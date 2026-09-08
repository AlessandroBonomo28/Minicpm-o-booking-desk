# Ramo FORCESPEAK-BETAGAMMA — predizioni scritte PRIMA del test dal vivo (08/09, pomeriggio)
Base: FORCESPEAK-GOODTEST-2 @ f29fcf6 (schermo slot / FATTO / domanda). Servizi riavviati dal ramo (tool agent e gateway; backend intatto).

## La causa (sess_41c874e48161)
Dopo "pick one randomly" l'omni fa la cosa giusta: "How about April 15th? Does that work?". σ lo vede (claim slot_free, giorno 15) e
il DB conferma il 15 libero, ma su GOODTEST-2 i valori di un claim NON entrano nel record: la proposta muore, lo schermo resta
`BOOK: APRIL / WHICH DAY?`. Il cliente dice "Uh, yes" -> `yes` in raccolta senza domanda aperta -> nulla. L'omni annuncia tre
volte la prenotazione (tre rossi giusti, tetto raggiunto); il cliente si sblocca solo ridicendo tutto da capo.
Il rosso curava il sintomo (l'annuncio falso), non la causa: il sì a una proposta dell'operatore non aveva un posto nella macchina.
Secondo difetto, a 136 s: σ ha dato stuck su "Yes, April 15th is available. What time would you like?" (esattamente la domanda
dello schermo) perché il client gli passava ancora come "aiuto precedente" l'indicazione di uno stato ormai superato.

## I tre cambi (ognuno una variabile, misurabile a banco)
1. **FSM (gateway.py, ramo heard/sigma)**: una PROPOSTA dell'operatore = claim `slot_free` con `claim_day` / `claim_time`, verificata
   sul DB (giorno non tutto occupato; ora libera), entra come tentativo marcato `"proposal"`. Solo in raccolta, solo sui campi
   mancanti, mai sopra un valore del cliente; un claim `slot_taken` / `booking_confirmed` non porta nulla. Schermo: `BOOK: APRIL 15?`
   / `DOES THAT WORK?` (il tentativo da readback resta `IS THAT RIGHT?`). Riga di stato per l'estrattore: "the desk PROPOSED day=15
   and asked whether that works. Open yes/no question". `yes` consolida (poi `WHAT TIME?`), `no` scarta, un valore del cliente vince.
   È la regola che avevo scritto su beta-gamma (3fb971c) e non avevo riportato nella ricostruzione da `demo`.
2. **Client (hud-app.js)**: l'aiuto precedente di σ si azzera quando la macchina cambia con una battuta del cliente (un aiuto vale per
   lo stato in cui è nato). Misurato a banco: con un aiuto stantio diverso dallo schermo, flash-lite dà la precedenza all'aiuto e
   dice stuck anche se il turno segue lo schermo; una frase nel prompt ("lo schermo vince") NON basta (provata e tolta). Quindi
   la cura è non mandare mai un aiuto stantio.
3. **Prompt di σ**: una proposta è claim slot_free ed è ok se lo schermo non mostra quel giorno/ora occupato; lo schermo poi la
   mostra col punto di domanda finché il cliente risponde; un turno che fa la domanda dello schermo è ok.

Banco: `tools/fsm_replay_test.py` 22/22 (replay locale della run con la regola nuova + casi negativi: giorno pieno, ora occupata,
valore del cliente già presente, fuori raccolta, no, correzione); `tools/sigma_probe.py` 10/10 (σ 7 + estrattore 3, flash-lite ~1 s).

## Predizioni per il test dal vivo (stesso copione: book, April, "pick one randomly")
- P1. Dopo "How about April 15th?" lo schermo passa entro ~1,5 s a `BOOK: APRIL 15?` / `DOES THAT WORK?` (σ ~1 s + un frame).
- P2. Il sì del cliente consolida: `BOOK: APRIL 15` / `WHAT TIME?`. Nessun "I've booked" a vuoto ripetuto: se l'omni annuncia
  la prenotazione prima del sì, rosso `NOTHING BOOKED YET` + force come prima, ma il sì successivo LEGA.
