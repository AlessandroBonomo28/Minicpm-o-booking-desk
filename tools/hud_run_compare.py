#!/usr/bin/env python3
"""A/B comparison between desk runs (FRAME channel vs TEXT channel): numbers from the registry logs_demo/hud_runs/<sess>.log.
Usage: python3 tools/hud_run_compare.py [sess_a [sess_b ...]]   (no arguments: the last 2 sessions)
Per run: channel, duration, customer lines, model turns, DB writes, forces (by source), sigma stuck verdicts (by kind), reds, screen
updates, reaction time of the first turn after an EVENT update, KV window scrolls per minute, long turns (>12 s),
readback: how often the model spoke the record's day in the turn after a day change (screen reading)."""
import os, re, sys, glob, statistics as st

DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs_demo", "hud_runs")


def parse(path):
    rows = []
    for ln in open(path, errors="replace"):
        m = re.match(r"\s*([\d.]+)s \[(\w+):(\w*)\] (.*)", ln.rstrip("\n"))
        if m:
            rows.append((float(m.group(1)), m.group(2), m.group(3), m.group(4)))
    return rows


def summarize(path):
    rows = parse(path)
    if not rows:
        return None
    txt = lambda pred: [(t, x) for t, log, cls, x in rows if pred(x)]
    cfg = next((x for t, l, c, x in rows if x.startswith("CONFIG")), "")
    channel = (re.search(r"(?:canale|channel) (\w+)", cfg) or [None, "vision"])[1] if cfg else "vision"
    dur = rows[-1][0]
    user = txt(lambda x: (x.startswith("TU (ASR)") or x.startswith("YOU (ASR)")))
    omni = [(t, x.split(": ", 1)[1].strip() if ": " in x else "") for t, x in txt(lambda x: x.startswith("AI (turno completo)") or x.startswith("AI (full turn)"))]
    ev_lines = txt(lambda x: ("dopo la tua battuta" in x or "after your line" in x) and "FSM" in x)
    writes = [(t, x) for i, (t, x) in enumerate(ev_lines) if "FSM DONE book" in x and "confirmed" in x
              and not (i > 0 and "FSM DONE book" in ev_lines[i - 1][1] and "confirmed" in ev_lines[i - 1][1])]
    forces = txt(lambda x: x.startswith("FORCE_SPEAK ("))
    stuck = txt(lambda x: "σ (" in x and "STUCK" in x)
    kinds = {}
    for _, x in stuck:
        k = (re.search(r"STUCK (\w+)", x) or [None, "?"])[1]; kinds[k] = kinds.get(k, 0) + 1
    reds = txt(lambda x: x.startswith("SEMAFORO RED") or x.startswith("TRAFFIC LIGHT RED"))
    updates = txt(lambda x: ("FRAME INVIATO" in x or "SCHERMO (testo)" in x or "FRAME SENT" in x or "SCREEN TEXT" in x) and ("EVENTO" in x or "EVENT" in x))
    reactions = [float(m.group(1)) for _, x in txt(lambda x: x.startswith("REAZIONE") or x.startswith("REACTION")) for m in [re.search(r"(?:REAZIONE|REACTION) \+([\d.]+)s", x)] if m]
    scroll = txt(lambda x: "FINESTRA KV: scorrimento" in x or "KV WINDOW: scroll" in x)
    # durata dei turni: dall'inizio ("AI: ") alla fine ("AI (turno completo)")
    starts = [t for t, x in txt(lambda x: x.startswith("AI: "))]
    long_turns = 0; durs = []
    for i, (te, _) in enumerate(omni):
        ts = max([s for s in starts if s <= te], default=None)
        if ts is not None:
            d = te - ts; durs.append(d); long_turns += d > 12
    # lettura dello schermo: dopo un evento del cliente che fissa un giorno, il primo turno dell'omni contiene quel giorno?
    day_events = [(t, m.group(1)) for t, x in txt(lambda x: ("dopo la tua battuta" in x or "after your line" in x) and "FSM" in x) for m in [re.search(r"FSM (?:COLLECTING|CONFIRM|DONE) \w+ \w+ (\d{1,2})\b", x)] if m]
    read_ok = read_tot = 0; seen = set()
    for t, day in day_events:
        nxt = next(((te, x) for te, x in omni if te > t), None)
        if not nxt or (t, day) in seen:
            continue
        seen.add((t, day)); read_tot += 1
        s = re.sub(r"(?<=\d)\s+(?=\d)", "", nxt[1].lower())
        if re.search(rf"\b{int(day)}(?:st|nd|rd|th)?\b", s):
            read_ok += 1
    return {
        "sessione": os.path.basename(path).replace(".log", ""), "canale": channel, "durata_s": round(dur), "battute": len(user), "turni_omni": len(omni),
        "scritture": len(writes), "force": len(forces), "stuck": kinds, "rossi": len(reds), "aggiornamenti_evento": len(updates),
        "reazione_mediana_s": round(st.median(reactions), 2) if reactions else None, "reazioni": len(reactions),
        "scorrimenti_KV_al_min": round(len(scroll) / max(dur / 60, 1e-6), 1), "turni_oltre_12s": long_turns,
        "turno_mediano_s": round(st.median(durs), 1) if durs else None,
        "giorno_letto_nel_turno_dopo": f"{read_ok}/{read_tot}",
    }


def main(argv):
    if argv:
        paths = [os.path.join(DIR, a if a.endswith(".log") else a + ".log") for a in argv]
    else:
        paths = sorted((p for p in glob.glob(os.path.join(DIR, "sess_*.log"))), key=os.path.getmtime)[-2:]
    sums = [s for s in (summarize(p) for p in paths) if s]
    if not sums:
        print("nessuna run"); return 1
    keys = list(sums[0].keys())
    w = max(len(k) for k in keys)
    for k in keys:
        print(f"{k:<{w}}  " + "  ".join(f"{str(s[k]):<34}" for s in sums))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
