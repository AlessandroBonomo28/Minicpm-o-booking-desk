#!/usr/bin/env python3
"""Rebuilds the conversations recorded by the gateway, WITH the customer's words (Whisper on the microphone
chunks) and the model's text, on the same timeline.

Usage (needs openai-whisper):
  python tools/transcribe_sessions.py --last 3
  python tools/transcribe_sessions.py sess_73e1b7b68996 [sess_...]
  options: --sessions-dir DIR (default: data/sessions), --model small|medium, --device cuda|cpu

Legend: YOU = customer (Whisper), AI = the model's text, [FRAME] = video frame sent,
        [customer speaking, not transcribed] = audio with energy but no recognised text.
"""
import argparse, glob, json, os, sys, wave
import numpy as np


def load_session(d):
    fr = [json.loads(l) for l in open(f"{d}/stream.jsonl")]
    t0 = fr[0]["ts"]; wavs = sorted(glob.glob(f"{d}/blob/*.wav")); wi = 0
    mic, events, cur, last = [], [], "", None
    for f in fr:
        e = f["frame"]; t = f["ts"] - t0
        if f["dir"] == "up" and e.get("type") == "input.append":
            if (e.get("input") or {}).get("video_frames"): events.append((t, "frame", ""))
            if wi < len(wavs):
                with wave.open(wavs[wi]) as wf:
                    sr = wf.getframerate(); x = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768
                wi += 1
                if sr == 16000: mic.append((t, x))
        elif f["dir"] == "down":
            k = e.get("kind")
            if k == "text":
                if last != "text": cur = ""
                cur += e.get("text") or ""
            elif k == "listen":
                if cur: events.append((t, "ai", cur.strip())); cur = ""
            elif k == "audio" and wi < len(wavs): wi += 1
            if k in ("text", "listen"): last = k
    if cur: events.append((fr[-1]["ts"] - t0, "ai", cur.strip()))
    return mic, events, fr[-1]["ts"] - t0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sessions", nargs="*")
    ap.add_argument("--last", type=int, default=0)
    ap.add_argument("--sessions-dir", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sessions"))
    ap.add_argument("--model", default="small")
    ap.add_argument("--device", default=None)
    a = ap.parse_args()
    import torch, whisper
    dev = a.device or ("cuda" if torch.cuda.is_available() else "cpu")
    ids = list(a.sessions)
    if a.last:
        ids += [os.path.basename(p) for p in sorted(glob.glob(f"{a.sessions_dir}/sess_*"), key=os.path.getmtime)[-a.last:]]
    if not ids:
        print("nessuna sessione indicata (usa --last N o gli id)"); return 1
    model = whisper.load_model(a.model, device=dev)
    for sid in ids:
        d = f"{a.sessions_dir}/{sid}"
        if not os.path.exists(f"{d}/stream.jsonl"):
            print(f"\n===== {sid}: non trovata in {a.sessions_dir}"); continue
        mic, events, dur = load_session(d)
        print(f"\n===== {sid} | durata {dur:.0f}s | chunk mic {len(mic)}")
        if mic:
            total = int(max(t for t, _ in mic)) + 2
            track = np.zeros(total * 16000, dtype=np.float32)
            for t, x in mic:
                i = int(round(t)) * 16000; n = min(len(x), len(track) - i)
                if n > 0: track[i:i + n] = x[:n]
            res = model.transcribe(track, fp16=(dev == "cuda"), condition_on_previous_text=False)
            for s in res["segments"]:
                if s["text"].strip(): events.append((s["start"], "user", s["text"].strip()))
            print(f"   lingua rilevata: {res.get('language')}")
        events.sort(key=lambda e: e[0])
        for t, k, txt in events:
            if k == "frame": print(f"  {t:6.1f}s  [FRAME → screen changed]")
            elif k == "user": print(f"  {t:6.1f}s  YOU: {txt}")
            elif k == "ai": print(f"  {t:6.1f}s  AI:  {txt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
