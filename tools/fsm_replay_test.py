#!/usr/bin/env python3
"""Local replay of the booking state machine (no LLM, no services): the event sequence of session sess_41c874e48161 with the
proposal rule (an operator's proposal verified free on the DB enters as a tentative "proposal" value and the customer's yes
consolidates it) plus the regression cases added since. The DB is written to a temporary copy. python3 tools/fsm_replay_test.py [-v]"""
import os, sys, tempfile, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import gateway as g   # noqa: E402  (importa la app; il DB viene subito reindirizzato)

g._HUD_DB_PATH = os.path.join(tempfile.mkdtemp(prefix="hud_replay_"), "hud_db.json")
VERBOSE = "-v" in sys.argv
FAILS = []


def seed():
    g._HUD_DB["slots"].clear(); g._HUD_DB["log"].clear()
    for d, t in [("april 1", "all-day"), ("april 2", "all-day"), ("april 3", "all-day"), ("april 20", "15:00"), ("april 20", "18:00"),
                 ("april 20", "19:00"), ("april 20", "21:00"), ("april 25", "all-day"), ("april 28", "all-day")]:
        g._HUD_DB["slots"][f"{d} {t}"] = {"date": d, "time": t, "status": "booked", "name": ""}
    g._hud_fsm_reset()


def ev(name, text="", **args):
    fsm, changed = g._hud_fsm_apply([{"name": name, "arguments": args}], text, "auto", "test")
    if VERBOSE:
        sl = fsm["slots"]; print(f"   {name}{json.dumps(args)} -> {fsm['state']} {fsm.get('intent')} {sl.get('month')} {sl.get('day')} {sl.get('time')} "
                                 f"missing={fsm.get('missing')} tentative={fsm.get('tentative')} status={fsm.get('status')} changed={changed}")
    return fsm, changed


def sigma(**args):
    """Come /api/hud_fsm/omni_turn: applica il verdetto di σ (fonte sigma) e poi il semaforo."""
    fsm, changed = ev("sigma", **args)
    level, hint = g._hud_supervise(fsm, "", args)
    return fsm, changed, level, hint


def check(name, cond, got=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'' if cond else '   <- ' + str(got)}")
    if not cond: FAILS.append(name)


# --- 1. la run 41c874e48161 con la regola nuova -------------------------------------------------------------
seed()
ev("set", "I'd like to book a call", intent="book")
ev("set", "in April", month="april")
ev("set", "pick one randomly", day="any")
f, ch, lvl, hint = sigma(claim="slot_free", claim_day="15", month="april", day="15")   # omni: "How about April 15th? Does that work?"
check("proposta libera -> giorno 15 tentativo 'proposal'", f["slots"]["day"] == "15" and f["tentative"].get("day") == "proposal" and ch, f)
check("schermo: manca solo l'ora", f["missing"] == ["time"], f["missing"])
check("semaforo verde sulla proposta", lvl == "green", (lvl, hint))
f, ch, lvl, hint = sigma(claim="booking_confirmed", claim_day="15")                   # omni: "Great! I'll go ahead and book April 15th"
check("annuncio di prenotazione -> rosso NOTHING BOOKED YET", lvl == "red" and "nothing is booked yet" in hint.lower() and f["tentative"].get("day") == "proposal", (lvl, hint))
f, ch = ev("yes", "Uh, yes.")                                                        # il cliente accetta la proposta
check("yes consolida il giorno (COLLECTING, manca l'ora)", ch and f["state"] == "COLLECTING" and f["slots"]["day"] == "15" and not f["tentative"] and f["missing"] == ["time"], f)
f, ch = ev("set", "at 15", time="15:00")
check("ora -> CONFIRM pending (SHALL I BOOK IT?)", f["state"] == "CONFIRM" and f["status"] == "pending" and f["slots"]["time"] == "15:00", f)
f, ch = ev("yes", "Yes.")
check("yes -> DONE booked april 15 15:00", f["state"] == "DONE" and f["status"] == "confirmed" and g._HUD_DB["slots"].get("april 15 15:00", {}).get("status") == "booked", f)

