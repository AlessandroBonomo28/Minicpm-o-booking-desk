# Sessione sess_0afd7f7d2788 — ramo hud-semaforo-2 (05/09 sera)
Correzioni del ramo -2 confermate (niente falso giallo su "the 28th"; PARTIAL letto giusto: "the 6 p.m. slot is taken").
Difetti emersi: (1) silenzio di 20 s dopo "Absolutely" (offerta accettata, MISSING: TIME in verde: l'atto non c'è);
(2) "the 7 p.m. slot is also taken" con le 19 libere: inventato, verde (nessuna regola); (3) "3 p.m." respinto NON VALID
dal parser (i punti di p.m.) → giro a vuoto; (4) dal rumore ASR l'estrattore ha tirato fuori 12:02; due timeout cloud e
ASR a 1-2 s con il frame costante. Nessuna scrittura sbagliata.

## Ramo hud-semaforo-fixrules (risposta ai punti 2 e 3, e al principio "regex e parser sono instabili col linguaggio")
- **La normalizzazione la fa il modello cloud**, in formato canonico (mese in minuscolo, giorno in cifre, ora HH:MM); il
  gateway è un **verificatore**: accetta il canonico subito, altrimenti passa al parser a regole (solo locale verbatim e
  form manuale), riordinato (a.m./p.m./o'clock prima dei punti) e coperto da `tools/test_norm.py` (40/40).
- **Il supervisore non usa più regex sul testo dell'omni**: `heard` traduce il turno in un `claim` canonico
  (slot_taken / slot_free / slot_invalid / booking_confirmed + claim_time) e il codice lo verifica contro il DB:
  "7 pm is also taken" con le 19 libere → rosso `19:00 IS FREE`; "6 PM is available" con le 18 occupate → rosso
  `18:00 IS TAKEN`; "3 pm is not valid" → rosso `15:00 IS FREE`; "confirmed" senza scrittura → rosso. I valori di un
  claim non entrano nel record (non sono una ripetizione). `heard` gira su ogni turno dell'omni.
- Regressioni invariate: base 52/55, dialogo 24/24; normalizzatore 40/40.
