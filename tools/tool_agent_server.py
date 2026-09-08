#!/usr/bin/env python3
"""Modello SEPARATO per il tool calling (ramo HUD, 03/09).

L'omni (MiniCPM-o 4.5) parla e ascolta; questo servizio legge il TESTO della
conversazione e decide se chiamare una funzione e con quali argomenti. Modello:
Qwen3-1.7B (tool calling nativo via chat template, stessa famiglia del cervello
dell'omni), ~3.4 GB bf16 sulla stessa GPU.

  POST /decide  {"transcript":[{"role":"assistant"|"user","text":"..."}], "user_audio_b64": ..., "language": "en",
                 "fsm": {stato della macchina dal gateway, opzionale}, "tools":[...opzionale...]}
                -> {"tool_calls":[{"name": book|check|cancel, "arguments":{...}}], "raw": "...", "user_text", "asr_s", "llm_s"}
  La FSM (merge dei campi, cosa manca, esecuzione) sta nel gateway: qui si estrae SOLO cio' che l'utente ha detto.
  GET  /health  -> "ready"

Avvio:  conda run -n minicpm python tools/tool_agent_server.py --port 22700
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import re
import sys
import threading
import time
import urllib.request
ASR_URL = "http://127.0.0.1:22710/transcribe"
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL_DIR = "/home/alex/progetti/MiniCPM-o-Demo/modelli/Qwen3-1.7B"

# Contratto nello SCHEMA, prompt minimo, valori VERBATIM (come Rasa: "extract slot values exactly as provided by the user,
# avoid assumptions or format changes"): le conversioni (ore a parole, ordinali) le fa il gateway, in codice.
DEFAULT_TOOLS = [
    {"type": "function", "function": {
        "name": "request",
        "description": "What the customer's last sentence asks the booking desk to do, and the month / day / time words it contains.",
        "parameters": {"type": "object", "properties": {
            "intent": {"type": "string", "enum": ["none", "check", "book", "cancel"],
                       "description": "none = default: greetings, thanks, hesitation, thinking aloud, anything that is not a request; "
                                      "check = asks whether a date or time is free/available (a question, no reservation); "
                                      "book = asks to reserve / make an appointment, or gives a month/day/time while a request is in progress; "
                                      "cancel = gives up the request in progress ('never mind', 'forget it', 'cancel')."},
            "month": {"type": ["string", "null"], "description": "the month NAME the customer said, exactly as said (e.g. 'April'); null if no month name was said. Numbers are never a month."},
            "day": {"type": ["string", "null"], "description": "the day of the month the customer said, exactly as said (e.g. '2nd', 'the second', 'twenty-first', '30'); null if no day was said."},
            "time": {"type": ["string", "null"], "description": "the time the customer said, exactly as said (e.g. '3 pm', 'half past ten', 'nine thirty', '15'); null if no time was said."}},
            "required": ["intent", "month", "day", "time"]}}},
]

# ---- 05/09 sera (Alessandro): l'algebra senza scorciatoie. Quattro eventi con un significato solo:
#      set = valori detti (mai scrive nel DB); yes / no = risposta alla domanda aperta (yes e' l'UNICO evento che scrive);
#      cancel = abbandono. Nessuna chiamata = nulla. "yes, at 3 pm" = set(time) + nuova conferma (yes non porta valori).
# Formato CANONICO in uscita dal modello (ramo hud-semaforo-fixrules): il modello normalizza il linguaggio, il gateway verifica.
_FIELDS = {"month": {"type": ["string", "null"], "description": "month as an English month name in lowercase ('april'); null if not said"},
           "day": {"type": ["string", "null"], "description": "day of the month as a plain number 1-31 ('2', '30'): convert 'the second' -> '2', '28th' -> '28'; 'any' if the customer asks about any day / the whole month; null if not said"},
           "time": {"type": ["string", "null"], "description": "time in 24h HH:MM ('15:00', '09:30'): convert '3 p.m.' -> '15:00', 'half past ten' -> '10:30', 'nine' -> '09:00' (1-7 without am/pm = afternoon); null if not said"}}
def _fn(name, desc, props=None, required=None):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props or {}, "required": required or []}}}
TOOL_DEFS = {
    "set": _fn("set", "The customer states or changes something about a request: what they want (intent: book = reserve / make an appointment; check = ask whether a date or time is free) and/or a month, a day, a time, exactly as said. Use it for new requests, for answers to the desk's questions ('the 20th', 'at 3 pm', 'April') and for corrections ('no, the 3rd', 'at 5 pm instead'). Pass only what was said.",
                {"intent": {"type": ["string", "null"], "enum": ["book", "check", None], "description": "book or check if the customer expressed it in this sentence; null otherwise"}, **_FIELDS}),
    "yes": _fn("yes", "The customer answers YES to the desk's open yes/no question (confirming a booking or accepting an offered slot): 'yes', 'ok', 'sure', 'go ahead', 'book it', 'that's fine'. Only when the sentence is a plain acceptance. NOT yes: a sentence that asks something back ('yeah, so did you check?', 'yes, but is it really free?', 'which one?') or that starts with yes and then changes a value (use set).",
               {"accepts": {"type": "string", "description": "the customer's own words that accept the offer, quoted (e.g. 'book it'); if the sentence contains no acceptance, do not call yes"}}, ["accepts"]),
    "no": _fn("no", "The customer answers NO to the desk's open yes/no question: 'no', 'no thanks', 'not that one', 'I'll think about it'."),
    "cancel": _fn("cancel", "The customer gives up the request in progress: 'never mind', 'forget it', 'cancel', 'stop'."),
}
def tools_for_state(fsm):
    return [TOOL_DEFS[n] for n in ("set", "yes", "no", "cancel")]

# ---- heard (05/09 sera): secondo orecchio = le RIPETIZIONI dell'operatore. L'omni sente meglio di Whisper; quando ripete un
#      valore ("Got it, April 20th") lo si legge come valore TENTATIVO (solo campi mancanti, conferma a livello di campo).
HEARD_TOOL = _fn("heard", "What the OPERATOR (the desk) just said. Fields month/day/time: ONLY values the operator repeats as the customer's (a readback: 'Got it, April 20th'); NOT questions, NOT proposals, NOT examples. Field claim: what the operator asserts about the booking system, if anything.",
                 {**_FIELDS,
                  "claim": {"type": ["string", "null"], "enum": ["slot_taken", "slot_free", "slot_invalid", "booking_confirmed", None],
                            "description": "slot_taken = says a time/day is taken or unavailable; slot_free = says a time/day is free or proposes it ('how about 16:00?', '6 pm is available'); slot_invalid = says a time/day is not valid; booking_confirmed = says the booking is done/confirmed/booked; null otherwise"},
                  "claim_time": {"type": ["string", "null"], "description": "the time the claim is about, 24h HH:MM; null if none"}})
HEARD_PROMPT = ("You read what the OPERATOR of a voice booking desk just said to the customer. Call `heard` with the month / day / time "
                "the operator repeats as understood from the customer; if the sentence repeats nothing (a question, a proposal, a greeting, "
                "a confirmation without values), call no function and answer NONE.")


# ---- σ "stuck detector" (07/09, Alessandro): un LLM in background con la conversazione intera, lo schermo, lo stato e i tempi
#      decide se l'omni e' BLOCCATO o FUORI CONTESTO e gli serve una mano (giallo con l'aiuto sullo schermo + force_speak).
#      Sostituisce heard: nella stessa chiamata riporta anche readback e claim.
SIGMA_TOOL = _fn("verdict", "Your verdict on the OPERATOR's situation right now.",
                 {**_FIELDS,
                  "claim": {"type": ["string", "null"], "enum": ["slot_taken", "slot_free", "slot_invalid", "booking_confirmed", None],
                            "description": "what the operator STATES about the booking system in its last turn, true or not: slot_taken, slot_free (also a proposal), slot_invalid, booking_confirmed; null if it states nothing"},
                  "claim_time": {"type": ["string", "null"], "description": "the time the claim is about, 24h HH:MM; null if none"},
                  "claim_day": {"type": ["string", "null"], "description": "the day of the month the claim is about, as a number; null if none"},
                  "status": {"type": "string", "enum": ["ok", "stuck"],
                             "description": "stuck = the operator needs help NOW. ok = the conversation is proceeding (small talk is ok; waiting after a customer filler like 'um' is ok)"},
                  "kind": {"type": ["string", "null"], "enum": ["silent", "off_context", "repeating", "ignores_screen", "false_claim", "cannot_do", None],
                           "description": "silent = the customer's last line needed an answer (a question, a request, a value) and the operator has not answered; off_context = the operator talks about something that is not this booking (another product, a car when the customer books a call); repeating = it asks again what it already asked and the customer already answered; ignores_screen = it does not ask for what the SCREEN marks MISSING, does not read a result the SCREEN shows, or does not follow the HELP it was given; false_claim = it announces a booking, an availability or an action ('I'll check the whole month') the SCREEN does not show; cannot_do = the customer asked something the system CANNOT do (see CAPABILITIES) and the operator did not say so"},
                  "help": {"type": ["string", "null"], "description": "ONLY if stuck: the exact sentence the operator should say to the customer now, first person, natural, max 14 words, using only facts on the SCREEN and the CAPABILITIES; never an instruction to the operator (it is read aloud as is). E.g. 'Which day in April would you like?', 'April 3rd is free except 6 pm. Shall I book it?', 'I can book one slot at a time. Which day?', 'Sorry, 3 pm on that day is taken.'; null otherwise"}},
                 ["status"])
SIGMA_CAPABILITIES = ("CAPABILITIES of the booking system (the SCREEN is its state): it can tell whether ONE day or ONE time slot is free; "
                      "it can show which days of a month are booked (when the month is known and the day is missing); it can book ONE slot "
                      "(month + day + time) only after the customer says yes; it can cancel the request. It CANNOT: book several slots or "
                      "recurring bookings, search across months, handle names, rooms, services, prices or payments, or anything outside "
                      "this booking. The operator must never announce an action the system is not doing: the SCREEN shows what it does.")
SIGMA_PROMPT = ("You are the SUPERVISOR of a voice booking desk. A small speech model, the OPERATOR, talks with the CUSTOMER and reads "
                "the SCREEN, which shows the booking system's state and is the only source of truth. You see the whole conversation, the "
                "SCREEN, the STATE, the TIMING and the CAPABILITIES. Call verdict() once. Be strict on off_context, false_claim and "
                "cannot_do. If HELP was given before this turn and the operator's turn does not follow it, it is still stuck "
                "(ignores_screen) with the same or a shorter help. The help is spoken to the customer word for word: write it as the operator's "
                "own sentence, never as an order to the operator. " + SIGMA_CAPABILITIES + " "
                "When REASON is no_reply, the operator has said nothing since the customer's last line: if that line is a question, a "
                "request, a value, or a direct address ('are you there?', 'hello?', 'so?'), it is stuck (kind silent) and help says what to "
                "answer from the SCREEN; only a filler ('um', 'hmm', 'ok', 'yeah') with nothing to answer is ok. "
                "month/day/time: ONLY values the operator repeats as the customer's own in its last turn (a readback), never questions, "
                "proposals or examples. A proposal by the operator ('how about April 15th?', '3 pm is free, shall I book it?') is claim "
                "slot_free with claim_day / claim_time, and it is ok when the SCREEN does not show that day or time as booked; the SCREEN "
                "then shows the proposal with a question mark ('BOOK: APRIL 15?' / 'DOES THAT WORK?') until the customer answers. "
                "If the operator's last turn asks the question on the SCREEN's last line or reads the fact the SCREEN shows, it is ok, "
                "even if brief or reworded.")


def decide_sigma(operator_text, fsm, transcript, screen, reason, timing, previous_help=""):
    lines = [(t.get("role"), (t.get("text") or "").strip()) for t in (transcript or []) if (t.get("text") or "").strip()]
    convo = "\n".join(f"{'OPERATOR' if r == 'assistant' else 'CUSTOMER'}: {x}" for r, x in lines[-40:]) or "(nothing yet)"
    state_line = fsm_line_v2(fsm) if isinstance(fsm, dict) else "STATE: unknown"
    t = timing or {}
    tline = (f"TIMING: the customer's last line was {t.get('since_user_s', '?')} s ago; the operator is {'speaking now' if t.get('omni_speaking') else 'silent'}; "
             f"its last turn ended {t.get('since_omni_s', '?')} s ago.")
    last = operator_text or ("(no operator turn since the customer's last line)" if reason == "no_reply" else "(silence)")
    hline = f"HELP GIVEN TO THE OPERATOR BEFORE THIS TURN: {previous_help}\n" if previous_help else ""
    user = (f"SCREEN (what the operator sees now): {screen or '?'}\n{state_line}\n{tline}\n{hline}\nCONVERSATION (oldest first):\n{convo}\n\n"
            f"OPERATOR'S LAST TURN: {last}\nREASON FOR THIS CHECK: {reason or 'turn_end'}\n\nCall verdict().")
    messages = [{"role": "system", "content": SIGMA_PROMPT}, {"role": "user", "content": user}]
    fname, args_json, used_model, ms = decide_cloud(messages, [SIGMA_TOOL])
    calls = []
    if fname == "verdict":
        try:
            a = json.loads(args_json or "{}")
        except Exception:
            a = {}
        args = {}
        for k in ("month", "day", "time", "claim", "claim_time", "claim_day", "kind"):
            v = a.get(k)
            if isinstance(v, (str, int, float)) and str(v).strip().lower() not in _EMPTY:
                args[k] = str(v).strip()
        args["status"] = "stuck" if str(a.get("status", "ok")).lower() == "stuck" else "ok"
        h = a.get("help")
        if args["status"] == "stuck" and isinstance(h, str) and h.strip().lower() not in _EMPTY:
            args["help"] = re.sub(r"\s+", " ", h.strip().strip('"\''))[:90]
        calls.append({"name": "sigma", "arguments": args})
    return {"tool_calls": calls, "backend": f"{BACKEND}:{used_model or CLOUD['model']} {ms:.0f}ms"}


def decide_heard(operator_text, fsm):
    """Ritorna la chiamata heard (o nessuna) sul testo dell'operatore. Solo con il backend cloud (il locale non e' usato)."""
    messages = [{"role": "system", "content": HEARD_PROMPT},
                {"role": "user", "content": f"OPERATOR: {operator_text}\n\nCall heard() or answer NONE."}]
    fname, args_json, used_model, ms = decide_cloud(messages, [HEARD_TOOL])
    calls = []
    if fname == "heard":
        try:
            a = json.loads(args_json or "{}")
        except Exception:
            a = {}
        args = {k: str(v).strip() for k, v in a.items() if k in ("month", "day", "time", "claim", "claim_time") and isinstance(v, (str, int, float)) and str(v).strip().lower() not in _EMPTY}
        if args:
            calls.append({"name": "heard", "arguments": args})
    return {"tool_calls": calls, "backend": f"cline:{used_model} {ms:.0f}ms"}

LOCAL_PROMPT = ("You are the request extractor of a booking desk. Read STATE and the customer's last sentence, then call at most ONE "
                "function: set (values said, copied exactly), yes / no (answer to the desk's open question), cancel. "
                "If the sentence is not a request or an answer (greeting, thanks, hesitation), call no function and answer NO ACTION.")
PROMPT_API = ("You are the request extractor of a voice booking desk (OPERATOR = the desk, USER = the customer, transcribed by an ASR "
              "with small errors). Read STATE, the last lines of the conversation and the customer's NOW line, then call at most ONE "
              "function about the NOW line.\n"
              "set = what the customer states: intent (book / check) and/or month, day, time, NORMALIZED: month name in lowercase, "
              "day as a number, time as 24h HH:MM. Never guess or compute values; a bare number answers what the desk just asked.\n"
              "yes / no = a plain answer to the desk's open yes/no question (STATE says if there is one). If the customer answers yes "
              "but also changes a value ('yes, at 3 pm'), call set with the value, not yes. A yes/no when STATE has no open question "
              "is still yes/no (the desk will ignore it).\n"
              "cancel = the customer gives up. Greeting, thanks, hesitation, off-topic, questions about the booking system: no function, "
              "answer NO ACTION.")
SYSTEM = LOCAL_PROMPT

# ---- HARNESS v2 (06/09, Alessandro: "e' tutto un fatto di harness"): il contesto giusto per sciogliere le ambiguita'.
#      1) la domanda aperta del banco e' riportata PAROLA PER PAROLA, con i valori (l'idempotenza della FSM rende innocua una copia);
#      2) dopo uno slot occupato lo stato dice cosa fare ("what's free?" = set intent check);
#      3) i valori vengono SOLO dalla riga NOW del cliente; le date relative si risolvono solo con un riferimento esplicito (oggi, o una
#      data nel dialogo); 4) una domanda / un dubbio non e' mai un si'.
PROMPT_API_V2 = ("You are the request extractor of a voice booking desk (OPERATOR = the desk, USER = the customer, transcribed by an ASR "
                 "with small errors). Read STATE, the last lines of the conversation and the customer's NOW line, then call at most ONE "
                 "function about the NOW line.\n"
                 "set = what the customer states in the NOW line: intent (book / check) and/or month, day, time, NORMALIZED: month name in "
                 "lowercase, day as a number, time as 24h HH:MM. Values come ONLY from the customer's NOW line: never copy a value from the "
                 "desk's lines or from STATE (they are context to understand the NOW line, not values to pass). A bare number answers what "
                 "STATE says is being asked. Relative dates ('the next day', 'the day after') are resolved only from a date said in the conversation; 'tomorrow' or 'next week' without a reference: pass nothing for the date.\n"
                 "Asking what is free ('when is it free?', 'what's the next free slot?', 'anything else that day?') = set with intent check "
                 "and no values (the desk keeps the date it already has). If the customer WIDENS the request ('the whole month', 'any day', "
                 "'all of April', 'any time', 'the whole day'), pass day: 'any' (or time: 'any'): the desk drops that value.\n"
                 "yes / no = a plain answer to the desk's open yes/no question quoted in STATE. yes ONLY if the customer accepts exactly "
                 "what the question offers; a question, a doubt, a request to verify ('did you check?', 'is it really free?', 'which one?') "
                 "or a comment is NOT a yes and NOT a value: no function. If the customer answers yes but also changes a value ('yes, at 3 pm'), "
                 "call set with the value.\n"
                 "cancel = the customer gives up the request. Greeting, thanks, hesitation, off-topic: no function, answer NO ACTION.")
HARNESS = "v2"   # v2 | legacy (--harness)


def _hl_date(sl):
    d = (sl.get("date") or "").strip()
    return d if d else " ".join(x for x in (sl.get("month", ""), sl.get("day", "")) if x)


def fsm_line_v2(fsm):
    """Riga di stato v2: la domanda aperta e' citata con i valori; dopo un occupato si dice cosa fare; oggi e' dichiarato."""
    # TODAY tolto (misurato 06/09 con minimax-m3: la data di oggi finiva copiata nei valori, "book a desk" -> september 6)
    today = ""
    st = (fsm or {}).get("state") if isinstance(fsm, dict) else None
    sl = (fsm or {}).get("slots") or {} if isinstance(fsm, dict) else {}
    tm = sl.get("time") or ""
    when = _hl_date(sl) + (f" at {tm}" if tm and tm != "all-day" else "")
    if st == "CONFIRM" and fsm.get("intent") == "book":
        return today + f'STATE: the desk asked the customer: "Shall I book {when}?" Open yes/no question (yes = book exactly that; no = do not; a corrected value = set).'
    if st == "CONFIRM":
        return today + f'STATE: the desk said "{when} is free" and asked: "Would you like to book it?" Open yes/no question (yes = book that slot; no = decline; another date/time = set).'
    if st == "COLLECTING" and (fsm.get("tentative") or {}):
        tent = fsm.get("tentative") or {}
        tk = [f"{k}={sl.get(k)}" for k in ("month", "day", "time") if tent.get(k)]
        if any(v == "proposal" for v in tent.values()):
            # FORCESPEAK-BETAGAMMA (08/09): proposta dell'operatore verificata libera, sullo schermo col punto di domanda
            return today + (f"STATE: a {fsm.get('intent')} request is in progress; the desk PROPOSED {', '.join(tk)} and asked the customer "
                            "whether that works. Open yes/no question (yes = the customer accepts the proposal; no = declines; another value = set).")
        return today + (f"STATE: a {fsm.get('intent')} request is in progress; the desk asked the customer to confirm what it understood: {', '.join(tk)}. "
                        "Open yes/no question (yes = correct; no = wrong; a corrected value = set).")
    if st == "COLLECTING":
        got = [k for k in ("month", "day", "time") if sl.get(k)]
        miss = [k for k in (fsm.get("missing") or []) if k in ("month", "day", "time")]
        ask = miss[0] if miss else "nothing"
        mi = fsm.get("month_info") or {}
        if mi.get("month"):
            today += f"The screen shows {mi['month']}: " + (f"booked days {', '.join(str(d) for d in mi['booked_days'])}, other days free. " if mi.get("booked_days") else "all days free. ")
        return today + (f"STATE: a {fsm.get('intent')} request is in progress; collected: {', '.join(got) or 'nothing'}; "
                        f"missing: {', '.join(miss) or 'nothing'}. The desk is asking for the {ask.upper()}: a bare number is the {ask}. No yes/no question is open.")
    if st == "DONE" and fsm.get("status") == "taken":
        return today + (f"STATE: the desk just told the customer that {when} is TAKEN. If the customer asks what is free or for another slot, "
                        "call set with intent check and no values; a new time = set with the time; thanks or goodbye = no function.")
    if st == "DONE":
        return today + "STATE: the last request is closed (done). No open question. Thanks or goodbye = no function; a new request = set."
    return today + "STATE: no request in progress. No open question."
DEFAULT_TOOLS = None   # per stato: vedi tools_for_state


tok = None
model = None
lock = threading.Lock()
TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)


def fsm_line(fsm):
    """Riga di stato per l'estrattore: mai valori; dice solo se c'e' una domanda sì/no aperta e cosa manca."""
    st = (fsm or {}).get("state") if isinstance(fsm, dict) else None
    if st == "CONFIRM" and fsm.get("intent") == "book":
        return "STATE: the desk asked the customer to CONFIRM a booking. Open question: yes / no (a corrected value is also possible)."
    if st == "CONFIRM":
        return "STATE: the desk said a slot is free and asked if the customer wants to book it. Open question: yes / no (or another date/time)."
    if st == "COLLECTING" and (fsm.get("tentative") or {}):
        tk = [k for k in ("month", "day", "time") if (fsm.get("tentative") or {}).get(k)]
        return (f"STATE: a {fsm.get('intent')} request is in progress; the desk asked the customer to CONFIRM the {' and '.join(tk)} "
                f"it understood. Open question: yes / no (or a corrected value with set).")
    if st == "COLLECTING":
        sl = fsm.get("slots") or {}
        got = [k for k in ("month", "day", "time") if sl.get(k)]
        miss = [k for k in (fsm.get("missing") or []) if k in ("month", "day", "time")]
        return (f"STATE: a {fsm.get('intent')} request is in progress; collected: {', '.join(got) or 'nothing'}; "
                f"missing: {', '.join(miss) or 'nothing'}. No yes/no question is open; a bare number answers the first missing field.")
    if st == "DONE":
        return "STATE: the last request is closed. No open question."
    return "STATE: no request in progress. No open question."