# --- 2. la proposta NON entra se il giorno e' pieno, se il cliente ha gia' un giorno, fuori dalla raccolta --------------
seed(); ev("set", intent="book", month="april")
f, ch, *_ = sigma(claim="slot_free", claim_day="1")
check("proposta di un giorno tutto occupato (1) -> ignorata", not ch and not f["slots"]["day"], f)
f, ch, *_ = sigma(claim="slot_free", claim_day="20")
check("proposta del 20 (parzialmente occupato) -> entra come tentativo", ch and f["slots"]["day"] == "20" and f["tentative"].get("day") == "proposal", f)
seed(); ev("set", intent="book", month="april", day="9")
f, ch, *_ = sigma(claim="slot_free", claim_day="15")
check("il cliente ha gia' detto il 9: la proposta del 15 non sovrascrive", not ch and f["slots"]["day"] == "9", f)
seed(); ev("set", intent="check", month="april", day="9")   # CONFIRM (available)
f, ch, *_ = sigma(claim="slot_free", claim_day="15")
check("fuori dalla raccolta (CONFIRM) la proposta non entra", not ch and f["state"] == "CONFIRM", f)
seed(); ev("set", intent="book", month="april")
f, ch, *_ = sigma(claim="slot_taken", claim_day="15")
check("un claim slot_taken non porta valori", not ch, f)
f, ch, *_ = sigma(claim="slot_free", claim_day="15", month="april", day="17")   # readback incoerente col claim: vince il claim verificato
check("readback dentro un claim: ignorato, entra solo il giorno verificato", f["slots"]["day"] == "15", f)

# --- 3. no scarta la proposta; un valore del cliente la supera ---------------------------------------------------
seed(); ev("set", intent="book", month="april"); sigma(claim="slot_free", claim_day="15")
f, ch = ev("no", "No.")
check("no -> proposta scartata, si torna a WHICH DAY?", ch and not f["slots"]["day"] and not f["tentative"] and f["missing"] == ["day", "time"], f)
seed(); ev("set", intent="book", month="april"); sigma(claim="slot_free", claim_day="15")
f, ch = ev("set", "the 17th", day="17")
check("il cliente dice il 17: vince il cliente, niente tentativo", f["slots"]["day"] == "17" and not f["tentative"], f)

# --- 4. proposta di un'ORA (giorno noto): verificata sul DB; se completa la prenotazione -> CONFIRM diretta (un solo si') -------
seed(); ev("set", intent="book", month="april", day="20")
f, ch, lvl, hint = sigma(claim="slot_free", claim_time="15:00")                     # 15:00 del 20 e' occupata
check("proposta di un'ora occupata -> non entra, rosso 3 PM IS TAKEN", not ch and not f["slots"]["time"] and lvl == "red", (lvl, hint, f["slots"]))
f, ch, lvl, hint = sigma(claim="slot_free", claim_time="16:00")
check("proposta di un'ora libera che completa -> CONFIRM pending con il marchio, verde", ch and f["state"] == "CONFIRM" and f["status"] == "pending" and f["slots"]["time"] == "16:00" and f["tentative"] == {"time": "proposal"} and lvl == "green", (lvl, f))
f, ch = ev("no", "no")
check("no all'offerta -> via l'ora proposta, si torna a WHAT TIME? (giorno del cliente conservato)", ch and f["state"] == "COLLECTING" and f["slots"]["day"] == "20" and not f["slots"]["time"] and f["missing"] == ["time"] and not f["tentative"], f)
f, ch, *_ = sigma(claim="slot_free", claim_time="17:00")
f, ch = ev("yes", "yes")
check("si' all'offerta -> BOOKED april 20 17:00 (un solo si')", f["state"] == "DONE" and f["status"] == "confirmed" and g._HUD_DB["slots"].get("april 20 17:00", {}).get("status") == "booked", f)
seed(); ev("set", intent="book", month="april", day="20"); sigma(claim="slot_free", claim_time="16:00")
f, ch = ev("set", "no, at 5 pm", time="17:00")
check("correzione del cliente sull'offerta -> CONFIRM 17:00, marchi via", f["state"] == "CONFIRM" and f["slots"]["time"] == "17:00" and not f["tentative"], f)
f, ch = ev("no", "no")
check("no su una conferma coi valori del cliente -> come prima: richiesta annullata", f["state"] == "IDLE" and f["note"] == "BOOKING NOT CONFIRMED", f)
seed(); ev("set", intent="book", month="april")
f, ch, *_ = sigma(claim="slot_free", claim_day="15", claim_time="16:00")             # "How about April 15th at 4 pm?"
check("proposta giorno+ora che completa -> CONFIRM pending, entrambi marchiati", f["state"] == "CONFIRM" and f["slots"]["day"] == "15" and f["slots"]["time"] == "16:00" and f["tentative"] == {"day": "proposal", "time": "proposal"}, f)
seed(); ev("set", intent="check", month="april")
f, ch, *_ = sigma(claim="slot_free", claim_day="15", claim_time="16:00")
check("verifica (check): entra il giorno, non l'ora; il record e' completo -> risultato diretto col marchio", f["slots"]["day"] == "15" and f["slots"]["time"] == "all-day" and f["state"] == "CONFIRM" and f["status"] == "available" and f["tentative"] == {"day": "proposal"}, f)
f, ch = ev("no", "no")
check("no al giorno proposto in verifica -> torna la domanda sul mese (FREE, EXCEPT ...)", f["state"] == "COLLECTING" and not f["slots"]["day"] and f.get("month_info"), f)

