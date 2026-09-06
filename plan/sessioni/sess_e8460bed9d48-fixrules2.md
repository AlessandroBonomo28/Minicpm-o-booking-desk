# Sessione sess_e8460bed9d48 — fixrules b06f068 (06/09, 12:52-12:58), letta dal registro
Config: prompt "ALWAYS SPEAK, read the screen to know what to say", heard on, blink on, turbo, finestra basic, trp 1.0.
DB: march 28 13:00/15:00/17:00 occupati. Durata 6 min, 34 tagli della finestra (19,7k token scartati), KV sempre ~3,5-4k.

## Conversazione (essenziale)
35.7  "I'd like to book" / "28" / "March"         -> raccolta pulita, readback giusti (28, March 28th)
63.0  "At 15"                                     -> DONE TAKEN (vero). Omni: "2:15. I am sorry, that slot is already taken."
                                                     heard: claim slot_taken 14:15 -> ROSSO "14:15 IS FREE" (falso allarme: l'omni ha
                                                     storpiato l'ora, 15 -> "2:15"; a 97 s "16" -> "4:16")
76.6  "What's the next free slot?"                -> nessun evento. Omni: "The next free slot is at 2:15" (ha rilanciato il banner rosso)
                                                     -> GIALLO (14:15 contraddice il 15:00 solido del record chiuso)
97.3  "at 16"                                     -> richiesta NUOVA da DONE: "valore senza intento = verifica" -> CHECK ? ? 16:00,
                                                     data persa; omni "4:16. you forgot the month"
107.6 "28th of March"                             -> CONFIRM check march 28 16:00 AVAILABLE; omni "That slot is available."
117   "um"                                        -> set(march,28,16:00) eco -> INVARIATO (idempotenza ok)
133.1 "Okay, let's book it"                       -> yes -> DONE BOOKED march 28 16:00 (scritto). Omni "your booking is confirmed" -> verde
142-213 chiacchiere in DONE: "You're welcome", "I'm fine", "I see a message from the system. It says 'Booking done, March 28th,
        16:00, confirmed'" (legge lo schermo alla lettera), "My day was okay...", "I think there is a plane available" (inventato)
222.4 "No, I told you it's April available"      -> set(april) -> nuovo CHECK april ? (manca day)
236.7 "no i don't care about the plane"           -> cancel -> IDLE
253.4 "Which one?"                                -> set(april) INVENTATO dal contesto -> CHECK april ?
259   omni "I think April 1st is a free day"      -> claim slot_free (valori non entrano: regola dei claim)
275.4 "check it for april 1st"                    -> CONFIRM check april 1 all-day AVAILABLE
276-300 omni: "I can check it for April 1st" / "it's available" / "I can check for that day" (eco del cliente, non legge AVAILABLE)
306.8 "yeah so did you check"                     -> YES (domanda scambiata per accettazione) -> accetta l'offerta -> COLLECTING book april 1
                                                     manca time. Omni: "Yeah, I checked it." (risponde alla voce, ignora NEW BOOKING)
315.2 "No, you're lying"                          -> no -> nessuna domanda aperta -> invariato
322-365 "You are lying" x2, "Why don't you answer anymore?", "Do you hear me?", "Hello?", "are you there": OMNI MUTO 56 s
        (backend: nessun turno speak dopo 306 s; frame inviati fino al #346; KV 3,6-4k; nessun errore)

## Cosa si vede
1. Fix 1 e 5 hanno retto: CONFIRM reso giusto (AVAILABLE, niente "SLOT TAKEN" inventato); tre eco dell'estrattore
   ("um", "Is it available?", "check for that day") sono rimasti invariati senza spegnere nulla.
2. **Slot occupato che chiude la richiesta** ha fatto tre danni in fila: "next free slot" senza evento, "at 16" letto come
   verifica senza data, giallo sulla proposta dell'omni (contraddice l'ora del record chiuso). Con "occupato = valore respinto,
   si resta in raccolta" tutti e tre spariscono: "at 16" -> CONFIRM book march 28 16:00 pending -> yes -> scritto.
3. **Silenzio, quarta occorrenza, sempre nello stesso stato**: COLLECTING con MISSING: TIME, verde, atto nascosto, schermo
   invariato dopo un si'/no/none. Nelle altre tre: 33 s, 20 s ("Are you there?" -> risposta), 20 s ("Absolutely"). Qui 56 s
   e nemmeno "Hello?" lo sveglia. In DONE, con lo schermo fermo 90 s, l'omni chiacchierava: non e' la finestra KV ne' il
   lampeggio, e' lo stato "manca l'ora" senza un atto che dica "chiedi l'ora". Il prompt "read the screen to know what to say"
   con uno schermo che non dice cosa dire = niente da dire.
4. **Estrattore**: "yeah so did you check" -> yes (domanda, non accettazione: ha aperto una prenotazione non voluta);
   "Which one?" -> set(april) dal contesto; "What's the next free slot?" -> nessun evento (deve essere set(check)).
5. **L'omni storpia le ore dette come numeri 24h** ("at 15" -> "2:15", "at 16" -> "4:16"): falso rosso "14:15 IS FREE" e poi
   il banner rilanciato come proposta ("the next free slot is at 2:15"). Non e' nostro: e' la pronuncia dei numeri dell'omni.
6. Finestra KV + lampeggio su 6 minuti: nessun degrado visibile (legge lo schermo alla lettera a 170 s, chiacchiera a 190 s).
