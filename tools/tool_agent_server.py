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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL_DIR = "/home/alex/progetti/MiniCPM-o-Demo/modelli/Qwen3-1.7B"

DEFAULT_TOOLS = [{
    "type": "function",
    "function": {
        "name": "check_availability",
        "description": "Verifica sul gestionale se uno slot di prenotazione e' libero. Da chiamare SOLO quando "
                       "l'operatore ha appena detto che controlla una data e un'ora precise richieste dall'utente.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "la data richiesta, es. '31 marzo'"},
                "time": {"type": "string", "description": "l'ora richiesta in formato HH:MM, es. '15:00'"},
            },
            "required": ["date", "time"],
        },
    },
}]

SYSTEM = ("Sei l'estrattore di azioni di uno sportello prenotazioni. Leggi la trascrizione (utente e operatore) "
          "e chiama check_availability SOLO se l'operatore sta per verificare una data e un'ora precise. "
          "Se mancano data o ora, o non c'e' una richiesta di verifica, non chiamare nulla e rispondi 'NESSUNA AZIONE'.")

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
            res = decide(req.get("transcript") or [], req.get("tools") or DEFAULT_TOOLS)
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