- P3. Ora detta -> `APRIL 15, 3 PM` / `FREE` / `SHALL I BOOK IT?` -> sì -> `BOOKED`. Una sola scrittura, solo dopo il sì.
- P4. Nessuno stuck falso su un turno che ripete la domanda dello schermo subito dopo una battuta del cliente.
- P5 (rischio accettato). Vedendo `DOES THAT WORK?` l'omni può ripetere la sua domanda (doppia domanda): non è un loop, σ non forza su ok.
- P6 (rischio, da osservare). Una proposta inventata in un turno forzato non informato ("April 17th") entra come tentativo se libera:
  lo schermo la mostra col `?`, il cliente decide con sì/no. È coerente (lo schermo segue ciò che il cliente ha sentito); se dà
  fastidio dal vivo è un dato da annotare, non da mitigare.
- P7. Proposta di un'ora ("how about 3 pm?") con giorno noto: entra solo se libera; se occupata, rosso `3 PM IS TAKEN` come prima.
Falsificazione: dopo il sì la macchina resta a `WHICH DAY?`; oppure entra una proposta occupata; oppure σ resta ok mentre l'omni
annuncia una prenotazione con la proposta ancora col `?`.

## Revisione (08/09 sera): 2 revisori (FSM; client+σ) + 22 sonde locali, presi in carico prima del test dal vivo
Sette segnalazioni valide, tutte sullo stesso asse (la proposta dell'operatore nella macchina):
1. Giorno PIENO proposto (in prenotazione lo schermo non elenca gli occupati): prima cadeva in silenzio -> ora rosso `APRIL 1 IS FULL`
   (il giorno verificato come l'ora; anche `APRIL 9 IS FREE` a chi dice occupato un giorno libero; ora occupata su giorno non nel record -> rosso).
2. Seconda proposta sopra una proposta ("sorry... how about the 17th?"): sostituisce la prima (il cliente risponde all'ultima sentita).
3. `any day` dopo una proposta: via anche il tentativo (lo schermo torna a WHICH DAY?).
4. `no` a una proposta in verifica: torna la riga del mese (FREE, EXCEPT ...), il record e' funzione dei campi, non del percorso.
5. Proposta che COMPLETA una prenotazione ("3 pm is free, shall I book it?"): va dritta alla conferma `APRIL 20, 4 PM / FREE / SHALL I BOOK IT?`,
   un solo si' (l'unico evento che scrive); il `no` toglie solo i campi proposti (giorno del cliente conservato) invece di annullare tutto.
6. Corsa: un si' arrivato PRIMA del verdetto di σ sulla proposta resta "slegato" 8 s e la proposta che entra dopo lo lega.
7. Mese della proposta: "How about April 15th?" a mese mancante entra (mese+giorno proposti); "May 15th" con il cliente su aprile ->
   rosso `APRIL, NOT MAY`. flash-lite non compila `claim_month` nemmeno se obbligatorio (misurato 3 volte): il gateway legge il mese
   nominato nel testo del turno (un fatto, non una forma).
8. Un turno che ha prodotto un evento (proposta entrata) non e' "stuck": σ non gli mette il giallo sopra (mai una domanda contraddittoria).
Trovato dal vivo e corretto: in `omni_turn` avevo confuso "record cambiato" con "semaforo cambiato": un giallo puro non avrebbe piu' forzato.
Banco: replay 42/42, sonde 12/12, API viva: giallo puro -> force; proposta entrata con σ stuck -> verde, niente force; annuncio falso -> rosso + force.
P7 cambia: proposta d'ora libera con giorno noto -> `SHALL I BOOK IT?` subito, il si' scrive. Non presa: alternativa dopo TAKEN (bug #2, da decidere).

## Fase 2 (08/09 sera, approvata da Alessandro: "vai 1 e 3"): σ in corsa + taglio, "scegli tu"
Causa (sess_f229adaaa73a): un turno degenerato (46 s, `<|speak|>` a ogni secondo) non ha nessuno che lo fermi, e "pick one randomly"
non è un evento della macchina. Due variabili nuove, misurabili a banco:
1. **σ in corsa + taglio** (client `midTurnCheck`, checkbox "σ in corsa", default ON): a 10 s di turno aperto e poi ogni 8 s, σ riceve il
   testo parziale (`reason: mid_turn`, `turn_s`); stuck → `force_listen` sul chunk successivo (nel modello: `<|turn_eos|>` + listen +
   reset TTS, cioè il turno si chiude pulito), audio fermato subito, poi a turno chiuso il verdetto del taglio va al semaforo con
   `reason: cut` (mai readback né claim nel record) → giallo con l'aiuto + force_speak con le guardie di sempre (un aiuto per battuta,
   6 s, tetto 2 per stato). Max 3 tagli per battuta del cliente. Sonde σ mid_turn 4/4: elenca → stuck, ripete → stuck, legge la riga
   dello schermo una volta → ok, risposta normale → ok.
2. **"Scegli tu"** (estrattore `day: 'pick'` / `time: 'pick'`; gateway `_hud_pick_fill`): la macchina propone il primo giorno senza
   prenotazioni (poi il primo non pieno) / la prima ora libera tra le 9 e le 18; entra come tentativo `proposal` (schermo
   `BOOK: APRIL 4?` / `DOES THAT WORK?`); `no` → il prossimo (il rifiutato è saltato); sì → solido; un valore del cliente o `any`
   chiude la delega; se il record si completa si va dritti al risultato (`APRIL 5, 9 AM / FREE / SHALL I BOOK IT?`, oppure per una
   verifica `APRIL 4, ALL DAY / FREE / WHAT TIME?`) con i marchi, così il `no` propone il successivo. L'omni che legge la proposta
   della macchina non produce un frame nuovo (stesso valore, stesso marchio). Estrattore: "pick one randomly", "I don't mind, you
   choose", "you pick the time" → pick; "when is it free?" resta una verifica (4/4).
Banco: replay 59/59 (`tools/fsm_replay_test.py`), sonde 20/20 (`tools/sigma_probe.py`), API viva: pick 4 → no → 5 → sì → pick ora 9:00
in conferma; turno tagliato → giallo con l'aiuto + force, record invariato.

### Predizioni (stesso copione della run in loop: book, April, "when is it free", "I don't know", "pick one randomly")
- P8. Un turno che elenca i giorni o si ripete viene tagliato a ~11 s (σ ~1 s + il chunk): l'audio si ferma, il turno si chiude,
  sullo schermo l'aiuto di σ, force_speak entro 1,5 s se in questa battuta non c'è già stato un force. Il turno 1 della run (lettura
  della riga in 12 s) è al margine: la sonda lo dà ok se legge la riga una volta e chiede il giorno.
- P9 (rischio). Dopo il taglio il turno forzato può riprendere il ciclo (il KV lo contiene ancora): σ taglia di nuovo (max 3 per
  battuta) e poi tace; la tua battuta successiva riparte pulita.
- P10. "pick one randomly" → `BOOK: APRIL 4?` / `DOES THAT WORK?` entro ~1,5 s (il 4 è il primo giorno senza prenotazioni nel DB
  vivo) → l'omni lo legge → sì → `WHAT TIME?` → "you pick" → `APRIL 4, 9 AM / FREE / SHALL I BOOK IT?` → sì → `BOOKED`.
  Un `no` fa passare al 5 (poi 6...) o alle 10 AM: nessun elenco, nessuna invenzione.
- P11. L'omni che legge "How about April 4th?" non cambia il record (nessun frame nuovo, nessun rosso).
Falsificazione: il taglio non chiude il turno (il modello riprende senza `<|turn_eos|>`) o l'audio continua; σ taglia un turno sano che
legge la riga; "pick one" non estratto (none).
