#!/usr/bin/env python3
"""Probes for the judge sigma (verdict: status/kind/help/claim/claim_day/claim_time/readback) and for the extractor, on the cases
of session sess_41c874e48161: the operator's proposal, the customer's yes to a proposal, the screen question repeated, a stale help line.
Runs against the live extractor service (:22700, cloud backend). python3 tools/sigma_probe.py [-v]"""
import json, sys, time, urllib.request
V = "-v" in sys.argv
A = lambda x: {"role": "assistant", "text": x}
U = lambda x: {"role": "user", "text": x}
SL = lambda m="", d="", t="": {"month": m, "day": d, "time": t, "date": f"{m} {d}".strip() if m and d else ""}
COLL_APR = {"state": "COLLECTING", "intent": "book", "slots": SL("april"), "missing": ["day", "time"], "tentative": {}}
COLL_PROP = {"state": "COLLECTING", "intent": "book", "slots": SL("april", "15"), "missing": ["time"], "tentative": {"day": "proposal"}}
COLL_15 = {"state": "COLLECTING", "intent": "book", "slots": SL("april", "15"), "missing": ["time"], "tentative": {}}
CONF_CHK = {"state": "CONFIRM", "intent": "check", "status": "available", "slots": SL("april", "15", "all-day"), "missing": []}
BASE = [U("I'd like to book a call."), A("Sure, which month?"), U("In April."), A("Which day would you like?"), U("I don't know, pick one randomly.")]

def post(path, body):
    t0 = time.time()
    d = json.loads(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:22700{path}", data=json.dumps(body).encode(),
                                          headers={"content-type": "application/json"}), timeout=60).read())
    return d, time.time() - t0

