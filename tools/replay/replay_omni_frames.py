import asyncio, base64, json, ssl, time, wave, io, numpy as np, websockets
from PIL import Image
SESS = "/home/alex/progetti/MiniCPM-o-Demo/data/sessions/sess_1adc5622a4dc"
OUT = "/tmp/claude-1000/-home-alex-progetti-MiniCPM-o-Demo/f961457c-85a6-44a5-a2a1-96bdcf75b1aa/scratchpad/ab"
frames = [json.loads(l) for l in open(f"{SESS}/stream.jsonl")]
ups = [f["frame"] for f in frames if f["dir"] == "up"]
init_rec = ups[0]["payload"]; appends = [u["input"] for u in ups[1:] if u.get("type") == "input.append"]
def load_chunk(ref):
    with wave.open(f"{SESS}/{ref[1:]}") as wf:
        x = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    return x
chunks = []
for a in appends:
    x = load_chunk(a["audio"]); rms = float(np.sqrt((x**2).mean()))
    vf = a.get("video_frames") or []
    jpg = base64.b64encode(open(f"{SESS}/{vf[0][1:]}", "rb").read()).decode() if vf else None
    chunks.append((base64.b64encode(x.astype(np.float32).tobytes()).decode(), rms, jpg))
# fotogramma nero costante, stessa risoluzione del primo frame reale
first = next(j for _, _, j in chunks if j)
w, h = Image.open(io.BytesIO(base64.b64decode(first))).size
buf = io.BytesIO(); Image.new("RGB", (w, h), (0, 0, 0)).save(buf, "JPEG", quality=70); BLACK = base64.b64encode(buf.getvalue()).decode()
print(f"replay: {len(chunks)} chunk, frame reali={sum(1 for c in chunks if c[2])}, frame {w}x{h}, prompt={init_rec['system_prompt'][:50]!r}", flush=True)

def loopiness(text):
    # frazione di 4-grammi di parole ripetuti
    w_ = text.split(); grams = [" ".join(w_[i:i+4]) for i in range(len(w_) - 3)]
    return round(1 - len(set(grams)) / len(grams), 2) if grams else 0.0

async def run_arm(name, video_mode):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    url = f"wss://127.0.0.1:8006/v1/realtime?mode={'video' if video_mode else 'audio'}&client_id=ab_{name}"
    events = []
    async with websockets.connect(url, ssl=ctx, max_size=None, ping_interval=None, open_timeout=60) as ws:
        payload = {k: init_rec[k] for k in ("system_prompt", "config", "use_tts", "ref_audio_base64") if k in init_rec}
        payload["max_slice_nums"] = 1
        await ws.send(json.dumps({"type": "session.init", "payload": payload}))
        while True:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=180))
            if m.get("type") == "session.created": break
        t0 = time.time()
        async def reader():
            try:
                async for raw in ws:
                    m = json.loads(raw)
                    if m.get("type", "").startswith("response"): events.append((time.time() - t0, m.get("kind"), m.get("text") or ""))
                    elif m.get("type") == "session.closed": return
            except Exception: return
        rt = asyncio.create_task(reader())
        for i, (b64, rms, jpg) in enumerate(chunks):
            await asyncio.sleep(max(0, t0 + i * 1.0 - time.time()))
            inp = {"audio": b64}
            if video_mode == "real" and jpg: inp["video_frames"] = [jpg]
            elif video_mode == "black": inp["video_frames"] = [BLACK]
            await ws.send(json.dumps({"type": "input.append", "input": inp}))
        await asyncio.sleep(4.0)
        await ws.send(json.dumps({"type": "session.close", "reason": "user_stop"}))
        try: await asyncio.wait_for(rt, timeout=5)
        except Exception: pass
    text = "".join(x for (_, k, x) in events if k == "text")
    ns = sum(1 for (_, k, _) in events if k == "text"); nl = sum(1 for (_, k, _) in events if k == "listen")
    # confini di parola: quante giunzioni tra delta di testo consecutivi sono incollate (lettera-lettera senza spazio)
    deltas = [x for (_, k, x) in events if k == "text" and x]
    joins = sum(1 for a, b in zip(deltas, deltas[1:]) if a and b and a[-1].isalnum() and b[0].isalnum())
    rep = {"arm": name, "speak": ns, "listen": nl, "loop_index": loopiness(text), "giunzioni_incollate": f"{joins}/{max(1, len(deltas)-1)}", "testo": text[:420]}
    print(json.dumps(rep, ensure_ascii=False), flush=True)
    json.dump({"rep": rep, "events": events}, open(f"{OUT}/omni_{name}.json", "w"))

async def main():
    for name, vm in [("A_frame_reali", "real"), ("B_solo_audio", None), ("C_frame_nero", "black")]:
        print(f"=== {name} — {time.strftime('%H:%M:%S')}", flush=True); await run_arm(name, vm); await asyncio.sleep(4)
asyncio.run(main())
