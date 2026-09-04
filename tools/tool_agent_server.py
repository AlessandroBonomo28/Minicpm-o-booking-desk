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
import os
import urllib.error
import re
import sys
import threading
import time
import urllib.request
ASR_URL = "http://127.0.0.1:22710/transcribe"
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL_DIR = "/home/alex/progetti/MiniCPM-o-Demo/modelli/Qwen3-1.7B"

# Contratto nello SCHEMA, prompt minimo, valori VERBATIM (come Rasa: "extract slot values exactly as provided by the user,
# avoid assumptions or format changes"): le conversioni (ore a parole, ordinali) le fa il gateway, in codice.
DEFAULT_TOOLS = [
    {"type": "function", "function": {
        "name": "request",
        "description": "What the customer's last sentence asks the booking desk to do, and the month / day / time words it contains.",
        "parameters": {"type": "object", "properties": {
            "intent": {"type": "string", "enum": ["none", "check", "book", "cancel"],
                       "description": "none = default: greetings, thanks, hesitation, thinking aloud, anything that is not a request; "
                                      "check = asks whether a date or time is free/available (a question, no reservation); "
                                      "book = asks to reserve / make an appointment, or gives a month/day/time while a request is in progress; "
                                      "cancel = gives up the request in progress ('never mind', 'forget it', 'cancel')."},
            "month": {"type": ["string", "null"], "description": "the month NAME the customer said, exactly as said (e.g. 'April'); null if no month name was said. Numbers are never a month."},
            "day": {"type": ["string", "null"], "description": "the day of the month the customer said, exactly as said (e.g. '2nd', 'the second', 'twenty-first', '30'); null if no day was said."},
            "time": {"type": ["string", "null"], "description": "the time the customer said, exactly as said (e.g. '3 pm', 'half past ten', 'nine thirty', '15'); null if no time was said."}},
            "required": ["intent", "month", "day", "time"]}}},
]

SYSTEM = ("You are the booking desk's request extractor. Read STATE and the customer's last sentence, then call `request` once.\n"
          "Copy month, day and time words exactly as the customer said them in this sentence; null when not said. Never guess.\n"
          "If STATE says a request is in progress, a bare number or a bare date/time word is the answer to what is still missing "
          "(day if the day is missing, otherwise time), with the same intent as the request in progress.\n"
          "If nothing is requested, intent is none."
          + ("\nA number or an ordinal ('25', 'the 3rd', 'third', 'twentieth') is a day or a time, never a month; month is only a month name."
             if os.environ.get("TA_ORDINAL_RULE") == "1" else ""))

# Prompt "smart" (TA_PROMPT=smart), pensato per i modelli cloud: qui si CHIEDE di risolvere i riferimenti e di calcolare,
# cose che al 1,7B non chiediamo perche' non le fa (con il prompt minimo i cloud copiano 'the day after' alla lettera).
SYSTEM_SMART = ("You are the booking desk's request extractor. Read STATE and the customer's last sentence, then call `request` once.\n"
                "Fill month (month name), day (number 1-31) and time (24h HH:MM) with what the sentence says. Resolve references using STATE: "
                "if an offer is pending, 'yes'/'ok'/'book it'/'that day' means book the offered date; 'the day after'/'the next day' means the "
                "offered day + 1 and 'the day before' the offered day - 1 (same month); a different day ('no, the 6th') or a question about "
                "another date is a check, not a booking. Convert spoken times ('half past ten' -> 10:30, '3 pm' -> 15:00).\n"
                "If STATE has no pending offer, never take values from it: a sentence without a date has month=null and day=null.\n"
                "If a request is in progress, a bare number answers what is still missing (day, otherwise time), same intent as the request.\n"
                "If nothing is requested (greetings, thanks, hesitation, thinking aloud), intent is none and all fields null.")
if os.environ.get("TA_PROMPT") == "smart":
    SYSTEM = SYSTEM_SMART

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


# ---- backend cloud (05/09): endpoint OpenAI-compatible del provider Cline (https://api.cline.bot/api/v1), stesso schema.
#      Chiave/modello da ~/.config/tool_agent.env (TA_API_KEY, TA_BASE_URL, TA_MODEL); il locale resta come fallback.
BACKEND = "local"
CLOUD = {"base_url": "https://api.cline.bot/api/v1", "model": "google/gemini-3.5-flash-lite", "key": "", "timeout": 4.0}


def load_env_file(path):
    try:
        for line in open(os.path.expanduser(path)):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass


def decide_cloud(messages, tools):
    """Una chiamata chat/completions con tool_choice forzato su `request`. Ritorna (raw_arguments_json, model, ms) o solleva."""
    body = json.dumps({"model": CLOUD["model"], "messages": messages, "tools": tools, "temperature": 0, "max_tokens": 200,
                       "tool_choice": {"type": "function", "function": {"name": "request"}}}).encode()
    req = urllib.request.Request(CLOUD["base_url"].rstrip("/") + "/chat/completions", data=body,
                                 headers={"Authorization": f"Bearer {CLOUD['key']}", "content-type": "application/json"})
    t0 = time.time()
    d = json.loads(urllib.request.urlopen(req, timeout=CLOUD["timeout"]).read())
    d = d.get("data", d)
    ch = d["choices"][0]["message"]
    tc = ch.get("tool_calls") or []
    if not tc:
        return "", d.get("model"), (time.time() - t0) * 1000
    return tc[0]["function"]["arguments"], d.get("model"), (time.time() - t0) * 1000


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
    backend_used = BACKEND
    raw = ""
    if BACKEND == "cline":
        try:
            args_json, used_model, ms = decide_cloud(messages, tools)
            raw = f'<tool_call>{{"name": "request", "arguments": {args_json or "{}"}}}</tool_call>'
            backend_used = f"cline:{used_model} {ms:.0f}ms"
        except Exception as e:
            sys.stderr.write(f"[tool-agent] cloud non disponibile ({type(e).__name__}: {str(e)[:80]}): fallback locale\n")
            backend_used = "local (fallback)"
    if not raw and tok is not None:
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
    return {"tool_calls": calls, "raw": raw.replace("<|im_end|>", "").strip()[:400], "backend": backend_used}


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
    ap.add_argument("--backend", choices=["local", "cline"], default="local", help="cline = API cloud (chiave in ~/.config/tool_agent.env), locale come fallback")
    ap.add_argument("--cloud-model", default=None, help="id modello sul provider (default: TA_MODEL o google/gemini-3.5-flash-lite)")
    ap.add_argument("--no-local", action="store_true", help="con --backend cline: non caricare il modello locale (niente fallback, libera la VRAM)")
    args = ap.parse_args()
    global tok, model, BACKEND
    load_env_file("~/.config/tool_agent.env")
    BACKEND = args.backend
    if BACKEND == "cline":
        CLOUD["key"] = os.environ.get("TA_API_KEY", ""); CLOUD["base_url"] = os.environ.get("TA_BASE_URL", CLOUD["base_url"])
        CLOUD["model"] = args.cloud_model or os.environ.get("TA_MODEL", CLOUD["model"])
        if not CLOUD["key"]:
            raise SystemExit("TA_API_KEY mancante (~/.config/tool_agent.env)")
        print(f"backend cloud: {CLOUD['base_url']} modello {CLOUD['model']} (timeout {CLOUD['timeout']} s)", flush=True)
    if BACKEND == "local" or not args.no_local:
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