SIGMA = [  # (nome, schermo, fsm, conversazione, turno operatore, reason, timing, previous_help, atteso)
    ("'I've cancelled your booking' con lo schermo CANCEL IT? -> claim booking_cancelled", "APRIL 20, 3 PM | BOOKED | CANCEL IT?",
     {"state": "CONFIRM", "intent": "unbook", "status": "pending_cancel", "slots": SL("april", "20", "15:00"), "missing": [], "tentative": {}},
     [U("Cancel my booking of April 20 at 3 pm.")], "Okay, I've cancelled your booking on April 20th at 3 PM.", "turn_end", {"since_user_s": 2.0, "since_omni_s": 0, "omni_speaking": False}, "",
     {"claim": "booking_cancelled"}),
    ("proposta = claim slot_free giorno 15, ok", "BOOK: APRIL | WHICH DAY?", COLL_APR, BASE,
     "Okay, let's pick a random day. How about April 15th? Does that work?", "turn_end", {"since_user_s": 2.1, "since_omni_s": 0, "omni_speaking": False}, "",
     {"status": "ok", "claim": "slot_free", "claim_day": "15"}),   # claim_month: flash-lite non lo compila, lo ricava il gateway dal testo
    ("mese ancora mancante, 'How about April 15th?' -> claim con mese e giorno, ok", "BOOK: ? | WHICH MONTH?",
     {"state": "COLLECTING", "intent": "book", "slots": SL(), "missing": ["month", "day", "time"], "tentative": {}},
     [U("I'd like to book a call."), A("Sure, which month?"), U("I don't know, you pick.")],
     "Okay. How about April 15th? Does that work for you?", "turn_end", {"since_user_s": 2.0, "since_omni_s": 0, "omni_speaking": False}, "",
     {"status": "ok", "claim": "slot_free", "claim_day": "15"}),
    ("proposta di un giorno pieno (lo schermo non lo sa): σ ok, lo verifica il DB", "BOOK: APRIL | WHICH DAY?", COLL_APR, BASE,
     "How about April 1st? Does that work?", "turn_end", {"since_user_s": 2.1, "since_omni_s": 0, "omni_speaking": False}, "",
     {"status": "ok", "claim": "slot_free", "claim_day": "1"}),
    ("annuncio senza il si' del cliente, con la proposta a schermo -> stuck false_claim", "BOOK: APRIL 15? | DOES THAT WORK?", COLL_PROP,
     BASE + [A("Okay, let's pick a random day. How about April 15th? Does that work?")],
     "Great! I'll go ahead and book April 15th for you. Is there anything else?", "turn_end", {"since_user_s": 9.8, "since_omni_s": 0, "omni_speaking": False}, "",
     {"status": "stuck", "kind": "false_claim", "claim": "booking_confirmed"}),
    ("il cliente accetta la proposta, l'operatore chiede l'ora -> ok", "BOOK: APRIL 15 | WHAT TIME?", COLL_15,
     BASE + [A("How about April 15th? Does that work?"), U("Uh, yes.")],
     "Great. What time would you like?", "turn_end", {"since_user_s": 1.5, "since_omni_s": 0, "omni_speaking": False}, "",
     {"status": "ok"}),
    ("domanda dello schermo ripetuta (WHAT TIME?) -> ok", "APRIL 15, ALL DAY | FREE | WHAT TIME?", CONF_CHK,
     BASE + [A("How about April 15th?"), U("Is it available April 15?")],
     "Yes, April 15th is available. What time would you like to book?", "turn_end", {"since_user_s": 3.0, "since_omni_s": 0, "omni_speaking": False}, "",
     {"status": "ok"}),
    # (misurato 08/09: con un HELP precedente diverso dallo schermo, flash-lite da' la precedenza all'HELP -> stuck ignores_screen anche se
    #  il turno segue lo schermo. Quindi il client azzera l'aiuto quando la macchina cambia con la battuta del cliente: mai un aiuto stantio a σ.)
    ("silenzio dopo il si' del cliente -> stuck silent, aiuto sull'ora", "BOOK: APRIL 15 | WHAT TIME?", COLL_15,
     BASE + [A("How about April 15th? Does that work?"), U("Uh, yes.")],
     "", "no_reply", {"since_user_s": 3.2, "since_omni_s": 8.0, "omni_speaking": False}, "",
     {"status": "stuck", "kind": "silent", "help_has": "time"}),
    ("filler del cliente, silenzio -> ok", "BOOK: APRIL 15? | DOES THAT WORK?", COLL_PROP,
     BASE + [A("How about April 15th? Does that work?"), U("Um...")],
     "", "no_reply", {"since_user_s": 3.1, "since_omni_s": 6.0, "omni_speaking": False}, "",
     {"status": "ok"}),
    ("TURNO APERTO a 10 s: elenca i giorni liberi uno per uno -> stuck repeating", "FREE: APRIL | FREE, EXCEPT 1, 2, 3, 15, 20, 25, 28 | WHICH DAY?",
     {"state": "COLLECTING", "intent": "check", "slots": SL("april"), "missing": ["day"], "tentative": {}, "month_info": {"month": "april", "booked_days": [1, 2, 3, 15, 20, 25, 28], "full_days": []}},
     [U("I'd like to book a call."), A("Which month?"), U("April."), A("Which day?"), U("I don't know when is it free"), A("Okay, let me check. The 1st, 2nd, 3rd, 15th, 20th, 25th, 28th are booked."), U("I don't know.")],
     "Okay, let me check again. The 4th, 5th, 6th, 7th, 8th, 9th, 10th, 11th, 12th", "mid_turn", {"since_user_s": 12.0, "since_omni_s": None, "omni_speaking": True, "turn_s": 10.0}, "",
     {"status": "stuck", "kind": "repeating"}),
    ("TURNO APERTO a 10 s: ripete se stesso -> stuck repeating", "FREE: APRIL | FREE, EXCEPT 1, 2, 3, 15, 20, 25, 28 | WHICH DAY?",
     {"state": "COLLECTING", "intent": "check", "slots": SL("april"), "missing": ["day"], "tentative": {}, "month_info": {"month": "april", "booked_days": [1, 2, 3, 15, 20, 25, 28], "full_days": []}},
     [U("I'd like to book a call."), A("Which month?"), U("April."), A("Which day?"), U("I don't know when is it free"), A("Okay, let me check. The 1st, 2nd, 3rd, 15th, 20th, 25th, 28th are booked."), U("pick one randomly")],
     "Okay, let me pick one randomly for you. Okay, the 16th is available. Okay, let me check again. The 16th is available. Okay, let me pick one randomly for you. Okay, the 16th", "mid_turn",
     {"since_user_s": 11.0, "since_omni_s": None, "omni_speaking": True, "turn_s": 10.0}, "", {"status": "stuck", "kind": "repeating"}),
    ("TURNO APERTO a 10 s: legge la riga dello schermo una volta e chiede il giorno -> ok", "FREE: APRIL | FREE, EXCEPT 1, 2, 3, 15, 20, 25, 28 | WHICH DAY?",
     {"state": "COLLECTING", "intent": "check", "slots": SL("april"), "missing": ["day"], "tentative": {}, "month_info": {"month": "april", "booked_days": [1, 2, 3, 15, 20, 25, 28], "full_days": []}},
     [U("I'd like to book a call."), A("Which month?"), U("April."), A("Which day?"), U("I don't know when is it free")],
     "Okay, let me check. April is free except the 1st, 2nd, 3rd, 15th, 20th, 25th and 28th. Which day would you like?", "mid_turn",
     {"since_user_s": 11.0, "since_omni_s": None, "omni_speaking": True, "turn_s": 10.0}, "", {"status": "ok"}),
    ("TURNO APERTO a 10 s: risposta normale di poche frasi -> ok", "BOOK: APRIL 15 | WHAT TIME?", COLL_15,
     BASE + [A("How about April 15th? Does that work?"), U("Uh, yes.")],
     "Great, April 15th it is. What time would you like to come in? We have slots in the morning and in the afternoon.", "mid_turn",
     {"since_user_s": 11.0, "since_omni_s": None, "omni_speaking": True, "turn_s": 10.0}, "", {"status": "ok"}),
    ("readback del cliente (non proposta) -> month/day/time, ok", "APRIL 15, 3 PM | FREE | SHALL I BOOK IT?", {"state": "CONFIRM", "intent": "book", "status": "pending", "slots": SL("april", "15", "15:00"), "missing": [], "tentative": {}},
     BASE + [A("Which day?"), U("The 15th at 3 pm.")],
     "So, April 15th at 3 pm. Shall I book it?", "turn_end", {"since_user_s": 1.2, "since_omni_s": 0, "omni_speaking": False}, "",
     {"status": "ok", "day": "15", "time": "15:00"}),
]
EXTRACT = [  # (nome, fsm, conversazione, funzione attesa, argomenti attesi)
    ("'Please cancel the booking of March 20 at 15' -> set intent unbook march 20 15:00 (CANCELING)", {"state": "IDLE", "intent": None, "slots": SL(), "missing": [], "tentative": {}},
     [U("Please cancel the booking of March 20 at 15.")], "set", {"intent": "unbook", "month": "march", "day": "20", "time": "15:00"}),
    ("'never mind' in raccolta -> cancel (rinuncia), non unbook", COLL_APR, BASE[:-1] + [U("Never mind, forget it.")], "cancel", {}),
    ("'remove my appointment on April 15' dopo BOOKED -> unbook", {"state": "DONE", "intent": "book", "status": "confirmed", "slots": SL("april", "15", "15:00"), "missing": [], "tentative": {}},
     [A("Booked, April 15th at 3 PM. Anything else?"), U("Actually, remove my appointment on April 15 at 3 pm.")], "set", {"intent": "unbook", "day": "15"}),
    ("si' alla proposta -> yes", COLL_PROP, BASE + [A("How about April 15th? Does that work?"), U("Uh, yes.")], "yes", {}),
    ("'now confirm the booking' alla proposta -> yes", COLL_PROP, BASE + [A("How about April 15th? Does that work?"), U("Now confirm the booking.")], "yes", {}),
    ("'no, the 17th' alla proposta -> set day 17", COLL_PROP, BASE + [A("How about April 15th? Does that work?"), U("No, the 17th.")], "set", {"day": "17"}),
    ("'pick one randomly' -> set day pick", COLL_APR, BASE, "set", {"day": "pick"}),
    ("'I don't mind, you choose' -> set day pick", COLL_APR, BASE[:-1] + [U("I don't mind, you choose.")], "set", {"day": "pick"}),
    ("'you pick the time, whatever is free' -> set time pick", COLL_15, BASE + [A("How about April 15th?"), U("Yes."), A("What time would you like?"), U("You pick the time, whatever is free.")], "set", {"time": "pick"}),
    ("'I don't know, when is it free?' -> set check (come prima, non pick)", COLL_APR, BASE[:-1] + [U("I don't know, when is it free?")], "set", {"intent": "check"}),
]

