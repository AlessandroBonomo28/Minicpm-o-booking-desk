#!/usr/bin/env python3
"""Extractor regression: sentence + state -> expected call. Measures the separate model's robustness instead of
guessing it. Runs against the live extractor, through the gateway proxy (or directly with --direct).

  python3 tools/tool_agent_eval.py            # all cases, prints pass/fail and the percentage
  python3 tools/tool_agent_eval.py -v         # passed cases too

Each case: (FSM state, sentence, expected) where expected = None (no action) or (intent, {fields}); the listed fields
must appear with that value (month/day compared normalised) and fields absent from 'expected' must NOT appear when
listed as forbidden. The cases come from the live tests of 3-4 September 2026.
"""
import argparse, json, sys, time, urllib.request, ssl

IDLE = {"state": "IDLE"}
def COLL(intent, month="", day="", time_="", missing=None):
    slots = {"month": month, "day": day, "time": time_}
    if missing is None:
        req = ["month", "day"] + (["time"] if intent == "book" else [])
        missing = [k for k in req if not slots[k]]
    return {"state": "COLLECTING", "intent": intent, "slots": slots, "missing": missing}
RES = {"state": "DONE", "intent": "book", "status": "confirmed", "slots": {"month": "may", "day": "25", "time": "15:00"}}
TAKEN = {"state": "DONE", "intent": "book", "status": "taken", "slots": {"month": "march", "day": "28", "time": "15:00"}}