_EMPTY = {"", "none", "null", "unknown", "n/a", "not specified", "not mentioned"}


CONTEXT_RULES = ("\nThe lines before NOW are the conversation so far (OPERATOR = the desk, USER = the customer). Use them ONLY to "
                 "understand what the NOW line refers to: if the customer accepts an offer ('yes', 'ok', 'sure', 'book it') or refers "
                 "to a date the operator or the customer just mentioned ('that day', 'the same day'), take month/day/time from that "
                 "mention; 'the next day' / 'the day after' = that day + 1, 'the day before' = that day - 1. If the NOW line does not "
                 "refer to them, ignore the earlier lines completely: 'thank you', 'let me think', chit-chat -> intent none, all null.")


# ---- backend cloud (05/09): endpoint OpenAI-compatible del provider Cline (https://api.cline.bot/api/v1), stesso schema.
#      Chiave/modello da ~/.config/tool_agent.env (TA_API_KEY, TA_BASE_URL, TA_MODEL); il locale resta come fallback.
BACKEND = "local"
CONSTRAINED = False
_constrained_cache = {}


def _constrained_prefix_fn(tools):
    """Grammatica JSON per lm-format-enforcer: {"name": <uno degli strumenti o none>, "arguments": {month, day, time | null}}."""
    from lmformatenforcer import JsonSchemaParser
    from lmformatenforcer.integrations.transformers import build_transformers_prefix_allowed_tokens_fn
    names = tuple(sorted(x["function"]["name"] for x in tools)) + ("none",)
    if names not in _constrained_cache:
        schema = {"type": "object",
                  "properties": {"name": {"type": "string", "enum": list(names)},
                                 "arguments": {"type": "object", "properties": {
                                     "month": {"type": ["string", "null"]}, "day": {"type": ["string", "null"]}, "time": {"type": ["string", "null"]}},
                                     "additionalProperties": False}},
                  "required": ["name", "arguments"], "additionalProperties": False}
        _constrained_cache[names] = build_transformers_prefix_allowed_tokens_fn(tok, JsonSchemaParser(schema))
    return _constrained_cache[names]
