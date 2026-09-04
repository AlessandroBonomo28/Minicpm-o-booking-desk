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
        "description": "Classify what the CUSTOMER just said (the NOW line) and extract the month, the day of the month and the time they said in it. Each field is independent: fill only the ones actually said.",
        "parameters": {"type": "object", "properties": {
            "intent": {"type": "string", "enum": ["book", "check", "cancel", "none"],
                       "description": "check = a QUESTION about availability, no reservation asked ('is X available?', 'is X free?', "
                                      "'do you have anything on X?', 'any slot on X?'); "
                                      "book = an explicit request to reserve ('I'd like to book', 'book it', 'reserve', 'make an appointment'); "
                                      "when STATE says a request is IN PROGRESS and the customer just gives a month, a day or a time, "
                                      "use the intent of the request in progress (book or check); "
                                      "cancel = gives up the request in progress ('never mind', 'forget it', 'cancel that', 'stop'); "
                                      "none = anything else (chat, thanks, greetings)."},
            "month": {"type": ["string", "null"], "description": "the month name the customer said in the NOW line ('April'); null if no month was said"},
            "day": {"type": ["integer", "null"], "description": "the day of the month the customer said in the NOW line, as a number (1-31): 'the 2nd' -> 2, 'the twentieth' -> 20, 'April 2nd' -> 2; null if no day was said"},
            "time": {"type": ["string", "null"], "description": "the time the customer said in the NOW line, as 24h HH:MM; null if they did not say a time"}},
            "required": ["intent", "month", "day", "time"]}}},
]

SYSTEM = ("You are the action extractor for a booking desk. You see ONE sentence the CUSTOMER just said (the NOW line) and the "
          "STATE of the booking system. Always call the function `request` exactly once, about that sentence.\n"
          "A question about whether a date/time is free is a check, NOT a booking: book only when the customer asks to reserve.\n"
          "month, day, time are INDEPENDENT fields: fill each one ONLY if the customer said it in this sentence, otherwise null. "
          "The customer may give them in any order and any combination ('April' alone -> month only; 'the 2nd' alone -> day only; "
          "'at 3 pm' alone -> time only; 'April 2nd at 3 pm' -> all three). Never guess, never fill from the STATE, never invent: "
          "a day without a month has month=null, a month without a day has day=null. A day is a number or an ordinal "
          "('25', 'the 3rd', 'third', 'the twentieth'); a month is ONLY an explicit month name (January...December). "
          "Never turn an ordinal or a number into a month: 'third' -> day 3, month=null; '25' -> day 25, month=null.\n"
          "If a request is IN PROGRESS (see STATE) and the customer answers with a month, a day or a time, keep the intent in progress "
          "(book stays book, check stays check) with just the fields said. A bare number as the whole answer, in digits or in words: "
          "if STATE says the day is missing it is the day ('30' -> day 30, 'the twentieth' -> day 20); if STATE says the time is "
          "missing it is the hour ('15' -> 15:00, 'nine' -> 09:00, 'nine thirty' -> 09:30).\n"
          "cancel only while a request is in progress; after a finished request, 'thanks'/'bye' is intent=none.\n"
          "TIME RULES (24h HH:MM, convert spoken English): 'half past ten' -> 10:30; 'quarter past nine' -> 09:15; 'quarter to six' -> 05:45; "
          "'ten thirty' -> 10:30; '3 pm' / 'three in the afternoon' -> 15:00; '8 in the evening' -> 20:00; 'noon' -> 12:00; '9 am' -> 09:00; "
          "'at 15' -> 15:00; '5:20 pm' -> 17:20.\n"
          "DATE EXPRESSIONS: 'the second of April' -> month April, day 2; 'March thirty-first' -> month March, day 31; "
          "'the twenty-first of May' -> month May, day 21; 'book for May' / 'something in June' -> month only; "
          "'tomorrow' / 'next Monday' -> month=null, day=null (the system will ask for a calendar date).")

tok = None
model = None
lock = threading.Lock()
TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)