# (stato, frase, atteso, vietati)
CASES = [
    # intento
    (IDLE, "Hello, how are you?", None, ()),
    (IDLE, "How are you today?", None, ()),
    (IDLE, "I would like to book a visit.", ("book", {}), ("month", "day", "time")),
    (IDLE, "I want to book a desk.", ("book", {}), ("month", "day", "time")),
    (IDLE, "Can I book an appointment please?", ("book", {}), ("month", "day", "time")),
    (IDLE, "Is March 31st at 3 pm available?", ("check", {"month": "march", "day": "31", "time": "15:00"}), ()),
    (IDLE, "Do you have anything on June 1st?", ("check", {"month": "june", "day": "1"}), ("time",)),
    (IDLE, "Is April 2nd free?", ("check", {"month": "april", "day": "2"}), ("time",)),
    (IDLE, "I wanted to know if there are any appointments on March.", ("check", {"month": "march"}), ("day", "time")),
    (IDLE, "Book me April 2nd at 3 pm.", ("book", {"month": "april", "day": "2", "time": "15:00"}), ()),
    (IDLE, "I need an appointment on May 5th.", ("book", {"month": "may", "day": "5"}), ("time",)),
    # mese da solo dentro una frase
    (IDLE, "So, I want to book for May.", ("book", {"month": "may"}), ("day", "time")),
    (IDLE, "No, I want a book for May.", ("book", {"month": "may"}), ("day", "time")),
    (IDLE, "Okay, and I want to book for April.", ("book", {"month": "april"}), ("day", "time")),
    (IDLE, "I want to book in June.", ("book", {"month": "june"}), ("day", "time")),
    (IDLE, "Book me something in May.", ("book", {"month": "may"}), ("day", "time")),
    # date parlate
    (COLL("book"), "to book for the second of April.", ("book", {"month": "april", "day": "2"}), ("time",)),
    (COLL("book"), "The second of April.", ("book", {"month": "april", "day": "2"}), ("time",)),
    (COLL("book"), "March thirty-first at half past two.", ("book", {"month": "march", "day": "31", "time": "14:30|02:30|2:30"}), ()),
    (COLL("book"), "The twenty-first of May, please.", ("book", {"month": "may", "day": "21"}), ("time",)),
    (COLL("book"), "June 1st.", ("book", {"month": "june", "day": "1"}), ("time",)),
    (COLL("book"), "December 1st", ("book", {"month": "december", "day": "1"}), ("time",)),
    (COLL("book"), "Tomorrow at 9.", ("book", {"time": "09:00|9"}), ("month", "day")),
    # giorno da solo: con e SENZA mese nello stato (mai inventare il mese)
    (COLL("book", month="april"), "The 2nd.", ("book", {"day": "2"}), ("time",)),
    (COLL("book", month="april"), "The second.", ("book", {"day": "2"}), ("time",)),
    (COLL("book", month="may"), "25", ("book", {"day": "25"}), ("time",)),
    (COLL("book", month="may"), "third", ("book", {"day": "3"}), ("time",)),
    (COLL("book", month="april"), "The twentieth.", ("book", {"day": "20"}), ("time",)),
    (COLL("check"), "For the second.", ("check", {"day": "2"}), ("month", "time")),
    (COLL("check", month="march"), "30", ("check", {"day": "30"}), ("time",)),
    (COLL("check", month="march"), "The 30th.", ("check", {"day": "30"}), ("time",)),
    (COLL("book", month="april"), "No, the 3rd.", ("book", {"day": "3"}), ("time",)),
    # ora da sola (manca l'ora)
    (COLL("book", month="april", day="20"), "15", ("book", {"time": "15:00|15"}), ()),
    (COLL("book", month="april", day="20"), "15. .", ("book", {"time": "15:00|15"}), ()),
    (COLL("book", month="april", day="20"), "Nine.", ("book", {"time": "09:00|9|nine"}), ()),
    (COLL("book", month="april", day="20"), "At nine.", ("book", {"time": "09:00|9"}), ()),
    (COLL("book", month="april", day="20"), "nine thirty", ("book", {"time": "09:30|9:30"}), ()),
    (COLL("book", month="april", day="20"), "3 pm", ("book", {"time": "15:00"}), ()),
    (COLL("book", month="april", day="20"), "Half past ten.", ("book", {"time": "10:30"}), ()),
    (COLL("book", month="april", day="20"), "9pm, 9pm.", ("book", {"time": "21:00"}), ()),
    (COLL("book", month="may", day="3"), "Aah, little...? 18?", ("book", {"time": "18:00|18"}), ()),
    (COLL("check", month="march", day="30"), "At 3 pm.", ("check", {"time": "15:00"}), ()),
    # ordine sparso: ora prima, poi giorno, poi mese
    (COLL("book"), "At 3 pm.", ("book", {"time": "15:00"}), ("month", "day")),
    (COLL("book", time_="15:00"), "The 2nd.", ("book", {"day": "2"}), ("month",)),
    (COLL("book", day="2", time_="15:00"), "April.", ("book", {"month": "april"}), ()),
    # dopo un esito: niente copie
    (RES, "Okay, thank you.", None, ()),
    (RES, "Thank you, bye!", None, ()),
    (RES, "Okay, I don't need you anymore.", None, ()),
    (RES, "Okay, thank you. And is it free?", ("check", {}), ("month", "day", "time")),
    (RES, "Is March 30 at 3 pm free?", ("check", {"month": "march", "day": "30", "time": "15:00"}), ()),
    # annulla
    (COLL("book"), "Actually, never mind, cancel that.", ("cancel", {}), ()),
    (COLL("book", month="may", day="25"), "Never mind, cancel that.", ("cancel", {}), ()),
    # dopo uno slot occupato (run del 06/09): "next free slot" e' una verifica, mai un'ora inventata; "at 16" e' solo l'ora
    (TAKEN, "What's the next free slot?", ("check", {}), ("month", "day", "time", "!none")),
    (TAKEN, "When is free?", ("check", {}), ("month", "day", "time", "!none")),
    (TAKEN, "at 16", ("check", {"time": "16:00|16"}), ("month", "day")),
    # rumore
    (IDLE, "Mm-hmm.", None, ()),
    (IDLE, "pizza", None, ()),
    (COLL("book"), "Um...", None, ()),
]

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]


import re as _re
_g = open(__file__.rsplit("/", 2)[0] + "/gateway.py").read(); _ns = {"re": _re}
exec(_g[_g.index("_MONTHS = ["):_g.index("def _hud_time_span")], _ns)   # normalizzatori del gateway (data, giorno, ora)


