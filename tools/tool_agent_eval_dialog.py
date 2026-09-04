#!/usr/bin/env python3
"""Esperimento (05/09): l'estrattore con CONTESTO di dialogo (ultime N righe, operatore compreso) risolve
'yes' / 'that day' / 'the next day' senza tornare a copiare campi dai turni precedenti?
Confronta context=0 (contratto attuale) e context=3 sugli stessi casi.

  python3 tools/tool_agent_eval_dialog.py            # entrambe le modalita'
  python3 tools/tool_agent_eval_dialog.py -v
"""
import argparse, json, sys, time, urllib.request, ssl
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from tool_agent_eval import IDLE, COLL, norm, canon

RES_CHECK = lambda m, d: {"state": "CONFIRM", "intent": "check", "status": "available", "slots": {"month": m, "day": d, "time": "all-day"}}
RES_BOOK = lambda m, d, t: {"state": "DONE", "intent": "book", "status": "confirmed", "slots": {"month": m, "day": d, "time": t}}
A = lambda x: {"role": "assistant", "text": x}
U = lambda x: {"role": "user", "text": x}

# (stato, transcript, atteso, vietati)  — atteso: None | (intent, {campi})
CASES = [
    # --- riferimenti da risolvere (servono le righe precedenti)
    (RES_CHECK("april", "4"), [U("I want to check April 4th."), A("April 4th is available all day. Would you like to book?"), U("Yes.")],
     ("book", {"month": "april", "day": "4"}), ("time",)),
    (RES_CHECK("march", "13"), [A("March 13th is available all day. Would you like to book?"), U("Yes")],
     ("book", {"month": "march", "day": "13"}), ("time",)),
    (RES_CHECK("may", "9"), [A("May 9th is available all day. Would you like to book?"), U("Sure, book it.")],
     ("book", {"month": "may", "day": "9"}), ("time",)),
    (RES_CHECK("march", "13"), [A("March 13th is available all day. Would you like to book?"), U("Book for that day.")],
     ("book", {"month": "march", "day": "13"}), ("time",)),
    (RES_CHECK("march", "21"), [U("How about March 21?"), A("The same thing, there's nothing booked on it."), U("Okay, I want to book for that day.")],
     ("book", {"month": "march", "day": "21"}), ("time",)),
    (RES_BOOK("march", "30", "15:00"), [A("Your booking is confirmed for March 30th at 15:00."), U("Yeah, how about the next day?")],
     ("check", {"month": "march", "day": "31"}), ()),
    (RES_CHECK("april", "4"), [A("April 4th is available all day. Would you like to book?"), U("Yes, at 3 pm.")],
     ("book", {"month": "april", "day": "4", "time": "15:00"}), ()),
    (RES_CHECK("april", "4"), [A("April 4th is available all day. Would you like to book?"), U("And the day after?")],
     ("check", {"month": "april", "day": "5"}), ()),
    # in CONFIRM la FSM eredita il mese dell'offerta se non se ne dice un altro: basta il giorno
    (RES_CHECK("april", "4"), [A("April 4th is available all day. Would you like to book?"), U("No, the 6th.")],
     ("check", {"day": "6"}), ()),
    # --- prenotazione in attesa di conferma (CONFIRM con intent book)
    ({"state": "CONFIRM", "intent": "book", "status": "pending", "slots": {"month": "march", "day": "2", "time": "15:00"}},
     [A("Booking for March 2nd at 15:00, shall I confirm?"), U("Yes.")], ("book", {"month": "march", "day": "2", "time": "15:00"}), ()),
    ({"state": "CONFIRM", "intent": "book", "status": "pending", "slots": {"month": "march", "day": "2", "time": "15:00"}},
     [A("Booking for March 2nd at 15:00, shall I confirm?"), U("Yes, go ahead.")], ("book", {"month": "march", "day": "2", "time": "15:00"}), ()),
    ({"state": "CONFIRM", "intent": "book", "status": "pending", "slots": {"month": "march", "day": "2", "time": "15:00"}},
     [A("Booking for March 2nd at 15:00, shall I confirm?"), U("At 5 pm instead.")], ("book", {"time": "17:00"}), ("day",)),
    ({"state": "CONFIRM", "intent": "book", "status": "pending", "slots": {"month": "march", "day": "2", "time": "15:00"}},
     [A("Booking for March 2nd at 15:00, shall I confirm?"), U("No, never mind.")], ("cancel", {}), ()),
    # --- rifiuto dell'offerta
    (RES_CHECK("april", "4"), [A("April 4th is available all day. Would you like to book?"), U("No, thank you.")], None, ()),
    (RES_CHECK("april", "4"), [A("April 4th is available all day. Would you like to book?"), U("Not now, thanks.")], None, ()),
    # --- casi di copia gia' pagati: NON devono tornare
    (RES_BOOK("april", "2", "15:00"), [A("Your booking is confirmed for April 2nd at 15:00. Is there anything else?"), U("Okay, thank you.")], None, ()),
    (RES_BOOK("may", "25", "15:00"), [U("on May."), U("25"), U("15"), A("Your booking is confirmed for May 25th at 15:00."), U("Okay, thank you. And is it free?")],
     ("check", {}), ("month", "day", "time")),
    (IDLE, [A("We have a slot on May 5th at 9."), U("Hmm, let me think.")], None, ()),
    (IDLE, [A("Hi there! How can I help?"), U("How are you today?")], None, ()),
    (COLL("book", month="april"), [A("Which day in April would you like?"), U("The 2nd.")], ("book", {"day": "2"}), ("time",)),
    (COLL("book", month="april", day="20"), [A("So time wise, how about nine thirty?"), U("No, at three pm.")], ("book", {"time": "15:00"}), ()),
    (COLL("book", month="april", day="20"), [A("So time wise, how about nine thirty?"), U("Hmm, let me check my calendar.")], None, ()),
    (RES_BOOK("march", "20", "18:00"), [A("Your booking is confirmed for March 20th at 18:00."), U("I want to check for April.")],
     ("check", {"month": "april"}), ("day", "time")),
    (RES_BOOK("march", "20", "18:00"), [A("Your booking is confirmed for March 20th at 18:00. Anything else?"), U("Yes.")], None, ()),
]


