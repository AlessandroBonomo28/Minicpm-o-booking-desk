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