def norm(k, v):
    """Confronto sui valori NORMALIZZATI come li vede la FSM: l'estrattore copia le parole, il gateway le converte."""
    v = str(v).strip().lower()
    if k == "month":
        return _ns["_hud_norm_date"](v)
    if k == "day":
        d = _ns["_hud_words_to_digits"](_re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", v)).replace("the ", "").strip()
        return d.lstrip("0")
    return _ns["_hud_norm_time"](v)


_DIM = {"january": 31, "february": 28, "march": 31, "april": 30, "may": 31, "june": 30, "july": 31, "august": 31, "september": 30, "october": 31, "november": 30, "december": 31}


def canon(st, got):
    """Chiamata dell'estrattore -> (intento, campi) come la applicherebbe la FSM, per confrontarla con le attese."""
    if got is None:
        return None
    name, a = got[0], dict(got[1]); state = st.get("state"); ref = st.get("slots") or {}
    a = {k: v for k, v in a.items() if v}
    if name in ("book", "check", "check_availability"):
        a["intent"] = "book" if name == "book" else "check"; name = "set"
    if name == "cancel":
        return None if (state == "CONFIRM" and st.get("intent") == "check") else ("cancel", {})
    if name == "no":
        return ("cancel", {}) if (state == "CONFIRM" and st.get("intent") == "book") else None
    if name == "yes" and any(a.get(k) for k in ("month", "day", "time")):
        name = "set"
    if name == "yes":
        if state != "CONFIRM": return None
        f = {"month": ref.get("month"), "day": ref.get("day")}
        if ref.get("time") and ref.get("time") != "all-day": f["time"] = ref["time"]
        return ("book", f)
    if name != "set":
        return None
    intent = a.pop("intent", None)
    if not a and intent not in ("book", "check"):
        return None
    if state == "COLLECTING":
        return (intent if intent in ("book", "check") else st.get("intent"), a)
    if state == "CONFIRM":
        f = {"month": ref.get("month"), "day": ref.get("day")}
        if ref.get("time") and ref.get("time") != "all-day": f["time"] = ref["time"]
        f.update(a)
        return (intent if intent in ("book", "check") else (st.get("intent") or "check"), f)
    return (intent if intent in ("book", "check") else "check", a)


def run(url, verbose):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    ok = 0; fails = []; t_all = []
    for st, text, exp, forbidden in CASES:
        body = json.dumps({"fsm": st, "transcript": [{"role": "user", "text": text}]}).encode()
        t0 = time.time()
        r = urllib.request.urlopen(urllib.request.Request(url, data=body, headers={"content-type": "application/json"}), timeout=60, context=ctx)
        d = json.loads(r.read()); t_all.append(time.time() - t0)
        calls = d.get("tool_calls") or []
        got = (calls[0]["name"], dict(calls[0].get("arguments") or {})) if calls else None
        op = got
        got = canon(st, got)
        if got and got[1].get("day") and got[1].get("time"):
            # come la FSM: un solo numero nella battuta non e' insieme giorno e ora
            nums = _re.findall(r"\d+", _ns["_hud_words_to_digits"](_re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", _re.sub(r"[^\w\s-]", " ", text.lower()))))
            if len(nums) == 1:
                if (st.get("slots") or {}).get("day"): got[1].pop("day")
                else: got[1].pop("time")
        if got and got[1].get("month"):
            # come la FSM: un numero/ordinale nel campo mese e' la risposta alla domanda corrente (giorno, poi ora)
            mv = norm("day", got[1]["month"])
            if mv.isdigit():
                slots = st.get("slots") or {}
                if got[1].get("day") and norm("day", got[1]["day"]) == mv: got[1].pop("month")   # stesso numero gia' nel giorno
                elif not got[1].get("day") and not slots.get("day") and 1 <= int(mv) <= 31: got[1]["day"] = mv; got[1].pop("month")
                elif not got[1].get("time") and not slots.get("time"): got[1]["time"] = mv; got[1].pop("month")
                else: got[1].pop("month")
        passed = False
        if exp is None:
            passed = got is None
        elif exp == ("check", {}) and got is None:
            passed = "!none" not in forbidden   # "is it free?" senza riferimento: nessuna chiamata vale quanto un check vuoto; "!none" la esige
        elif got is not None and (got[0] == exp[0] or (st.get("state") == "COLLECTING" and exp[0] in ("book", "check") and got[0] in ("book", "check"))):
            # in COLLECTING l'intento e' bloccato dalla FSM: book/check sono equivalenti per contratto
            passed = True
            for k, v in exp[1].items():
                gv = got[1].get(k)
                if gv is None or norm(k, gv) not in [norm(k, x) for x in str(v).split("|")]:
                    passed = False
            for k in forbidden:
                if k != "!none" and got[1].get(k):
                    passed = False
        tag = "PASS" if passed else "FAIL"
        if passed: ok += 1
        else: fails.append((st.get("state"), text, exp, got))
        if verbose or not passed:
            print(f"  {tag}  [{st.get('state')}{' ' + st.get('intent', '') if st.get('intent') else ''}] {text!r:45} atteso={exp} ottenuto={got} op={op}")
    n = len(CASES)
    print(f"\n{ok}/{n} passati ({100 * ok / n:.0f}%) · LLM medio {sum(t_all) / len(t_all):.2f} s · falliti {len(fails)}")
    return 0 if ok == n else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--direct", action="store_true", help="chiama l'estrattore su :22700 invece del proxy del gateway")
    a = ap.parse_args()
    sys.exit(run("http://127.0.0.1:22700/decide" if a.direct else "https://127.0.0.1:8006/api/tool_agent/decide", a.verbose))
