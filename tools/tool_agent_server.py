#!/usr/bin/env python3
"""Modello SEPARATO per il tool calling (ramo HUD, 03/09).

L'omni (MiniCPM-o 4.5) parla e ascolta; questo servizio legge il TESTO della
conversazione e decide se chiamare una funzione e con quali argomenti. Modello:
Qwen3-1.7B (tool calling nativo via chat template, stessa famiglia del cervello
dell'omni), ~3.4 GB bf16 sulla stessa GPU.

  POST /decide  {"transcript":[{"role":"assistant"|"user","text":"..."}], "tools":[...opzionale...]}
                -> {"tool_calls":[{"name":..., "arguments":{...}}], "raw": "..."}
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

DEFAULT_TOOLS = [{
    "type": "function",
    "function": {
        "name": "check_availability",
        "description": "Checks in the booking system whether a slot is available. Call it ONLY when the operator "
                       "has just said they will check a specific date and time requested by the user.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "the requested date as spoken, e.g. 'March 31'"},
                "time": {"type": "string", "description": "the requested time in 24h HH:MM, e.g. '15:00'. OMIT it when the user asks about a whole day or gives no time."},
            },
            "required": ["date"],
        },
    },
}]

SYSTEM = ("You are the action extractor for a booking desk. Read the transcript (USER and OPERATOR) and call "
          "check_availability ONLY when the operator is about to check a specific date and time. If the date or the time "
          "is missing, or there is no availability check, call nothing and answer 'NO ACTION'.\n"
          "The date and time must come from the USER lines only; OPERATOR lines are context, never a source of dates. "
          "If the USER did not mention a date, answer 'NO ACTION'.\n"
          "TIME RULES (24h HH:MM, convert spoken English):\n"
          "- 'half past ten' -> 10:30; 'quarter past nine' -> 09:15; 'quarter to six' -> 05:45; 'ten thirty' -> 10:30\n"
          "- '3 pm' / 'three in the afternoon' -> 15:00; '8 in the evening' -> 20:00; 'noon' -> 12:00; '9 am' -> 09:00\n"
          "- 'at 15' / 'fifteen hundred' -> 15:00; '5:20 pm' -> 17:20\n"
          "DATE RULES: copy the date as spoken ('March 31', 'April 2nd', 'tomorrow', 'next Monday').\n"
          "If the user asks about a whole day or gives no time, call check_availability with the date ONLY (no time field). Never invent a time that was not said.")

tok = None
model = None
lock = threading.Lock()
TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)


def decide(transcript, tools):
    import torch
    convo = "\n".join(f"{'OPERATORE' if t.get('role') == 'assistant' else 'UTENTE'}: {t.get('text', '')}" for t in transcript)
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Trascrizione:\n{convo}\n\nDecidi."}]
    prompt = tok.apply_chat_template(messages, tools=tools, add_generation_prompt=True, tokenize=False, enable_thinking=False)
    with lock:
        ids = tok(prompt, return_tensors="pt").to(model.device)
        out = model.generate(**ids, max_new_tokens=160, do_sample=False)
        raw = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=False)
    calls = []
    for m in TOOL_CALL_RE.finditer(raw):
        try:
            c = json.loads(m.group(1))
            if isinstance(c, dict) and c.get("name"):
                calls.append({"name": c["name"], "arguments": c.get("arguments") or {}})
        except Exception:
            pass
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
                res = decide(transcript, req.get("tools") or DEFAULT_TOOLS)
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
