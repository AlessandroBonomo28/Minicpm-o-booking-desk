# Architettura del ramo FORCESPEAK-GOODTEST (07/09/2026) — come funziona e perche'

## In una frase
L'omni (MiniCPM-o 4.5 duplex) resta la voce e il cervello della conversazione; una macchina a stati deterministica tiene i
fatti e scrive nel DB; un LLM in background (σ) guarda la conversazione intera e, quando l'omni e' bloccato o fuori strada,
gli mette sullo schermo la frase da dire e gli apre il turno con il suo stesso token `<|speak|>`.

## I tre canali, ognuno nel posto per cui il modello e' addestrato
1. **Audio = solo il cliente.** Nessuna voce finta. Il trigger naturale del parlato dell'omni e' acustico (paper §3.1: l'utente
   entra nel flusso solo come env-audio; giuria del 06/09: 0/13 frame senza turno pendente hanno prodotto parlato).
2. **Pixel = lo schermo**, un frame da 448x448 a ogni chunk (lampeggio). Regola (07/09): lo schermo e' DOMANDA e RISPOSTA,
   al massimo tre righe, tutte pronunciabili al cliente cosi' come sono. Niente istruzioni per l'operatore: con force_speak
   il turno forzato e' una lettura letterale ("SAY: AVAILABLE" -> "I'm going to say available").
   - raccolta: `BOOK: APRIL` / `WHICH DAY?`; verifica sul mese: `IS IT FREE: APRIL` / `FREE, EXCEPT 1, 2, 3, 20, 25, 28` / `WHICH DAY?`
   - risultato: `APRIL 20, ALL DAY: FREE?` / `YES, EXCEPT 3 PM, 6 PM` / `BOOK IT?`;  `APRIL 20, 2 PM: FREE?` / `YES` / `BOOK IT?`
   - prenotazione: `BOOK APRIL 20, 2 PM?` / `FREE` / `SHALL I BOOK IT?` -> `BOOKED` oppure `TAKEN`
   - banner in alto: verde OK; giallo = la frase di aiuto di σ; rosso = fatto del DB ("NOTHING BOOKED YET", "18:00 IS TAKEN")
   - orari in forma parlata (`6 PM`), giorni occupati solo se la domanda e' sul mese, nessun elenco non richiesto.
3. **Token di controllo = il "quando".** `force_listen` (upstream) zittisce; `force_speak` (nostro, commit 31b5d52 su
   MiniCPMO45, specchio esatto di force_listen) apre il turno: a j=0, con il turno chiuso, `<|listen|>` -> `<|speak|>`.
   La sequenza e' quella di ogni onset naturale. Misurato: turno aperto in 0,5-1,2 s in 11 casi su 12.

## Il ciclo per ogni battuta del cliente
1. VAD a 300 ms di pausa -> ASR (Whisper large-v3-turbo) -> estrattore (gemini-3.5-flash-lite, harness v3, contratto
   set/yes/no/cancel, `yes` con citazione dell'accettazione, `any` per allargare la richiesta) -> evento alla FSM.
2. La FSM (gateway.py) aggiorna il record: merge in raccolta, verifica sul giorno o sul mese, prenotazione solo con un `yes`
   esplicito, idempotenza (stesso record = evento nullo), valori respinti mostrati, DB scritto solo dal codice.
3. Lo schermo cambia; l'omni risponde dalla voce e legge lo schermo (1,5-3 s dopo la fine della battuta).
4. A fine turno dell'omni (e 3 s dopo una battuta senza risposta) parte σ: conversazione intera, schermo, stato, tempi,
   CONTRATTO del sistema -> `verdict(status ok|stuck, kind, help, readback, claim)`.
   - i CLAIM (slot libero/occupato, prenotazione fatta) li verifica il CODICE sul DB: rosso se falsi, sempre esatto;
   - i readback riempiono i campi mancanti come valori tentativi, solo se il turno segue una battuta del cliente;
   - stuck (silent, off_context, repeating, ignores_screen, false_claim, cannot_do) -> giallo con la frase da dire.
5. Stuck o rosso -> `force_speak` sul chunk che porta lo schermo nuovo -> l'omni apre il turno e dice la frase / legge lo schermo.
   Guardie: UN solo aiuto tra due battute del cliente, tetto di due per stato (gialli e rossi), almeno 6 s tra due force,
   verdetti stantii scartati se la FSM e' cambiata durante il giudizio, mai un force nei primi 3 chunk o a turno aperto.

## Perche' cosi' (gli errori pagati)
- Frame che non svegliano l'omni (tutte le sessioni fino al 06/09) -> force_speak, non prompt, non banner, non audio finto.
- Testo iniettato nell'unita' = parole sue (07/09, "do you like cats" -> "I like cats"); testo di sistema = sfondo, non ordine.
- τ deterministica (force sul frame evento + latch + guardiano a tempo) -> parlava troppo, risposte doppie: scartata; decide σ.
- Atto e titoli da operatore sullo schermo -> letti alla lettera: via tutto, resta domanda e risposta.
- "18 TAKEN" + "OTHER HOURS FREE" su due righe -> invertito dall'omni: ora una riga, `YES, EXCEPT 6 PM`.
- Loop giallo/rosso/force -> un aiuto per battuta, tetto anche sui rossi.
- Valori inventati riciclati nel record dai readback -> accettati solo da turni che seguono la voce del cliente.
- Taglio della finestra KV: al tasso del caso (giuria), non e' una causa; basic 4000/3500 regge 6 minuti.

## Numeri di riferimento (sess_f0ab8867fc79)
estrattore 1,0-1,4 s · σ 0,8-1,2 s · force -> turno 0,6-0,7 s · 12 giudizi, 3 stuck fondati, 0 falsi sui filler ·
0 scritture sbagliate · 1 rosso esatto corretto a voce entro 1 s.

## Cosa resta aperto
bug #2 (lo slot occupato chiude la richiesta e la data si perde), nessun `unset` oltre a `any`, cloud lento a tratti
(fallback locale a 4 s), stato morto delle sessioni lunghe non riprodotto in questo ramo, hold e sticky (opzioni spente).
