#!/usr/bin/env python3
"""Side ASR for the extractor: transcribes the last seconds of the customer's microphone, so that the separate
extractor / judge LLM reads the customer's words too (the speech model is end-to-end and produces no transcript).

  POST /transcribe {"audio_b64": <base64 float32 mono 16 kHz>, "language": "en"|null} -> {"text": "..."}
  GET  /health -> "ready"

Start (needs openai-whisper):
  python tools/asr_server.py --port 22710 --model large-v3-turbo --device cuda
"""
import argparse, base64, json, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import numpy as np

model = None; lock = threading.Lock(); DEV = "cuda"; MODEL_NAME = "?"
# lessico dello sportello come initial_prompt: condiziona Whisper verso date e ore dette separate ("April 20 at 16", non "2016")
LEXICON = "Booking desk. The customer books an appointment: April 20th at 16:00, the 2nd of May at 3 pm, half past ten, 9 am, March, June."


class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a): sys.stderr.write("[asr] " + (fmt % a) + "\n")

    def _send(self, code, body: bytes, ctype="application/json"):
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        self._send(200, MODEL_NAME.encode(), "text/plain") if self.path == "/health" else self._send(404, b"")

    def do_POST(self):
        if self.path != "/transcribe": self._send(404, b""); return
        n = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
            x = np.frombuffer(base64.b64decode(req.get("audio_b64") or ""), dtype=np.float32)
            if len(x) < 1600: self._send(200, b'{"text": ""}'); return
            t0 = time.time()
            ctx_s = float(req.get("context_s") or 0)
            with lock:
                r = model.transcribe(x, language=req.get("language") or None, fp16=(DEV == "cuda"), condition_on_previous_text=False,
                                     initial_prompt=LEXICON if req.get("lexicon", False) else None)   # default OFF: misurato 05/09, allucina su audio povero
            # con il contesto davanti alla battuta: si tiene solo cio' che finisce dopo l'inizio della battuta
            segs = r.get("segments") or []
            kept = [s for s in segs if float(s.get("end", 0)) > ctx_s + 0.2] if ctx_s > 0 else segs
            text = " ".join((s.get("text") or "").strip() for s in kept).strip() if ctx_s > 0 else (r.get("text") or "").strip()
            self._send(200, json.dumps({"text": text, "language": r.get("language"), "asr_s": round(time.time() - t0, 2), "audio_s": round(len(x) / 16000, 1),
                                        "model": MODEL_NAME, "context_s": ctx_s, "dropped": len(segs) - len(kept)}).encode())
        except Exception as e:
            self._send(500, json.dumps({"error": f"{type(e).__name__}: {e}"}).encode())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=22710); ap.add_argument("--model", default="small"); ap.add_argument("--device", default="cuda")
    a = ap.parse_args()
    global model, DEV, MODEL_NAME
    import whisper
    DEV = a.device; MODEL_NAME = a.model
    print(f"carico whisper {a.model} su {DEV} ...", flush=True)
    model = whisper.load_model(a.model, device=DEV)
    print(f"pronto su :{a.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