def fsm_line(fsm):
    """Stato della macchina (dal gateway) reso in una riga per l'estrattore.
    CONFIRM: verifica con posto LIBERO in sospeso -> lo stato porta la data offerta: 'yes' / 'that day' si risolvono da
    stato + domanda, senza righe di dialogo (idea di Alessandro, misurata 15/20 contro 13/20 del dialogo).
    COLLECTING: solo i NOMI dei campi raccolti e mancanti, mai i valori (copiabili).
    DONE/IDLE: nessun valore: una nuova richiesta riparte da zero (il "thank you" -> book(April 2, 15:00) veniva da qui)."""
    if not isinstance(fsm, dict):
        return "STATE: no request in progress."
    if fsm.get("state") == "CONFIRM":
        sl = fsm.get("slots") or {}
        when = f"{str(sl.get('month', '')).capitalize()} {sl.get('day', '')}"
        if sl.get("time") and sl.get("time") != "all-day":
            when += f" at {sl['time']}"
        return (f"STATE: OFFER PENDING. The desk just checked {when} and it is FREE (not booked yet). "
                f"If the customer accepts ('yes', 'ok', 'sure', 'book it', 'that day', 'the same day') -> intent=book with that month and day "
                f"(and time if it was part of the offer or is said now). A QUESTION about another date/time ('and the day after?', "
                f"'what about the 6th?') -> intent=check with only what they say. If they decline, thank or chat -> intent=none, all null.")
    if fsm.get("state") == "DONE" and (fsm.get("slots") or {}).get("month"):
        sl = fsm.get("slots") or {}
        when = f"{str(sl.get('month', '')).capitalize()} {sl.get('day', '')}"
        if sl.get("time") and sl.get("time") != "all-day":
            when += f" at {sl['time']}"
        what = {"confirmed": "was BOOKED", "taken": "was NOT booked (slot taken)", "booked": "is NOT free (already booked)"}.get(fsm.get("status"), "was handled")
        return (f"STATE: LAST REQUEST CLOSED. {when} {what}. Nothing is pending. If the customer refers to it with a change "
                f"('the next day' = day+1, 'the day after' = day+1, 'the day before' = day-1, 'the same day at 5' = same month/day, new time) "
                f"-> intent=check (or book if they ask to reserve) with the NEW month/day/time. 'thank you', 'bye', chat -> intent=none, all null. "
                f"Never repeat the closed request as a new one.")
    if fsm.get("state") != "COLLECTING":
        return "STATE: no request in progress."
    sl = fsm.get("slots") or {}
    got = [k for k in ("month", "day", "time") if sl.get(k)]
    miss = [k for k in (fsm.get("missing") or []) if k in ("month", "day", "time")]
    return (f"STATE: {fsm.get('intent')} IN PROGRESS; already collected: {', '.join(got) or 'nothing'}; "
            f"still missing: {', '.join(miss) or 'nothing'}.")


_EMPTY = {"", "none", "null", "unknown", "n/a", "not specified", "not mentioned"}


CONTEXT_RULES = ("\nThe lines before NOW are the conversation so far (OPERATOR = the desk, USER = the customer). Use them ONLY to "
                 "understand what the NOW line refers to: if the customer accepts an offer ('yes', 'ok', 'sure', 'book it') or refers "
                 "to a date the operator or the customer just mentioned ('that day', 'the same day'), take month/day/time from that "
                 "mention; 'the next day' / 'the day after' = that day + 1, 'the day before' = that day - 1. If the NOW line does not "
                 "refer to them, ignore the earlier lines completely: 'thank you', 'let me think', chit-chat -> intent none, all null.")


def decide(transcript, tools, fsm=None, context=0):
    """context=0: SOLO la battuta corrente (contratto attuale: le righe precedenti erano una fonte da cui copiare campi).
    context=N: esperimento (05/09, richiesta di Alessandro): anche le ultime N righe del dialogo, operatore compreso,
    per risolvere 'yes' / 'that day' / 'the next day'."""
    import torch
    lines = [(t.get("role"), (t.get("text") or "").strip()) for t in transcript if (t.get("text") or "").strip()]
    users = [x for r, x in lines if r == "user"]
    if not users:
        return {"tool_calls": [], "raw": "NO ACTION (nessuna riga utente)"}
    last_user_idx = max(i for i, (r, _) in enumerate(lines) if r == "user")
    convo = f"NOW USER: {lines[last_user_idx][1]}"
    system = SYSTEM
    if context and context != "state" and last_user_idx > 0:
        prev = lines[max(0, last_user_idx - int(context)):last_user_idx]
        convo = "\n".join(f"{'OPERATOR' if r == 'assistant' else 'USER'}: {x}" for r, x in prev) + "\n" + convo
        system = SYSTEM + CONTEXT_RULES
    messages = [{"role": "system", "content": system},
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
        for k in ("month", "day", "time", "date"):
            v = a.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                args[k] = str(int(v))
            elif isinstance(v, str) and v.strip().lower() not in _EMPTY:
                if k == "time" and not re.search(r"\d|noon|midnight|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|half|quarter", v.lower()):
                    continue   # 'time' / 'later': non e' un orario, non si passa alla FSM
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
                ctxmode = req.get("context") or 0
                if ctxmode == "state":
                    pass   # nessuna riga di dialogo: l'offerta in sospeso sta nella riga di stato
                elif ctxmode == "auto":
                    # contesto SOLO con un'offerta in sospeso (ultimo esito: verifica con posto libero): li' 'yes'/'that day'
                    # devono prendere la data dall'offerta; in ogni altro stato il contesto e' solo una fonte di copie
                    f = req.get("fsm") or {}
                    ctxmode = 3 if f.get("state") == "CONFIRM" else 0
                res = decide(transcript, req.get("tools") or DEFAULT_TOOLS, req.get("fsm"), ctxmode if ctxmode == "state" else int(ctxmode))
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
