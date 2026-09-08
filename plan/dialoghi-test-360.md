# Dialoghi di prova a 360° — ramo FORCESPEAK-BETAGAMMA (08/09 sera, @ 321d59c)

Prima di partire: ricarica la pagina; σ ON, **σ in corsa ON**, τ OFF, hold OFF, sticky OFF; preset inglese; cuffie.
Dopo ogni dialogo: **Stop** e riparti (registro pulito, un file per sessione). Per leggere l'esito: `python3 tools/hud_run_log.py --conv`.

DB di stasera (tutte prenotazioni PARZIALI, nessun giorno pieno):
- marzo: 2 (3 PM, 6 PM), 3 (11 AM, 3 PM), 7 (6, 7 PM), 13 (9 AM), 16 (4 PM), 20 (3, 6 PM), 28 (1, 3, 4, 5 PM), 30 (3 PM), 31 (4 PM)
- aprile: 1 (3 PM), 2 (3, 5, 6 PM), 3 (6 PM), **4 (3 PM)**, 15 (3 PM), 20 (2, 3, 6, 7, 9 PM), 25 (6 PM), 28 (3, 6 PM)
- maggio: 3 (6 PM), 9 (3 PM) · novembre: 15 (6 PM) · dicembre 1, 3 · gennaio 2 · febbraio 2 · **giugno, luglio, agosto, settembre, ottobre: vuoti**
Primo giorno libero (senza prenotazioni): marzo 1, aprile 5, maggio 1, novembre 1. Prima ora libera dello sportello: 9 AM.
Per avere un **giorno pieno** (rosso `IS FULL`): dal pannello, intent book, esito "forza BOOKED", giorno senza ora, poi conferma.

Legenda: **TU** = cosa dici · **SCHERMO** = righe attese · **OMNI** = cosa dovrebbe dire · **PASSA SE** = criterio. Le battute
in corsivo sono varianti da provare la seconda volta.

---

## A. Base: prenotazione liscia (linea di riferimento)
1. TU "Hello, I'd like to book a call." → SCHERMO `BOOK: ?` / `WHICH MONTH?` → OMNI chiede il mese.
2. TU "In May." → `BOOK: MAY` / `WHICH DAY?`
3. TU "The twelfth." → `BOOK: MAY 12` / `WHAT TIME?`
4. TU "Half past ten." → `MAY 12, 10:30 AM` / `FREE` / `SHALL I BOOK IT?` → OMNI "Shall I book it?"
5. TU "Yes." → `MAY 12, 10:30 AM` / `BOOKED` / `ANYTHING ELSE?`
6. TU "No, thanks. Bye." → OMNI saluta, nessun evento.
PASSA SE: una sola scrittura, dopo il tuo sì; nessun rosso; nessun force (o al massimo un `silent` se tardi a rispondere).

## B. Verifica sul mese → "scegli tu" (il copione della run perfetta, con le varianti)
1. TU "I'd like to book in April." → `BOOK: APRIL` / `WHICH DAY?`
2. TU "When is it free?" → `FREE: APRIL` / `FREE, EXCEPT 1, 2, 3, 4, 15, 20, 25, 28` / `WHICH DAY?` → OMNI legge la riga UNA volta.
   PASSA SE: nessun elenco dei giorni liberi; σ in corsa a 10 s dice ok (o il turno finisce prima).
3. TU "I don't know, you pick." → `APRIL 5, ALL DAY` / `FREE` / `WHAT TIME?` (il 5 è il primo giorno senza prenotazioni; la
   proposta completa la verifica → risultato diretto). OMNI "April 5th, all day free. What time?"
4. TU "No, another day." → `no` → `APRIL 6, ALL DAY` / `FREE` / `WHAT TIME?` (il 5 saltato). *Ripeti "no" due volte: 7, poi 8.*
5. TU "Fine. You pick the time too." → in verifica l'ora non si propone: schermo invariato, OMNI chiede l'ora (annotato).
6. TU "At 3 pm." → `APRIL 8, 3 PM` / `FREE` / `SHALL I BOOK IT?`
7. TU "Yes, book it." → `BOOKED`.
PASSA SE: mai un numero inventato dall'omni; ogni `no` fa avanzare di un giorno; una sola scrittura.

## C. "Scegli tu" in prenotazione, con l'ora delegata (conferma diretta)
1. TU "Book a call in November." → `BOOK: NOVEMBER` / `WHICH DAY?`
2. TU "Pick one randomly." → `BOOK: NOVEMBER 1?` / `DOES THAT WORK?` → OMNI "How about November 1st? Does that work?"
   PASSA SE: σ dà claim slot_free giorno 1 e NESSUN frame nuovo (registro: "FSM → ... invariato" o nessuna riga FSM).
