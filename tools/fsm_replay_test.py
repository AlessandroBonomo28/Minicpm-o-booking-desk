#!/usr/bin/env python3
"""Replay locale della macchina degli stati dell'HUD (nessun LLM, nessun servizio): la sequenza di sess_41c874e48161 con la regola
FORCESPEAK-BETAGAMMA (08/09): una PROPOSTA dell'operatore verificata libera sul DB entra come tentativo "proposal" e il si' del
cliente la consolida. Il DB e' scritto in una copia temporanea. python3 tools/fsm_replay_test.py [-v]"""
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
check("annuncio di prenotazione -> rosso NOTHING BOOKED YET", lvl == "red" and hint == "NOTHING BOOKED YET" and f["tentative"].get("day") == "proposal", (lvl, hint))
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

# --- 4. proposta di un'ORA (giorno noto): verificata sul DB ---------------------------------------------------------
seed(); ev("set", intent="book", month="april", day="20")
f, ch, lvl, hint = sigma(claim="slot_free", claim_time="15:00")                     # 15:00 del 20 e' occupata
check("proposta di un'ora occupata -> non entra, rosso 3 PM IS TAKEN", not ch and not f["slots"]["time"] and lvl == "red", (lvl, hint, f["slots"]))
f, ch, lvl, hint = sigma(claim="slot_free", claim_time="16:00")
check("proposta di un'ora libera -> tentativo 'proposal', verde", ch and f["slots"]["time"] == "16:00" and f["tentative"].get("time") == "proposal" and lvl == "green", (lvl, f))
f, ch = ev("yes", "yes")
check("yes -> record completo -> CONFIRM pending", f["state"] == "CONFIRM" and f["status"] == "pending" and f["slots"]["time"] == "16:00", f)
f, ch = ev("yes", "yes")
check("secondo yes -> BOOKED april 20 16:00", f["state"] == "DONE" and f["status"] == "confirmed", f)
seed(); ev("set", intent="book", month="april")
f, ch, *_ = sigma(claim="slot_free", claim_day="15", claim_time="16:00")             # "How about April 15th at 4 pm?"
check("proposta giorno+ora insieme -> entrambi tentativi", f["slots"]["day"] == "15" and f["slots"]["time"] == "16:00" and f["tentative"] == {"day": "proposal", "time": "proposal"}, f)
seed(); ev("set", intent="check", month="april")
f, ch, *_ = sigma(claim="slot_free", claim_day="15", claim_time="16:00")
check("verifica (check): entra il giorno, non l'ora (non richiesta)", f["slots"]["day"] == "15" and not f["slots"]["time"], f)

# --- 5. readback senza claim: come prima (tentativo True) ------------------------------------------------------------
seed(); ev("set", intent="book", month="april")
f, ch, *_ = sigma(month="april", day="12")
check("readback (senza claim) -> tentativo True, IS THAT RIGHT?", f["slots"]["day"] == "12" and f["tentative"].get("day") is True, f)

print(f"\n{len(FAILS)} FALLITI: {FAILS}" if FAILS else "\nTUTTI PASSATI")
sys.exit(1 if FAILS else 0)
