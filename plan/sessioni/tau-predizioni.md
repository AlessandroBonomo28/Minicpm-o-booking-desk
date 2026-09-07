# Politica del turno τ (ramo forcespeak-stickyctx, 07/09) — predizioni PRIMA della prova
Architettura: audio = solo il cliente; pixel = fatti + ATTO sempre visibile; token di controllo = τ (force_speak sul frame evento a
turno chiuso, latch se il turno e' aperto, guardiano a 3,5 s; hold opzionale spento); testo di sistema = solo il prompt.
Guardie: readback accettati solo da turni che seguono una battuta del cliente (< 6 s); verdetto di heard scartato se la FSM e'
cambiata nel frattempo; max 2 forzature per stato, pausa 3 s, mai nei primi 3 chunk.

## Prova A: 10 eventi dal pannello a microfono coperto (book/check con data e ora, yes, cancel; DB seminato)
- turno aperto entro 1,5 s dal frame evento: >= 8/10; con "let me check" gia' in corso, latch e turno entro 1,5 s dalla chiusura.
- contenuto che legge lo schermo (valori, TAKEN/AVAILABLE/CONFIRMED, o la domanda dell'atto): >= 7/10.
- forzature sul lampeggio: 0; cicli (force -> giallo -> force oltre il tetto): 0; turni vuoti: <= 1.
- readback inventati nel record: 0 (i turni forzati senza battuta recente non entrano).

## Prova B: copione parlato (saluto, book, data, ora, si', lettura verbatim, TAKEN, saluto)
- nessun silenzio > 4 s dopo una tua battuta (guardiano + latch); risposta cieca possibile a 0,7-1,4 s (hold spento).
- invenzioni nella risposta cieca: <= 1 per run, corrette entro 3 s da un rosso/giallo + force.
- "let me check" con esito a schermo: se capita, il turno forzato successivo legge l'esito (<= 2 s dalla chiusura).
- 0 scritture sbagliate; 0 rossi falsi (i claim sul DB sono deterministici).
Se la prova B mostra >= 2 invenzioni cieche per run: accendere hold e ripetere lo stesso copione (variabile singola).

## Revisione 07/09 (Alessandro): la τ deterministica e' scartata, decide σ "stuck detector"
σ (LLM in background, conversazione intera + schermo + stato + tempi + CONTRATTO) a fine turno dell'omni e 3 s dopo una battuta
senza risposta -> ok | stuck {silent, off_context, repeating, ignores_screen, false_claim, cannot_do} + aiuto (max 10 parole).
Stuck o rosso sul DB -> aiuto sullo schermo + force_speak nudo. Tetto: due aiuti per stato della macchina. Rigiudizio contro
l'aiuto dato. Verifica sul mese (giorni occupati sullo schermo). Titolo "IS IT FREE?" al posto di "AVAILABILITY CHECK".
Sonde (flash-lite): off_context -> ASK FOR THE MONTH; "Are you there?" senza risposta -> silent; "Ummm" -> ok (2/2);
"I'll check the entire month" con i giorni occupati a schermo -> false_claim "READ THE BOOKED DAYS ON SCREEN"; lettura dei
giorni occupati -> ok; aiuto ignorato -> ignores_screen; "every Monday" -> cannot_do "SAY: I CAN ONLY CHECK ONE DAY";
tetto: giallo, giallo, poi verde e nessun force; stato nuovo -> il tetto riparte.
Predizioni dal vivo: una risposta per battuta (niente doppie domande); filler senza forzature; "all the month" -> l'omni legge i
giorni occupati; una bugia del tipo "I'll check" -> giallo + force entro 1,5 s dalla chiusura del turno e turno forzato che
legge lo schermo >= 2/3; mai piu' di due forzature sullo stesso stato; 0 readback inventati nel record.
Rischio non nostro: cloud lento stanotte (LLM 4-8 s, timeout di σ): l'estrattore cade sul fallback locale.