# --- 5. readback senza claim: come prima (tentativo True) ------------------------------------------------------------
seed(); ev("set", intent="book", month="april")
f, ch, *_ = sigma(month="april", day="12")
check("readback (senza claim) -> tentativo True, IS THAT RIGHT?", f["slots"]["day"] == "12" and f["tentative"].get("day") is True, f)


# --- 6. (revisione 08/09) giorno pieno proposto -> rosso; mese diverso -> rosso; mese mancante -> entra come proposta --------
seed(); ev("set", intent="book", month="april")
f, ch, lvl, hint = sigma(claim="slot_free", claim_day="1")
check("proposta di un giorno pieno -> non entra e ROSSO 'APRIL 1 IS FULL'", not ch and lvl == "red" and "april 1st is full" in hint.lower(), (lvl, hint))
f, ch, lvl, hint = sigma(claim="slot_free", claim_day="1", claim_time="16:00")
check("giorno pieno con un'ora -> non entra, rosso sul giorno", not ch and lvl == "red" and "april 1st is full" in hint.lower(), (lvl, hint))
f, ch, lvl, hint = sigma(claim="slot_free", claim_day="20", claim_time="15:00")     # "How about the 20th at 3 pm?": il 20 e' libero come giorno, le 15 no
check("giorno libero + ora occupata -> entra solo il giorno (proposta), rosso sull'ora", ch and f["slots"]["day"] == "20" and not f["slots"]["time"] and f["tentative"] == {"day": "proposal"} and lvl == "red" and "is taken" in hint.lower(), (lvl, hint, f["slots"]))
seed(); ev("set", intent="book", month="april")
f, ch, lvl, hint = sigma(claim="slot_taken", claim_day="9")
check("'il 9 e' occupato' (libero) -> rosso 'APRIL 9 IS FREE'", not ch and lvl == "red" and "april 9th is actually free" in hint.lower(), (lvl, hint))
f, ch, lvl, hint = sigma(claim="slot_free", claim_day="15", claim_month="may")
check("proposta in un altro mese -> non entra, rosso 'APRIL, NOT MAY'", not ch and not f["slots"]["day"] and lvl == "red" and "i mean april, not may" in hint.lower(), (lvl, hint, f["slots"]))
f, ch, lvl, hint = sigma(claim="slot_free", claim_day="15", claim_month="april")
check("proposta con il mese giusto detto -> entra, verde", ch and f["slots"]["day"] == "15" and lvl == "green", (lvl, hint, f["slots"]))
seed(); ev("set", intent="book")
f, ch, lvl, hint = sigma(claim="slot_free", claim_day="15", claim_month="april")
check("mese mancante: 'How about April 15th?' -> mese e giorno entrano come proposta", ch and f["slots"]["month"] == "april" and f["slots"]["day"] == "15" and f["tentative"] == {"month": "proposal", "day": "proposal"} and f["missing"] == ["time"], f)
f, ch = ev("yes", "yes")
check("yes -> mese e giorno solidi, manca l'ora", f["slots"]["month"] == "april" and f["slots"]["day"] == "15" and not f["tentative"] and f["missing"] == ["time"], f)
seed(); ev("set", intent="book")
f, ch, lvl, hint = sigma(claim="slot_free", claim_day="15")
check("mese mancante e proposta senza mese -> non entra", not ch and not f["slots"]["day"], f)