3. TU "Yes." → `BOOK: NOVEMBER 1` / `WHAT TIME?`
4. TU "Whatever is free, you choose." → `NOVEMBER 1, 9 AM` / `FREE` / `SHALL I BOOK IT?` (conferma diretta, un solo sì)
5. TU "No, later." → `no` → `NOVEMBER 1, 10 AM` / `FREE` / `SHALL I BOOK IT?` (il giorno resta; solo l'ora cambia)
6. TU "Yes." → `BOOKED`.
PASSA SE: il `no` all'offerta NON annulla la richiesta (giorno conservato); il sì scrive subito.

## D. Delega col mese mancante
1. TU "I need an appointment, you choose the day." → `BOOK: ?` / `WHICH MONTH?` (la delega è ricordata) → OMNI chiede il mese.
2. TU "June." → `BOOK: JUNE 1?` / `DOES THAT WORK?` (giugno vuoto → il primo).
3. TU "No, the 9th." → `BOOK: JUNE 9` / `WHAT TIME?` (il tuo valore vince, delega chiusa).
4. TU "9 am." → `JUNE 9, 9 AM` / `FREE` / `SHALL I BOOK IT?` → TU "Yes." → `BOOKED`.

## E. Proposta DELL'OMNI (non della macchina) e il sì che la lega
Serve che l'omni proponga da solo: non dire "pick", di' che non sai.
1. TU "Book something in May." → `BOOK: MAY` / `WHICH DAY?`
2. TU "Mmm, I really don't know." (nessun evento) → aspetta: l'omni di solito propone ("How about May 10th?").
   → `BOOK: MAY 10?` / `DOES THAT WORK?` entro ~1,5 s dal suo turno.
   *Se l'omni chiede di nuovo "which day?" e non propone: TU "Suggest me one."* (può diventare `pick`: va bene lo stesso).
3. TU "Uh, yes." → `BOOK: MAY 10` / `WHAT TIME?`  ← il punto che falliva nella run di April 15.
4. TU "4 pm." → `MAY 10, 4 PM` / `FREE` / `SHALL I BOOK IT?` → TU "Yes." → `BOOKED`.
PASSA SE: il sì alla proposta dell'omni lega; nessun "I've booked" a vuoto; nessun rosso.
Variante E2: al passo 3 di' "Yes" *subito, sopra la fine della sua frase*: il sì può arrivare prima del verdetto di σ; PASSA SE
entro 8 s il giorno diventa solido comunque (registro: "yes slegato" poi la proposta che lo lega).
Variante E3: al passo 2, se l'omni propone e poi TU "No, the 17th." → `BOOK: MAY 17` / `WHAT TIME?`.
Variante E4: dopo la proposta, TU "Any day is fine, what's free?" → `FREE: MAY` / `FREE, EXCEPT 3, 9` / `WHICH DAY?` (la
proposta e la delega spariscono, torna la riga del mese).

## F. Slot occupato e correzioni
1. TU "Book April 4th at 3 pm." → `APRIL 4, 3 PM` / `TAKEN` → OMNI "Sorry, 3 pm is taken."
2. TU "Then at 4 pm." → `APRIL 4, 4 PM` / `FREE` / `SHALL I BOOK IT?` (annotato come bug #2: se invece torna a `WHICH MONTH?`,
   è il difetto noto "slot occupato chiude la richiesta").
3. TU "Actually make it 5 pm." → `APRIL 4, 5 PM` / `FREE` / `SHALL I BOOK IT?` (correzione in conferma, nessuna scrittura).
4. TU "No." → `BOOKING NOT CONFIRMED` (richiesta annullata: è il contratto per un `no` su valori tuoi).
5. TU "Is the 20th free in April?" → `APRIL 20, ALL DAY` / `FREE, EXCEPT 2 PM, 3 PM, 6 PM, 7 PM, 9 PM` / `WHAT TIME?` → OMNI la
   legge con la polarità giusta ("free except...").
6. TU "3 pm." → `APRIL 20, 3 PM` / `TAKEN`.
7. TU "Forget it." → `REQUEST CANCELLED`.

## G. I rossi (l'omni che afferma il falso) e il giorno pieno
Prima crea un giorno pieno: pannello → book, "forza BOOKED", **April 10** senza ora → sì.
1. TU "Book in April, you pick." → la macchina propone il 5 (mai il 10).
2. TU "No... how about the 10th?" → `set(day 10)` → `APRIL 10` ... → `TAKEN` (giorno pieno).
3. TU "Book May 9th at 3 pm." → `TAKEN`; se l'omni dice "3 pm is free" → ROSSO `15:00 IS TAKEN` + force → si corregge.
4. In una conferma (`SHALL I BOOK IT?`) resta in silenzio 4-5 s: se l'omni annuncia "booked" da solo → ROSSO
   `NOTHING BOOKED YET` + force → "Sorry, nothing is booked yet. Shall I book it?" → TU "Yes." → `BOOKED`.
5. Con la macchina su aprile, se l'omni propone un giorno di un altro mese ("May 15th") → ROSSO `APRIL, NOT MAY`.
PASSA SE: ogni rosso è vero rispetto al DB e l'omni si corregge a voce entro 1,5 s; mai due force di fila senza una tua battuta.

## H. Turno degenerato → taglio (σ in corsa)
1. TU "Check March." → `FREE: MARCH` / `FREE, EXCEPT 2, 3, 7, 13, 16, 20, 28, 30, 31` / `WHICH DAY?` → OMNI legge (10-12 s, ok).
2. TU "List me all the free days one by one, slowly." → l'omni elenca: a ~11 s σ in corsa → **TAGLIO**: audio fermo, turno
   chiuso, schermo `⚠ <aiuto>` (es. "Which day in March would you like?"), force → l'omni dice l'aiuto.
   PASSA SE (registro): "σ in corsa ... STUCK repeating → TAGLIO", "TAGLIO: force_listen sul chunk #", "turno tagliato dopo N s",
   poi "FORCE_SPEAK ... turno aperto a +<1,5 s". Se il turno forzato riprende l'elenco: secondo taglio, al massimo tre, poi tace.
3. TU "The 5th." → `MARCH 5, ALL DAY` / `FREE` / `WHAT TIME?` (il cliente riparte pulito).
Variante H2: "I don't know" tre volte di fila sullo stesso schermo del mese (il copione della run in loop): PASSA SE nessun turno
supera i ~12 s senza taglio.

## I. Fuori contesto, silenzi, ripetizioni (i tre `stuck` classici)
1. TU "Can you book me a hotel room?" → σ off_context/cannot_do → giallo "I can only book a time slot. Which day?" + force.
2. TU "What's the weather like?" → stessa cosa (o l'omni rifiuta da solo: ok).
3. TU "Book in July." → `WHICH DAY?`; poi TU "um..." e basta → nessun force (filler); TU "So?" → σ no_reply silent → force.
4. Dopo un `BOOKED`, TU "Great, thanks." → se l'omni ripete "booked. Anything else?" → σ repeating → "Please tell me what you need."
PASSA SE: un solo aiuto tra due tue battute; niente force sui filler.

## J. Sopra la voce (barge-in naturale) e cambio di mese in corsa
1. TU "Check availability for March." → mentre l'omni legge le eccezioni, TU "No wait, November." → l'omni dovrebbe cedere;
   `FREE: NOVEMBER` / `FREE, EXCEPT 15` / `WHICH DAY?`; se l'omni finisce marzo, σ a fine turno → ignores_screen → force → legge novembre.
2. TU "The 15th at 6 pm." → `NOVEMBER 15, 6 PM` / `TAKEN` (prenotata stasera).
3. TU "7 pm then." → `FREE` / `SHALL I BOOK IT?` → TU "Yes." → `BOOKED`.

## K. Orari e numeri difficili (ASR + normalizzazione)
Su `BOOK: AUGUST <giorno>` prova, uno per volta, e guarda la riga 1 dello schermo:
"quarter past nine" → 9:15 AM · "quarter to six" → 5:45 PM · "twenty past two" → 2:20 PM · "at 15" → 3 PM · "nine in the
morning" → 9 AM · "seven" (senza am/pm) → 7 PM (sportello: 1-7 = pomeriggio) · "noon" → 12 PM · "the twenty-second" → 22 ·
"the second" → 2 · "next Monday" → nessun valore (data relativa senza riferimento: lo schermo non cambia, l'omni chiede la data).
PASSA SE: ogni valore entra giusto o resta fuori; mai un valore sbagliato che finisce in `SHALL I BOOK IT?`.

## L. Sessione lunga (finestra KV, memoria di σ)
Concatena A + B + C senza fermarti (5-6 minuti). PASSA SE: nessuna sessione morta (l'omni risponde fino alla fine), i force
restano fondati, nessun valore di una richiesta precedente rispunta in quella nuova.

## M. Filler e cinese (solo osservazione)
Rispondi "uhm... ehm... uhm" a due domande di fila, poi un valore. Annota se la pronuncia scivola in cinese (accettato); PASSA SE
il testo resta inglese e lo schermo non cambia sui filler.

---

## Cosa guardare nel registro, dopo
```bash
python3 tools/hud_run_log.py --conv | grep -v 'KV pruned\|FINESTRA'
```
e nel file `logs_demo/hud_runs/latest.log`: righe `σ (`, `σ in corsa`, `TAGLIO`, `FORCE_SPEAK`, `SEMAFORO`, `FSM →`.
Da segnare per ogni dialogo: scritture (giuste/sbagliate), rossi (veri/falsi), force (fondati/no), tagli, turni oltre 12 s,
valori entrati sbagliati, "sì" caduti nel vuoto.
