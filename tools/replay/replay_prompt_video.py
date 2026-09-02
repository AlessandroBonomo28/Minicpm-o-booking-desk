import asyncio, base64, json, ssl, time, wave, sys, numpy as np, websockets
SESS = "/home/alex/progetti/MiniCPM-o-Demo-upstream-puro/data/sessions/sess_91048c4d2798"
OUT = "/tmp/claude-1000/-home-alex-progetti-MiniCPM-o-Demo/f961457c-85a6-44a5-a2a1-96bdcf75b1aa/scratchpad/ab"
NATIVE = "Streaming Omni Conversation."
LONG = ("Replicate the tone and style from the input audio. Your task is to be a helpful assistant using this voice pattern. "
        "Please answer the user's questions seriously and in a high quality. Please chat with the user in a high naturalness style. "
        "You are in duplex mode, where you can listen and speak at the same time.")
frames = [json.loads(l) for l in open(f"{SESS}/stream.jsonl")]
ups = [f["frame"] for f in frames if f["dir"] == "up"]
init_rec = ups[0]["payload"]; appends = [u["input"] for u in ups[1:] if u.get("type") == "input.append"]

def load_chunk(ref):
    with wave.open(f"{SESS}/{ref[1:]}") as wf:
        assert wf.getframerate() == 16000
        x = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    return x
chunks = []
for a in appends:
    x = load_chunk(a["audio"]); rms = float(np.sqrt((x**2).mean()))
    vf = a.get("video_frames") or []
    jpg = base64.b64encode(open(f"{SESS}/{vf[0][1:]}", "rb").read()).decode() if vf else None
    chunks.append((base64.b64encode(x.astype(np.float32).tobytes()).decode(), rms, jpg))
print(f"replay: {len(chunks)} chunk da 1 s, ref audio {len(init_rec['ref_audio_base64'])} b64", flush=True)

async def run_arm(name, prompt, video):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    url = f"wss://127.0.0.1:8006/v1/realtime?mode={'video' if video else 'audio'}&client_id=ab_{name}"
    events = []; t0 = None
    async with websockets.connect(url, ssl=ctx, max_size=None, ping_interval=None, open_timeout=60) as ws:
        await ws.send(json.dumps({"type": "session.init", "payload": {
            "system_prompt": prompt, "config": {"length_penalty": 1.1}, "max_slice_nums": 1,
            "use_tts": True, "ref_audio_base64": init_rec["ref_audio_base64"]}}))
        # aspetta session.created
        t_wait = time.time()
        while True:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=180))
            if m.get("type") == "session.created": break
            print("   pre-created:", str(m)[:120], flush=True)
        print(f"   session.created dopo {time.time()-t_wait:.1f}s", flush=True)
        t0 = time.time()
        async def reader():
            try:
                async for raw in ws:
                    m = json.loads(raw)
                    if m.get("type", "").startswith("response"):
                        events.append((time.time() - t0, m.get("kind"), m.get("text") or ""))
                    elif m.get("type") == "session.closed":
                        return
            except Exception:
                return
        rt = asyncio.create_task(reader())
        sent = []
        for i, (b64, rms, jpg) in enumerate(chunks):
            target = t0 + i * 1.0
            await asyncio.sleep(max(0, target - time.time()))
            inp = {"audio": b64}
            if video and jpg: inp["video_frames"] = [jpg]
            await ws.send(json.dumps({"type": "input.append", "input": inp}))
            sent.append((time.time() - t0, rms))
        await asyncio.sleep(3.0)
        await ws.send(json.dumps({"type": "session.close", "reason": "user_stop"}))
        try: await asyncio.wait_for(rt, timeout=5)
        except Exception: pass
    # analisi
    decis = [(t, "L" if k == "listen" else "S") for (t, k, _) in events if k in ("listen", "text")]
    attempts = yields = 0; lat = []
    for (t, rms) in sent:
        if rms < 0.02: continue
        prev = [k for (tt, k) in decis if tt <= t]
        if len(prev) >= 2 and prev[-1] == "S" and prev[-2] == "S":
            attempts += 1
            nxt = [tt for (tt, k) in decis if tt > t and k == "L"]
            if nxt and nxt[0] - t <= 2.5: yields += 1; lat.append(nxt[0] - t)
    ns = sum(1 for _, k in decis if k == "S"); nl = sum(1 for _, k in decis if k == "L")
    # turni = run consecutivi di S
    runs = []; cur = 0
    for _, k in decis:
        if k == "S": cur += 1
        elif cur: runs.append(cur); cur = 0
    if cur: runs.append(cur)
    text = "".join(x for (_, k, x) in events if k == "text")
    rep = {"arm": name, "prompt": prompt[:30], "video": video, "speak_units": ns, "listen_units": nl,
           "turni": len(runs), "durata_media_turno_s": round(float(np.mean(runs)), 1) if runs else 0, "turno_max_s": max(runs) if runs else 0,
           "interruzioni_cedute": yields, "tentativi": attempts, "latenza_media_s": round(float(np.mean(lat)), 2) if lat else None,
           "testo": text[:600]}
    json.dump({"rep": rep, "events": events, "sent": sent}, open(f"{OUT}/{name}.json", "w"))
    print(json.dumps(rep, ensure_ascii=False), flush=True)

async def main():
    for name, prompt, video in [("A_nativo_audio", NATIVE, False), ("B_lungo_audio", LONG, False), ("C_nativo_video", NATIVE, True)]:
        print(f"=== braccio {name} — {time.strftime('%H:%M:%S')}", flush=True)
        await run_arm(name, prompt, video)
        await asyncio.sleep(4)
asyncio.run(main())