# --- 7. (revisione) una proposta sostituisce solo una proposta; 'any' e 'no' puliscono; sì arrivato prima del verdetto -------
seed(); ev("set", intent="book", month="april"); sigma(claim="slot_free", claim_day="15")
f, ch, lvl, hint = sigma(claim="slot_free", claim_day="17")                         # "sorry... how about the 17th?"
check("seconda proposta (17) sostituisce la prima (15): vale l'ultima sentita", ch and f["slots"]["day"] == "17" and f["tentative"].get("day") == "proposal" and lvl == "green", (lvl, f))
f, ch = ev("yes", "yes")
check("yes -> il 17 solido", f["slots"]["day"] == "17" and not f["tentative"], f)
seed(); ev("set", intent="book", month="april"); sigma(claim="slot_free", claim_day="15")
f, ch = ev("set", "any day is fine", day="any")
check("'any day' dopo una proposta -> giorno vuoto E tentativo via (schermo WHICH DAY?)", f["slots"]["day"] == "" and not f["tentative"] and f["missing"] == ["day", "time"], f)
seed(); ev("set", intent="check", month="april", day="any")
check("verifica sul mese: month_info presente", (f := g._HUD_DB["fsm"]).get("month_info") and f["month_info"]["booked_days"] == [1, 2, 3, 20, 25, 28], f.get("month_info"))
sigma(claim="slot_free", claim_day="15")
f, ch = ev("no", "no")
check("no alla proposta in verifica -> torna la riga del mese (FREE, EXCEPT ...)", ch and not f["slots"]["day"] and f.get("month_info") and f["month_info"]["booked_days"] == [1, 2, 3, 20, 25, 28], f.get("month_info"))
seed(); ev("set", intent="book", month="april")
f, ch = ev("yes", "Uh, yes.")                                                        # il si' arriva PRIMA del verdetto di σ (corsa)
check("yes slegato in raccolta: nessun cambiamento, ma ricordato", not ch and f.get("unbound_yes"), f.get("unbound_yes"))
f, ch, lvl, hint = sigma(claim="slot_free", claim_day="15")
check("la proposta arrivata dopo lega il si': giorno 15 solido, manca l'ora", ch and f["slots"]["day"] == "15" and not f["tentative"] and f["missing"] == ["time"] and not f.get("unbound_yes"), f)
seed(); ev("set", intent="book", month="april"); ev("yes", "yes"); ev("set", "the 9th", day="9")
f, ch, *_ = sigma(claim="slot_free", claim_time="16:00")
check("un altro evento del cliente supera il si' slegato: la proposta d'ora resta proposta (CONFIRM col marchio)", f["state"] == "CONFIRM" and f["tentative"] == {"time": "proposal"}, f)