CLOUD = {"base_url": "https://api.cline.bot/api/v1", "model": "google/gemini-3.5-flash-lite", "key": "", "timeout": 4.0, "context": 6, "extra": {}}
CLOUD_BACKENDS = ("cline", "openai")   # ramo phonellm (06/09): "openai" = qualunque endpoint OpenAI-compatible (Modal/vLLM, Featherless, ...)
_TAG_CALL_RE = re.compile(r"<(?:TOOLCALL|tool_call)>\s*(.*?)\s*</(?:TOOLCALL|tool_call)>", re.S)


def _parse_text_tool_call(content):
    """Provider senza tool parser nativo: la chiamata arriva nel testo (Nemotron <TOOLCALL>[{...}]</TOOLCALL>, Hermes <tool_call>{...}</tool_call>)."""
    for m in _TAG_CALL_RE.finditer(content or ""):
        try:
            obj = json.loads(m.group(1))
        except Exception:
            continue
        if isinstance(obj, list):
            obj = obj[0] if obj else None
        if isinstance(obj, dict) and obj.get("name"):
            args = obj.get("arguments") if obj.get("arguments") is not None else (obj.get("parameters") or {})
            return str(obj["name"]), (args if isinstance(args, str) else json.dumps(args))
    return None


def load_env_file(path):
    try:
        for line in open(os.path.expanduser(path)):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass


