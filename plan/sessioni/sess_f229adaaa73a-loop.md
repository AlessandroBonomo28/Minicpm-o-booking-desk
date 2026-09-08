# Sessione sess_f229adaaa73a — 08/09 ~18:13, ramo FORCESPEAK-BETAGAMMA @ c823fc0 — "è andato in loop"
Config come GOODTEST-2 (σ ON, τ OFF, hold OFF, finestra basic 4000/3500, flash-lite). DB: aprile con 1, 2, 3, 15, 20, 25, 28 occupati (tutti parziali).

## Conversazione (2 min 20 s)
6.8   "Hello, how are you?" / 14.7 "I'd like to book a call." -> set(book) / 24.1 "book in April" -> set(book, april): tutto regolare, turni brevi.
33.2  "I don't know when is it free" -> set(check, day any)   schermo: FREE: APRIL | FREE, EXCEPT 1, 2, 3, 15, 20, 25, 28 | WHICH DAY?
34.4  turno 1 (12 s): "Okay, let me check. The 1st, 2nd, 3rd, 1 5th, 2 0th, 2 5th, ..."  legge la riga delle eccezioni; i numeri escono a
      cifre staccate ("1" "5th"): il tokenizer spezza le cifre e il TTS a unita' (25 token per secondo) le pronuncia separate.
57.3  "I don't know." -> set(check, day any) = invariato (nessun frame nuovo, stesso schermo)
56.9  turno 2 (23 s): "Okay, let me check again. The 4th, 5th, 6th, 7th, 8th, 9th ..."  ELENCA I GIORNI LIBERI (il complemento della riga).
85.2  "I don't know, I think..." -> none;  87.7 "pick one randomly" -> none  (nessun evento della macchina: il contratto non ha "scegli tu")
88.4  turno 3 (46 s, MAI chiuso): "Okay, let me pick one randomly for you. Okay, the 16th is available. Okay, let me check again. The 16th
      is available. Okay, let me pick one randomly for you. Okay, the 16th is available. Okay, let me check again. ..."  (backend.log)
      Per ogni unita': `<|speak|>` a j=0, is_listen=False, "incomplete result. hit max_new_token: 26" (413 unita' nella sessione al tetto di testo).
111.0 "Okay, okay, okay." / 122.5 "Okay, it is good. Let's check for 16." -> set(check, 16) -> CONFIRM check april 16 available
      schermo: APRIL 16, ALL DAY | FREE | WHAT TIME?  ma l'omni non lo legge: il turno e' ancora aperto e non cede la parola.
134.5 "Oh, I said okay. Stop." -> cancel -> IDLE. Sessione fermata a mano.

## Cosa NON c'entra
- La regola nuova (proposta -> tentativo) non e' mai scattata: σ ha giudicato i turni 1 e 2 "ok" (leggevano lo schermo) e il turno 3 non
  e' mai finito, quindi σ non e' stato chiamato; nessun aiuto, nessun force, nessuna scrittura. Stesso esito sarebbe uscito su GOODTEST-2.
- Il controllo di no_reply non parte mentre l'omni parla (giusto).

## Le cause, per struttura
1. **Un turno degenerato non ha nessuno che lo fermi.** Il nostro anello agisce solo ai confini del turno: σ a fine turno, force_speak a
   turno chiuso. Dentro un turno aperto la sola voce del cliente dovrebbe far scattare `<|listen|>` (paper §3.2), ma in degenerazione
   (ripetizione) il modello ha campionato `<|speak|>` a ogni secondo per 46 s ("Okay, okay, okay", "Let's check for 16", "Stop" ignorati).
2. **Lo stesso schermo, la stessa domanda, tre volte.** "I don't know" / "I don't know" / "pick one randomly" non cambiano lo stato: l'omni
   rirsponde alla stessa domanda con turni sempre piu' lunghi (12 -> 23 -> 46 s) finche' cade nel ciclo. I numeri costano molti token
   (cifre spezzate) e ogni unita' arriva al tetto di 26 token di testo: elencare giorni e' l'attivita' piu' fragile che gli chiediamo.
3. **"Scegli tu" non e' un evento della macchina.** L'estrattore (giustamente, per contratto) risponde `none`; la scelta resta tutta
   all'omni su uno schermo che dice WHICH DAY?. Nella run precedente aveva proposto il 15 (bene); qui ha elencato.

## Proposte (da decidere con Alessandro, non implementate)
A. **σ in corsa + taglio con force_listen.** Ogni ~8 s di turno aperto, σ riceve il testo parziale e la durata del turno: se dice stuck
   (repeating, off_context...) il client manda `force_listen` per un chunk (token di controllo dell'upstream, specchio del nostro
   force_speak): il turno si chiude, l'aiuto va sullo schermo, poi force_speak come oggi. Nessun timer sui turni sani: decide σ.
B. **Interruzione garantita (barge-in).** Se il cliente parla per >= 1,5 s sopra un turno aperto e il modello non cede entro 1 s, un
   `force_listen`. E' il comportamento per cui il modello e' addestrato, imposto dal suo stesso token quando non lo fa da se'.
C. **"Scegli tu" come capacita' del sistema.** Evento `set(day="pick")` (o "first free"): la macchina propone lei il primo giorno libero,
   schermo `BOOK: APRIL 4?` / `DOES THAT WORK?`, l'omni lo legge, il si' lega (regola gia' in produzione). L'omni non deve piu' inventare
   ne' elencare. Rientra nell'algebra ("spezziamo il compito in stati"), non e' una pezza.
D. (da osservare, non da fare ora) la riga del mese con 7 numeri: in GOODTEST letta bene una volta; il problema e' la ripetizione.

Registro: da questa run in poi il testo COMPLETO di ogni turno dell'omni finisce nel registro ("AI (turno completo): ...").