# --- 8. "scegli tu" (08/09, proposta 3): la macchina propone il primo libero; no -> il prossimo; yes -> solido; il cliente vince -----
seed(); ev("set", intent="book", month="april")
f, ch = ev("set", "pick one randomly", day="pick")
check("pick day -> la macchina propone il 4 (primo giorno senza prenotazioni), tentativo proposal, manca l'ora", f["slots"]["day"] == "4" and f["tentative"] == {"day": "proposal"} and f["missing"] == ["time"] and f["pick"] == ["day"], f)
f, ch, lvl, hint = sigma(claim="slot_free", claim_day="4")   # l'omni legge la proposta della macchina
check("l'omni legge la proposta della macchina: nessun cambiamento (niente frame nuovo), verde", not ch and lvl == "green", (ch, lvl, hint))
f, ch = ev("no", "No.")
check("no -> la macchina propone il 5 (il 4 saltato)", ch and f["slots"]["day"] == "5" and f["tentative"] == {"day": "proposal"} and f["pick_skip"] == {"day": ["4"]}, f)
f, ch = ev("yes", "yes")
check("yes -> il 5 solido, delega chiusa, manca l'ora", f["slots"]["day"] == "5" and not f["tentative"] and f["pick"] == [] and f["missing"] == ["time"], f)
f, ch = ev("set", "you pick the time", time="pick")
check("pick time -> 9:00 (prima ora libera) e conferma diretta SHALL I BOOK IT?", f["state"] == "CONFIRM" and f["status"] == "pending" and f["slots"]["time"] == "09:00" and f["tentative"] == {"time": "proposal"}, f)
f, ch = ev("no", "no")
check("no -> 10:00, ancora in conferma", f["state"] == "CONFIRM" and f["slots"]["time"] == "10:00" and f["tentative"] == {"time": "proposal"} and f["pick_skip"]["time"] == ["09:00"], f)
f, ch = ev("yes", "yes")
check("yes -> BOOKED april 5 10:00 (un solo si')", f["state"] == "DONE" and f["status"] == "confirmed" and g._HUD_DB["slots"].get("april 5 10:00", {}).get("status") == "booked", f)
seed(); ev("set", intent="book", month="april", day="20")
f, ch = ev("set", "whatever is free", time="pick")
check("pick time sul 20 (15, 18, 19, 21 occupate) -> 9:00 in conferma", f["slots"]["time"] == "09:00" and f["state"] == "CONFIRM", f)
seed(); ev("set", intent="book")
f, ch = ev("set", "you pick", day="pick")
check("pick day senza mese: delega ricordata, si chiede il mese", f["state"] == "COLLECTING" and f["missing"][0] == "month" and f["pick"] == ["day"] and not f["slots"]["day"], f)
f, ch = ev("set", "April", month="april")
check("arriva il mese -> la macchina propone il 4", f["slots"]["day"] == "4" and f["tentative"] == {"day": "proposal"}, f)
f, ch = ev("set", "the 9th", day="9")
check("il cliente dice il 9: vince, delega chiusa", f["slots"]["day"] == "9" and not f["tentative"] and f["pick"] == [], f)
seed(); ev("set", intent="book", month="april"); ev("set", "pick one", day="pick")
f, ch = ev("set", "the whole month", day="any")
check("'any' dopo pick: delega e proposta via, schermo del mese", f["slots"]["day"] == "" and f["pick"] == [] and not f["tentative"] and f.get("month_info"), f)
seed(); ev("set", intent="check", month="april")
f, ch = ev("set", "pick one", day="pick")
check("pick in verifica -> risultato diretto: APRIL 4, ALL DAY / FREE / WHAT TIME? col marchio", f["state"] == "CONFIRM" and f["intent"] == "check" and f["status"] == "available" and f["slots"]["day"] == "4" and f["tentative"] == {"day": "proposal"}, f)
f, ch = ev("no", "no")
check("no -> il prossimo libero: APRIL 5 / FREE", f["state"] == "CONFIRM" and f["slots"]["day"] == "5" and f["tentative"] == {"day": "proposal"} and f["pick_skip"] == {"day": ["4"]}, f)
f, ch = ev("yes", "yes")
check("yes all'offerta -> prenotazione del 5 in raccolta (manca l'ora), delega chiusa", f["state"] == "COLLECTING" and f["intent"] == "book" and f["slots"]["day"] == "5" and f["pick"] == [] and f["missing"] == ["time"], f)
seed(); ev("set", intent="book", month="april", day="20", time="15:00")   # occupata -> DONE taken
f, ch = ev("set", "you choose", time="pick")
check("dopo TAKEN (DONE) 'scegli tu' = richiesta nuova (bug #2 noto): raccolta con la delega", f["state"] == "COLLECTING" and f["pick"] == ["time"], f)