def decide_cloud(messages, tools):
    """Una chiamata chat/completions (tools + tool_choice auto, temperatura 0). Ritorna (name, arguments_json, model, ms) o solleva.
    CLOUD["extra"] viene aggiunto al corpo (es. chat_template_kwargs.enable_thinking=false per Nemotron/Qwen3 su vLLM);
    se il provider lo rifiuta (HTTP 400) si ritenta senza. Se il provider non ha il tool parser, la chiamata si legge dal testo."""
    payload = {"model": CLOUD["model"], "messages": messages, "tools": tools, "temperature": 0, "max_tokens": 200, "tool_choice": "auto"}
    payload.update(CLOUD.get("extra") or {})
    headers = {"content-type": "application/json"}
    if CLOUD.get("key"):
        headers["Authorization"] = f"Bearer {CLOUD['key']}"
    url = CLOUD["base_url"].rstrip("/") + "/chat/completions"
    t0 = time.time()
    try:
        d = json.loads(urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers), timeout=CLOUD["timeout"]).read())
    except urllib.error.HTTPError as e:
        if e.code != 400 or not CLOUD.get("extra"):
            raise
        for k in CLOUD["extra"]:
            payload.pop(k, None)
        d = json.loads(urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers), timeout=CLOUD["timeout"]).read())
    d = d.get("data", d)
    ch = d["choices"][0]["message"]
    tc = ch.get("tool_calls") or []
    ms = (time.time() - t0) * 1000
    if tc:
        return tc[0]["function"]["name"], tc[0]["function"]["arguments"], d.get("model"), ms
    parsed = _parse_text_tool_call(ch.get("content") or "")
    if parsed:
        return parsed[0], parsed[1], d.get("model"), ms
    return "", "", d.get("model"), ms


