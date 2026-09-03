#!/usr/bin/env python3
"""ASR di servizio per il tool agent (ramo HUD): trascrive gli ultimi secondi del microfono
dell'utente, cosi' il modello separato di tool calling legge ANCHE le parole dell'utente
(l'omni non produce trascrizioni: e' end-to-end).

  POST /transcribe {"audio_b64": <base64 float32 mono 16 kHz>, "language": "en"|null} -> {"text": "..."}
  GET  /health -> "ready"

Avvio (env cosyvoice2, che ha openai-whisper):
  /home/alex/miniconda3/envs/cosyvoice2/bin/python tools/asr_server.py --port 22710 --model small
"""
import argparse, base64, json, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import numpy as np

model = None; lock = threading.Lock(); DEV = "cuda"


class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a): sys.stderr.write("[asr] " + (fmt % a) + "\n")

    def _send(self, code, body: bytes, ctype="application/json"):
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        self._send(200, b"ready", "text/plain") if self.path == "/health" else self._send(404, b"")

    def do_POST(self):
        if self.path != "/transcribe": self._send(404, b""); return
        n = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
            x = np.frombuffer(base64.b64decode(req.get("audio_b64") or ""), dtype=np.float32)
            if len(x) < 1600: self._send(200, b'{"text": ""}'); return
            with lock:
                r = model.transcribe(x, language=req.get("language") or None, fp16=(DEV == "cuda"), condition_on_previous_text=False)
            self._send(200, json.dumps({"text": (r.get("text") or "").strip(), "language": r.get("language")}).encode())
        except Exception as e:
            self._send(500, json.dumps({"error": f"{type(e).__name__}: {e}"}).encode())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=22710); ap.add_argument("--model", default="small"); ap.add_argument("--device", default="cuda")
    a = ap.parse_args()
    global model, DEV
    import whisper
    DEV = a.device
    print(f"carico whisper {a.model} su {DEV} ...", flush=True)
    model = whisper.load_model(a.model, device=DEV)
    print(f"pronto su :{a.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
