# Sessione sess_14993ad6e097 — ramo hud-semaforo-fixrules (06/09 notte), letta dal registro logs_demo/hud_runs/
Config: fixrules d84293d (no-store, heard su ogni turno, supervisore sui claim), turbo, cloud flash-lite, finestra 4000/3500, blink.
DB: march 28 15:00 occupato (run precedente), march 29 tutto libero.

## Conversazione (essenziale)
14.0  "I'd like to book a call"        set(book)                -> COLLECTING manca month,day,time
27.4  "book in 28"                     set(book, day 28)        -> manca month,time
35.0  "March"                          set(month march)         -> manca time; omni "March 28th, what time?"
45.5  "look at 15"                     set(time 15:00)          -> DONE TAKEN (vero: 15:00 occupato). omni "already taken"
57.1  "Yeah, when is free?"            set(check)               -> COLLECTING check da ZERO (data persa)  <-- punto 2
69.0  "the next day"                   set(day 29)              (indovinato dal contesto del dialogo)
75.6  omni "that would be March 29th"  heard month=march        -> DATE: MARCH? 29
80.4  "Um..."                          set(check, day "next day") (inventato dal contesto) -> CONFIRM check march 29 AVAILABLE
92.5  omni "no bookings on March 29"   claim slot_free (vero)   verde
104.1 "I'll book it for that day"      yes                      -> COLLECTING book march 29 manca time; OMNI MUTO 20 s
116.4 "yeah book it for that day"      yes                      invariato, muto; 125 "Are you there?" -> "Yeah, I'm here. What time?"
160.6 "book at 15"                     set(book, time 15:00)    -> CONFIRM PENDING, ma SCHERMO: "BOOKING | MARCH 29 15:00 | SLOT TAKEN"  <-- BUG RESA
168.3 omni "the 15 slot is taken"      claim slot_taken 15:00   -> ROSSO 15:00 IS FREE (giusto sul DB, contro lo schermo)
173.5 "But you told me it was free"    set(book, 15:00) (eco)   -> ricalcolo identico contato come cambio -> VERDE; omni ripete l'errore
187.6 "when is it free in march"       set(month march)         invariato; omni "I can only see March 29"
200.9 "remove the time"                set{}                    nulla: NON ESISTE UN EVENTO DI RIMOZIONE  <-- punto 3
206.3 omni "removed the time, book at 15:30?"  claim slot_free 15:30 vs solido 15:00 -> giallo

## Analisi
1. **Bug di resa (certo, dal 04/09)**: in `themeFor` il ramo `intent === 'book'` (SLOT TAKEN / BOOKING DONE) precede il ramo
   CONFIRM: ogni prenotazione in attesa del si' e' resa "BOOKING / <slot> / SLOT TAKEN" invece di "WAIT FOR USER CONFIRMATION /
   BOOKING FOR <slot>? / SAY YES TO BOOK". Su main non si vedeva: l'atto "ASK: CONFIRM BOOKING" in alto guidava l'omni.
   In verde (semaforo) l'atto e' nascosto e resta solo la meta' sbagliata. Spiega anche la run precedente
   (sess_883c0f120263: "3 p.m.? already taken" con 15:00 libero), attribuita a torto a un'invenzione dell'omni.
2. **Slot occupato = richiesta chiusa**: "when is free?" riparte da zero e la data va persa. Proposta: occupato = valore
   respinto dell'ora (come NOT VALID), si resta in raccolta con mese/giorno; la verifica si fonde col record.
3. **Nessun evento di rimozione**: "remove the time" cade nel vuoto; `no` in CONFIRM di prenotazione fa un reset totale.
4. **Idempotenza violata**: un set che riproduce lo stesso record viene contato come cambio e spegne il rosso.
5. **Silenzio dopo il si' all'offerta** (terza occorrenza nello stesso punto): schermo "NEW BOOKING / MISSING: TIME" senza atto.
6. Minori: primo ASR 11,6 s (nessun warm-up del turbo); tre HTTP 500 da Cline etichettati "local (fallback)" con --no-local;
   l'estrattore inventa argomenti dal contesto ("Um..." -> set(check,"next day"); "But you told me..." -> set(book,15:00)).
Nessuna scrittura sbagliata nel DB.