ok = 0; n = 0; ts = []
print("σ:")
for name, screen, fsm, tr, text, reason, timing, prev, exp in SIGMA:
    d, dt = post("/sigma", {"operator_text": text, "fsm": fsm, "transcript": tr, "screen": screen, "reason": reason, "timing": timing, "previous_help": prev}); ts.append(dt)
    a = (d.get("tool_calls") or [{}])[0].get("arguments") or {}
    fails = []
    for k, v in exp.items():
        if k == "help_has":
            if v not in (a.get("help") or "").lower(): fails.append(f"help={a.get('help')!r}")
        elif str(a.get(k) or "").lower().lstrip("0") != str(v).lower().lstrip("0"): fails.append(f"{k}={a.get(k)!r}")
    n += 1; ok += not fails
    print(f"  {'PASS' if not fails else 'FAIL'}  {name} ({dt:.1f} s)" + ("" if not fails else "   <- " + ", ".join(fails)))
    if V or fails: print(f"        -> {json.dumps(a)}")
print("estrattore:")
for name, fsm, tr, fn, args in EXTRACT:
    d, dt = post("/decide", {"fsm": fsm, "transcript": tr, "context": "state"}); ts.append(dt)
    c = (d.get("tool_calls") or [{}])[0]; got = c.get("name"); ga = c.get("arguments") or {}
    fails = ([] if got == fn else [f"name={got}"]) + [f"{k}={ga.get(k)!r}" for k, v in args.items() if str(ga.get(k) or "").lstrip("0") != v]
    n += 1; ok += not fails
    print(f"  {'PASS' if not fails else 'FAIL'}  {name} ({dt:.1f} s)" + ("" if not fails else "   <- " + ", ".join(fails)))
    if V or fails: print(f"        -> {got}{json.dumps(ga)}  raw={str(d.get('raw'))[:120]!r}")
print(f"\n{ok}/{n} passati · media {sum(ts) / len(ts):.2f} s")
sys.exit(0 if ok == n else 1)