def decide(transcript, _tools_unused, fsm=None, context=0):
    """context=0: SOLO la battuta corrente (contratto attuale: le righe precedenti erano una fonte da cui copiare campi).
    context=N: esperimento (05/09, richiesta di Alessandro): anche le ultime N righe del dialogo, operatore compreso,
    per risolvere 'yes' / 'that day' / 'the next day'."""
    import torch
    lines = [(t.get("role"), (t.get("text") or "").strip()) for t in transcript if (t.get("text") or "").strip()]
    users = [x for r, x in lines if r == "user"]
    if not users:
        return {"tool_calls": [], "raw": "NO ACTION (nessuna riga utente)"}
    last_user_idx = max(i for i, (r, _) in enumerate(lines) if r == "user")
    convo = f"NOW USER: {lines[last_user_idx][1]}"
    tools = tools_for_state(fsm)
    # cloud: PROMPT_API + ultime righe del dialogo; locale: LOCAL_PROMPT e SOLO la battuta corrente
    system = (PROMPT_API_V2 if HARNESS == "v2" else PROMPT_API) if BACKEND in CLOUD_BACKENDS else LOCAL_PROMPT
    state_line = fsm_line_v2(fsm) if (HARNESS == "v2" and BACKEND in CLOUD_BACKENDS) else fsm_line(fsm)
    if context == "state":
        context = 0
    if BACKEND in CLOUD_BACKENDS and not context:
        context = CLOUD.get("context", 6)
    if context and last_user_idx > 0:
        prev = lines[max(0, last_user_idx - int(context)):last_user_idx]
        convo = "\n".join(f"{'OPERATOR' if r == 'assistant' else 'USER'}: {x}" for r, x in prev) + "\n" + convo

    messages = [{"role": "system", "content": system},
                {"role": "user", "content": f"{state_line}\n\n{convo}\n\nCall one function about the NOW line."}]
    backend_used = BACKEND
    raw = ""
    if BACKEND in CLOUD_BACKENDS:
        try:
            fname, args_json, used_model, ms = decide_cloud(messages, tools)
            raw = f'<tool_call>{{"name": "{fname or "none"}", "arguments": {args_json or "{}"}}}</tool_call>'
            backend_used = f"{BACKEND}:{used_model or CLOUD['model']} {ms:.0f}ms"
        except Exception as e:
            sys.stderr.write(f"[tool-agent] cloud non disponibile ({type(e).__name__}: {str(e)[:80]}): fallback locale\n")
            backend_used = "local (fallback)"
    if not raw and tok is not None:
        prompt = tok.apply_chat_template(messages, tools=tools, add_generation_prompt=True, tokenize=False, enable_thinking=False)
        with lock:
            if CONSTRAINED:
                # decodifica VINCOLATA: solo JSON valido per gli strumenti disponibili (niente formato rotto, niente 'day': 'of');
                # si forza il prefisso <tool_call> e si lascia al modello solo la scelta dentro la grammatica
                prompt2 = prompt + "<tool_call>\n"
                ids = tok(prompt2, return_tensors="pt").to(model.device)
                fn = _constrained_prefix_fn(tools)
                out = model.generate(**ids, max_new_tokens=80, do_sample=False, prefix_allowed_tokens_fn=fn)
                body = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
                raw = "<tool_call>\n" + body.strip() + "\n</tool_call>"
            else:
                ids = tok(prompt, return_tensors="pt").to(model.device)
                out = model.generate(**ids, max_new_tokens=120, do_sample=False)
                raw = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=False)
    calls = []
    allowed = {x["function"]["name"] for x in tools}
    for m in TOOL_CALL_RE.finditer(raw):
        try:
            c = json.loads(m.group(1))
        except Exception:
            continue
        if not isinstance(c, dict):
            continue
        name = str(c.get("name") or "none").lower(); a = dict(c.get("arguments") or {})
        if name in ("book", "check", "check_availability"):   # compat vecchio contratto
            a["intent"] = "book" if name == "book" else "check"; name = "set"
        if name not in allowed:
            break
        args = {}
        for k in ("intent", "month", "day", "time", "date"):
            v = a.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                args[k] = str(int(v))
            elif isinstance(v, str) and v.strip().lower() not in _EMPTY:
                if k == "time" and not re.search(r"\d|noon|midnight|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|half|quarter", v.lower()):
                    continue
                args[k] = v.strip()
        calls.append({"name": name, "arguments": args})
        break
    return {"tool_calls": calls, "raw": raw.replace("<|im_end|>", "").strip()[:400], "backend": backend_used}


