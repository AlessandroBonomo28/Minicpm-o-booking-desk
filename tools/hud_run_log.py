#!/usr/bin/env python3
"""Prints a desk run recorded by the gateway (logs_demo/hud_runs/). Default: the latest, without the 'frame ready / FRAME SENT' lines.
   usage: hud_run_log.py [session|latest] [--frames] [--conv]   (--conv: conversation log only)"""
import os, re, sys
d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs_demo", "hud_runs")
args = [a for a in sys.argv[1:] if not a.startswith("--")]
sid = args[0] if args else "latest"
path = os.path.join(d, sid if sid.endswith(".log") else sid + ".log")
if not os.path.exists(path):
    sys.exit(f"no run: {path}\navailable: " + ", ".join(sorted(os.listdir(d)) if os.path.isdir(d) else []))
frames = "--frames" in sys.argv; conv_only = "--conv" in sys.argv
for ln in open(path):
    if conv_only and "[hud:" in ln: continue
    if not frames and re.search(r"\] (frame pronto|FRAME INVIATO|frame ready|FRAME SENT)", ln):
        # tieni solo i frame il cui schermo cambia testo (frame pronto con 'schermo:' diverso dal precedente)
        m = re.search(r"(?:schermo|screen): (.*)$", ln)
        if not m: continue
        if m.group(1) == globals().get("_last"): continue
        globals()["_last"] = m.group(1)
    sys.stdout.write(ln)