def run(url, context, verbose):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    ok = 0; t_all = []
    for st, tr, exp, forbidden in CASES:
        body = json.dumps({"fsm": st, "transcript": tr, "context": context}).encode()
        t0 = time.time()
        r = urllib.request.urlopen(urllib.request.Request(url, data=body, headers={"content-type": "application/json"}), timeout=60, context=ctx)
        d = json.loads(r.read()); t_all.append(time.time() - t0)
        calls = d.get("tool_calls") or []
        op = (calls[0]["name"], calls[0].get("arguments") or {}) if calls else None
        got = canon(st, op)
        if exp is None:
            passed = got is None
        elif exp == ("check", {}) and got is None:
            passed = True
        else:
            passed = got is not None and (got[0] == exp[0] or (st.get("state") == "COLLECTING" and got[0] in ("book", "check")))
            if passed:
                for k, v in exp[1].items():
                    gv = got[1].get(k)
                    if gv is None or norm(k, gv) not in [norm(k, x) for x in str(v).split("|")]:
                        passed = False
                for k in forbidden:
                    if got[1].get(k):
                        passed = False
        ok += passed
        if verbose or not passed:
            print(f"  {'PASS' if passed else 'FAIL'}  {tr[-1]['text']!r:40} (prima: {tr[-2]['text'][:45]!r}) atteso={exp} ottenuto={got} op={op}")
    n = len(CASES)
    print(f"  => context={context}: {ok}/{n} ({100 * ok / n:.0f}%) · LLM medio {sum(t_all) / len(t_all):.2f} s\n")
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    url = "https://127.0.0.1:8006/api/tool_agent/decide"
    print("== CONTRATTO ATTUALE: stato (CONFIRM porta l'offerta) + frase, nessuna riga di dialogo"); run(url, 0, a.verbose)
    print("== confronto: in piu' le ultime 3 righe di dialogo (operatore compreso)"); run(url, 3, a.verbose)
