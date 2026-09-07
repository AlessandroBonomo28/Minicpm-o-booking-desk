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