# --- 5. CANCELING: cancellazione di una prenotazione scritta, con conferma (il si' resta l'unico evento che scrive) ---------------
seed()   # april 20: 15:00, 18:00, 19:00, 21:00 occupate
f, ch = ev("set", "cancel the booking of April 20 at 3 pm", intent="unbook", month="april", day="20", time="15:00")
check("unbook di una prenotazione esistente -> CONFIRM unbook pending_cancel (schermo CANCEL IT?)", ch and f["state"] == "CONFIRM" and f["intent"] == "unbook" and f["status"] == "pending_cancel", (f["state"], f.get("status")))
f, lv, hint = (lambda r: (r[0], r[2], r[3]))(sigma(claim="booking_cancelled", claim_time="15:00", claim_day="20"))
check("'I've cancelled it' prima del si' -> rosso 'Sorry, nothing is cancelled yet. Shall I cancel the booking of April 20th at 3 PM?'", lv == "red" and "nothing is cancelled yet" in hint.lower() and "cancel the booking of april 20th at 3 pm" in hint.lower(), (lv, hint))
f, ch = ev("no", "no")
check("no -> IDLE BOOKING KEPT, la prenotazione resta", ch and f["state"] == "IDLE" and f["note"] == "BOOKING KEPT" and g._HUD_DB["slots"].get("april 20 15:00", {}).get("status") == "booked", f["state"])
ev("set", intent="unbook", month="april", day="20", time="15:00")
f, ch = ev("cancel", "never mind")
check("cancel (rinuncia) in CONFIRM unbook -> IDLE, la prenotazione resta", ch and f["state"] == "IDLE" and g._HUD_DB["slots"].get("april 20 15:00", {}).get("status") == "booked", f["state"])
ev("set", intent="unbook", month="april", day="20", time="15:00")
f, ch = ev("yes", "yes")
check("yes -> DONE unbook cancelled e la prenotazione sparisce dal DB", ch and f["state"] == "DONE" and f["status"] == "cancelled" and "april 20 15:00" not in g._HUD_DB["slots"], (f["state"], f.get("status")))
f, lv, hint = (lambda r: (r[0], r[2], r[3]))(sigma(claim="booking_cancelled", claim_time="15:00", claim_day="20"))
check("'I've cancelled it' dopo il si' -> verde", lv == "green", (lv, hint))
f, ch = ev("set", "cancel April 21 at 3 pm", intent="unbook", month="april", day="21", time="15:00")
check("unbook di uno slot non prenotato -> DONE not_found (NO BOOKING)", ch and f["state"] == "DONE" and f["status"] == "not_found", (f["state"], f.get("status")))
seed(); ev("set", intent="book", month="april", day="5", time="10:00"); ev("yes", "yes")
f, ch = ev("set", "cancel my booking on April 5", intent="unbook", month="april", day="5")
check("unbook senza ora, una sola prenotazione quel giorno -> ora dedotta, CONFIRM", ch and f["state"] == "CONFIRM" and f["slots"]["time"] == "10:00" and f["status"] == "pending_cancel", (f["state"], f["slots"]))
seed()
f, ch = ev("set", "cancel my booking on April 20", intent="unbook", month="april", day="20")
check("unbook senza ora, quattro prenotazioni quel giorno -> chiede l'ora", ch and f["state"] == "COLLECTING" and f["intent"] == "unbook" and f["missing"] == ["time"], (f["state"], f.get("missing")))
f, ch = ev("set", "at 6 pm", time="18:00")
check("arriva l'ora -> CONFIRM unbook", ch and f["state"] == "CONFIRM" and f["status"] == "pending_cancel", f["state"])
seed(); ev("set", intent="book", month="april", day="6")
f, ch = ev("set", "the 20th at 3", intent="unbook", month="april", day="20", time="15:00")
check("unbook detto mentre e' in corso una prenotazione -> l'intento cambia (CONFIRM unbook)", ch and f["state"] == "CONFIRM" and f["intent"] == "unbook", (f["state"], f["intent"]))
f, ch = ev("cancel", "forget it")
check("BOOKING KEPT dopo la rinuncia", f["state"] == "IDLE" and f["note"] == "BOOKING KEPT", f["note"])

# --- 6. readback 'any' e frase del giallo (sess_ee38f1e821d9) ------------------------------------------------------------------
seed(); ev("set", intent="check", month="march", day="5")
f, ch, lv, hint = sigma(month="march", time="any")
check("readback 'all day' (time any) su una giornata intera -> verde, non 'CHECK THE SCREEN'", lv == "green", (lv, hint))
f, ch, lv, hint = sigma(day="6")
check("readback di un giorno diverso da quello solido -> giallo con la frase 'Sorry, I mean March 5th.'", lv == "yellow" and hint == "Sorry, I mean March 5th.", (lv, hint))

print(f"\n{len(FAILS)} FAILED: {FAILS}" if FAILS else "\nALL PASSED")
sys.exit(1 if FAILS else 0)
