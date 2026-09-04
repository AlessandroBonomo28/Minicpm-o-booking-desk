#!/usr/bin/env python3
"""Modello SEPARATO per il tool calling (ramo HUD, 03/09).

L'omni (MiniCPM-o 4.5) parla e ascolta; questo servizio legge il TESTO della
conversazione e decide se chiamare una funzione e con quali argomenti. Modello:
Qwen3-1.7B (tool calling nativo via chat template, stessa famiglia del cervello
dell'omni), ~3.4 GB bf16 sulla stessa GPU.

  POST /decide  {"transcript":[{"role":"assistant"|"user","text":"..."}], "user_audio_b64": ..., "language": "en",
                 "fsm": {stato della macchina dal gateway, opzionale}, "tools":[...opzionale...]}
                -> {"tool_calls":[{"name": book|check|cancel, "arguments":{...}}], "raw": "...", "user_text", "asr_s", "llm_s"}
  La FSM (merge dei campi, cosa manca, esecuzione) sta nel gateway: qui si estrae SOLO cio' che l'utente ha detto.
  GET  /health  -> "ready"

Avvio:  conda run -n minicpm python tools/tool_agent_server.py --port 22700
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
import urllib.request
ASR_URL = "http://127.0.0.1:22710/transcribe"
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL_DIR = "/home/alex/progetti/MiniCPM-o-Demo/modelli/Qwen3-1.7B"

DEFAULT_TOOLS = [
    {"type": "function", "function": {
        "name": "request",
        "description": "Classify what the CUSTOMER just said (the NOW line) and extract the date/time they said in it.",
        "parameters": {"type": "object", "properties": {
            "intent": {"type": "string", "enum": ["book", "check", "cancel", "none"],
                       "description": "check = a QUESTION about availability, no reservation asked ('is X available?', 'is X free?', "
                                      "'do you have anything on X?', 'any slot on X?'); "
                                      "book = an explicit request to reserve ('I'd like to book', 'book it', 'reserve', 'make an appointment'); "
                                      "when STATE says a request is IN PROGRESS and the customer just gives a date, a day or a time, "
                                      "use the intent of the request in progress (book or check); "
                                      "cancel = gives up the request in progress ('never mind', 'forget it', 'cancel that', 'stop'); "
                                      "none = anything else (chat, thanks, greetings)."},
            "date": {"type": ["string", "null"], "description": "the date the customer said in the NOW line: 'Month D' (e.g. month name + day number), or the month alone if only the month was said; null if no date or month was said"},
            "time": {"type": ["string", "null"], "description": "the time the customer said in the NOW line, as 24h HH:MM; null if they did not say a time"}},
            "required": ["intent", "date", "time"]}}},
]

SYSTEM = ("You are the action extractor for a booking desk. You see ONE sentence the CUSTOMER just said (the NOW line) and the "
          "STATE of the booking system. Always call the function `request` exactly once, about that sentence.\n"
          "A question about whether a date/time is free is a check, NOT a booking: book only when the customer asks to reserve.\n"
          "date and time: ONLY if the customer said them in this sentence, otherwise null. Never guess, never fill from the STATE, "
          "never invent. A sentence without a date has date=null; without a time has time=null.\n"
          "If a request is IN PROGRESS (see STATE) and the customer answers with a date, a day or a time, keep the intent in progress "
          "(book stays book, check stays check) with just that field. If they correct a field ('no, the 3rd'), same intent with the "
          "corrected value (use the month from STATE if only the day is said).\n"
          "A bare number as the whole answer, in digits OR in words ('30', 'nine', 'the twentieth'): if STATE says the day of the month "
          "is missing, it is the day (with the month from STATE: '30' -> 'March 30', 'the twentieth' -> 'April 20'); if STATE says the "
          "time is missing, it is the hour ('15' -> 15:00, 'nine' / 'at nine' -> 09:00, 'nine thirty' -> 09:30).\n"
          "cancel only while a request is in progress; after a finished request, 'thanks'/'bye' is intent=none.\n"
          "TIME RULES (24h HH:MM, convert spoken English): 'half past ten' -> 10:30; 'quarter past nine' -> 09:15; 'quarter to six' -> 05:45; "
          "'ten thirty' -> 10:30; '3 pm' / 'three in the afternoon' -> 15:00; '8 in the evening' -> 20:00; 'noon' -> 12:00; '9 am' -> 09:00; "
          "'at 15' -> 15:00; '5:20 pm' -> 17:20.\n"
          "DATE RULES ('Month D', month name + day in digits): 'the second of April' -> April 2; 'March thirty-first' -> March 31; "
          "'the twenty-first of May' -> May 21; 'April 2nd' -> April 2. A MONTH ALONE IS A VALID DATE VALUE: 'book for May', "
          "'something in June', 'on March' -> date='May' / 'June' / 'March' (the system will then ask for the day). "
          "If only the day is said ('the 3rd', 'the third') and STATE has a month, use that month ('April 3'). "
          "'tomorrow' / 'next Monday' stay as said (the system will ask for a calendar date).")

tok = None
model = None
lock = threading.Lock()
TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)


def fsm_line(fsm):
    """Stato della macchina (dal gateway) reso in una riga per l'estrattore. In RESULT/IDLE NON si passano i campi:
    una nuova richiesta riparte da zero e il modello, se li vede, li ricopia ("thank you" -> book(April 2, 15:00))."""
    if not isinstance(fsm, dict) or fsm.get("state") != "COLLECTING":
        return "STATE: no request in progress."
    sl = fsm.get("slots") or {}
    got = [f"{k}={sl.get(k)}" for k in ("date", "time") if sl.get(k)]
    if not sl.get("date") and sl.get("month"):
        got.append(f"month={sl['month']} (day not said yet)")
    miss = [("day of the month" if (m == "date" and sl.get("month")) else m) for m in (fsm.get("missing") or [])]
    return f"STATE: {fsm.get('intent')} IN PROGRESS, collected: {', '.join(got) or 'nothing yet'}; still missing: {', '.join(miss)}."


_EMPTY = {"", "none", "null", "unknown", "n/a", "not specified", "not mentioned"}


def decide(transcript, tools, fsm=None):
    import torch
    users = [t.get("text", "") for t in transcript if t.get("role") == "user" and (t.get("text") or "").strip()]
    if not users:
        return {"tool_calls": [], "raw": "NO ACTION (nessuna riga utente)"}
    # SOLO la battuta appena detta: le righe precedenti erano una fonte da cui copiare campi ("is it free?" dopo una
    # prenotazione -> check(May, 15) ripescati dai turni prima). Il contesto multi-turno lo porta la riga di stato.
    convo = f"NOW USER: {users[-1]}"
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"{fsm_line(fsm)}\n\n{convo}\n\nCall request() about the NOW line."}]
    prompt = tok.apply_chat_template(messages, tools=tools, add_generation_prompt=True, tokenize=False, enable_thinking=False)
    with lock:
        ids = tok(prompt, return_tensors="pt").to(model.device)
        out = model.generate(**ids, max_new_tokens=120, do_sample=False)
        raw = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=False)
    calls = []
    for m in TOOL_CALL_RE.finditer(raw):
        try:
            c = json.loads(m.group(1))
        except Exception:
            continue
        if not isinstance(c, dict):
            continue
        a = c.get("arguments") or {}
        intent = str(a.get("intent") or c.get("name") or "none").lower()
        if intent not in ("book", "check", "cancel"):
            continue
        args = {}
        for k in ("date", "time"):
            v = a.get(k)
            if isinstance(v, str) and v.strip().lower() not in _EMPTY:
                args[k] = v.strip()
        calls.append({"name": intent, "arguments": args})
        break   # una sola decisione per turno
    return {"tool_calls": calls, "raw": raw.replace("<|im_end|>", "").strip()[:400]}


class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):
        sys.stderr.write("[tool-agent] " + (fmt % a) + "\n")

    def _send(self, code, body: bytes, ctype="application/json"):
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, b"ready", "text/plain")
        else:
            self._send(404, b"")

    def do_POST(self):
        if self.path != "/decide":
            self._send(404, b""); return
        n = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
            transcript = list(req.get("transcript") or [])
            user_text = ""; asr_s = None; t_all = time.time()
            if req.get("user_audio_b64"):
                # ASR degli ultimi secondi del microfono (servizio separato, env cosyvoice2)
                try:
                    body = json.dumps({"audio_b64": req["user_audio_b64"], "language": req.get("language") or "en"}).encode()
                    r = urllib.request.urlopen(urllib.request.Request(ASR_URL, data=body, headers={"content-type": "application/json"}), timeout=20)
                    rj = json.loads(r.read()); user_text = (rj.get("text") or "").strip(); asr_s = rj.get("asr_s")
                except Exception as e:
                    user_text = ""; sys.stderr.write(f"[tool-agent] ASR non disponibile: {e}\n")
                if user_text:
                    # la voce dell'utente precede l'ultima battuta dell'operatore
                    if transcript and transcript[-1].get("role") == "assistant":
                        transcript.insert(len(transcript) - 1, {"role": "user", "text": user_text})
                    else:
                        transcript.append({"role": "user", "text": user_text})
            t_llm = time.time()
            if req.get("user_audio_b64") and not user_text:
                # il trigger e' il turno dell'utente: senza parole dell'utente non c'e' nulla da decidere
                res = {"tool_calls": [], "raw": "NO ACTION (nessun testo utente)"}
            else:
                res = decide(transcript, req.get("tools") or DEFAULT_TOOLS, req.get("fsm"))
            res["user_text"] = user_text; res["asr_s"] = asr_s; res["llm_s"] = round(time.time() - t_llm, 2); res["total_s"] = round(time.time() - t_all, 2)
            self._send(200, json.dumps(res, ensure_ascii=False).encode())
        except Exception as e:
            self._send(500, json.dumps({"error": f"{type(e).__name__}: {e}"}).encode())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=22700)
    ap.add_argument("--model-dir", default=MODEL_DIR)
    args = ap.parse_args()
    global tok, model
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    print(f"carico {args.model_dir} ...", flush=True)
    tok = AutoTokenizer.from_pretrained(args.model_dir)
    model = AutoModelForCausalLM.from_pretrained(args.model_dir, torch_dtype=torch.bfloat16, low_cpu_mem_usage=True).to("cuda").eval()
    print(f"pronto su :{args.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), H).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