class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):
        sys.stderr.write("[tool-agent] " + (fmt % a) + "\n")

    def _send(self, code, body: bytes, ctype="application/json"):
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, b"ready", "text/plain")
        else:
            self._send(404, b"")

    def do_POST(self):
        if self.path == "/sigma":
            n = int(self.headers.get("Content-Length", 0))
            try:
                req = json.loads(self.rfile.read(n) or b"{}")
                if BACKEND not in CLOUD_BACKENDS:
                    self._send(200, json.dumps({"tool_calls": [], "backend": "local: sigma non disponibile"}).encode()); return
                t0 = time.time()
                res = decide_sigma((req.get("operator_text") or "").strip(), req.get("fsm"), req.get("transcript") or [], req.get("screen") or "",
                                   req.get("reason") or "turn_end", req.get("timing") or {}, str(req.get("previous_help") or ""))
                res["total_s"] = round(time.time() - t0, 2)
                self._send(200, json.dumps(res, ensure_ascii=False).encode())
            except Exception as e:
                self._send(500, json.dumps({"error": f"{type(e).__name__}: {e}"}).encode())
            return
        if self.path == "/heard":
            n = int(self.headers.get("Content-Length", 0))
            try:
                req = json.loads(self.rfile.read(n) or b"{}")
                if BACKEND not in CLOUD_BACKENDS:
                    self._send(200, json.dumps({"tool_calls": [], "backend": "local: heard non disponibile"}).encode()); return
                t0 = time.time()
                res = decide_heard((req.get("operator_text") or "").strip(), req.get("fsm"))
                res["total_s"] = round(time.time() - t0, 2)
                self._send(200, json.dumps(res, ensure_ascii=False).encode())
            except Exception as e:
                self._send(500, json.dumps({"error": f"{type(e).__name__}: {e}"}).encode())
            return
        if self.path != "/decide":
            self._send(404, b""); return
        n = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
            transcript = list(req.get("transcript") or [])
            user_text = ""; asr_s = None; asr_model = None; t_all = time.time()
            if req.get("user_audio_b64"):
                # ASR degli ultimi secondi del microfono (servizio separato, env cosyvoice2)
                try:
                    body = json.dumps({"audio_b64": req["user_audio_b64"], "language": req.get("language") or "en", "context_s": float(req.get("context_s") or 0)}).encode()
                    r = urllib.request.urlopen(urllib.request.Request(ASR_URL, data=body, headers={"content-type": "application/json"}), timeout=20)
                    rj = json.loads(r.read()); user_text = (rj.get("text") or "").strip(); asr_s = rj.get("asr_s"); asr_model = rj.get("model")
                except Exception as e:
                    user_text = ""; sys.stderr.write(f"[tool-agent] ASR non disponibile: {e}\n")
                if user_text:
                    # la voce dell'utente precede l'ultima battuta dell'operatore
                    if transcript and transcript[-1].get("role") == "assistant":
                        transcript.insert(len(transcript) - 1, {"role": "user", "text": user_text})
                    else:
                        transcript.append({"role": "user", "text": user_text})
            t_llm = time.time()
            if req.get("user_audio_b64") and not user_text:
                # il trigger e' il turno dell'utente: senza parole dell'utente non c'e' nulla da decidere
                res = {"tool_calls": [], "raw": "NO ACTION (nessun testo utente)"}
            else:
                ctxmode = req.get("context") or 0
                if ctxmode == "state":
                    pass   # nessuna riga di dialogo: l'offerta in sospeso sta nella riga di stato
                elif ctxmode == "auto":
                    # contesto SOLO con un'offerta in sospeso (ultimo esito: verifica con posto libero): li' 'yes'/'that day'
                    # devono prendere la data dall'offerta; in ogni altro stato il contesto e' solo una fonte di copie
                    f = req.get("fsm") or {}
                    ctxmode = 3 if f.get("state") == "CONFIRM" else 0
                res = decide(transcript, None, req.get("fsm"), ctxmode if ctxmode == "state" else int(ctxmode))
            res["user_text"] = user_text; res["asr_s"] = asr_s; res["asr_model"] = asr_model; res["fallback_local"] = tok is not None; res["llm_s"] = round(time.time() - t_llm, 2); res["total_s"] = round(time.time() - t_all, 2)
            self._send(200, json.dumps(res, ensure_ascii=False).encode())
        except Exception as e:
            self._send(500, json.dumps({"error": f"{type(e).__name__}: {e}"}).encode())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=22700)
    ap.add_argument("--model-dir", default=MODEL_DIR)
    ap.add_argument("--backend", choices=["local", "cline", "openai"], default="local",
                    help="cline = API Cline (TA_API_KEY); openai = endpoint OpenAI-compatible generico (TA_OPENAI_BASE_URL, TA_OPENAI_API_KEY, TA_OPENAI_MODEL); locale come fallback")
    ap.add_argument("--cloud-model", default=None, help="id modello sul provider (default: TA_MODEL / TA_OPENAI_MODEL)")
    ap.add_argument("--extra-body", default=None, help='JSON aggiunto a ogni richiesta, es. {"chat_template_kwargs":{"enable_thinking":false}}')
    ap.add_argument("--harness", choices=["v2", "legacy"], default="v2", help="v2 = domanda aperta citata con i valori, TODAY, stato 'taken' esplicito (06/09); legacy = riga di stato senza valori")
    ap.add_argument("--no-think", action="store_true", help="chat_template_kwargs.enable_thinking=false (Nemotron 3 / Qwen3 su vLLM o SGLang: PhoneLLM va usato cosi')")
    ap.add_argument("--no-local", action="store_true", help="con --backend cline: non caricare il modello locale (niente fallback, libera la VRAM)")
    args = ap.parse_args()
    global tok, model, BACKEND, CONSTRAINED, HARNESS
    load_env_file("~/.config/tool_agent.env")
    BACKEND = args.backend; HARNESS = args.harness
    try:
        import lmformatenforcer  # noqa: F401
        CONSTRAINED = os.environ.get("TA_CONSTRAINED", "0") == "1"   # misurato 05/09: vincolata 44/55 contro 47 libera (inventa valori per riempire il JSON)
    except ImportError:
        CONSTRAINED = False
    print(f"decodifica vincolata (locale): {'ON' if CONSTRAINED else 'OFF'}", flush=True)
    if BACKEND in CLOUD_BACKENDS:
        if BACKEND == "openai":
            CLOUD["base_url"] = os.environ.get("TA_OPENAI_BASE_URL", ""); CLOUD["key"] = os.environ.get("TA_OPENAI_API_KEY", "")
            CLOUD["model"] = args.cloud_model or os.environ.get("TA_OPENAI_MODEL", "")
            CLOUD["timeout"] = float(os.environ.get("TA_OPENAI_TIMEOUT", "8"))
            if not CLOUD["base_url"] or not CLOUD["model"]:
                raise SystemExit("TA_OPENAI_BASE_URL / TA_OPENAI_MODEL mancanti (~/.config/tool_agent.env)")
        else:
            CLOUD["key"] = os.environ.get("TA_API_KEY", ""); CLOUD["base_url"] = os.environ.get("TA_BASE_URL", CLOUD["base_url"])
            CLOUD["model"] = args.cloud_model or os.environ.get("TA_MODEL", CLOUD["model"])
            if not CLOUD["key"]:
                raise SystemExit("TA_API_KEY mancante (~/.config/tool_agent.env)")
            CLOUD["timeout"] = float(os.environ.get("TA_TIMEOUT", CLOUD["timeout"]))
        CLOUD["context"] = int(os.environ.get("TA_CONTEXT", CLOUD["context"]))
        extra = json.loads(args.extra_body) if args.extra_body else {}
        if args.no_think:
            extra.setdefault("chat_template_kwargs", {})["enable_thinking"] = False
        CLOUD["extra"] = extra
        print(f"backend cloud ({BACKEND}): {CLOUD['base_url']} modello {CLOUD['model']} (timeout {CLOUD['timeout']} s, extra {extra or 'nessuno'}, harness {HARNESS})", flush=True)
    if BACKEND == "local" or not args.no_local:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        print(f"carico {args.model_dir} ...", flush=True)
        tok = AutoTokenizer.from_pretrained(args.model_dir)
        model = AutoModelForCausalLM.from_pretrained(args.model_dir, torch_dtype=torch.bfloat16, low_cpu_mem_usage=True).to("cuda").eval()
    print(f"pronto su :{args.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), H).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
