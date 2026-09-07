# Sessione sess_f0ab8867fc79 — 07/09 ~23:55, ramo forcespeak-stickyctx @ 8cf0b2a → salvata come FORCESPEAK-GOODTEST
"È la prova migliore fino ad ora in assoluto" (Alessandro).
Config: prompt "You are in duplex mode... You are the operator of a booking desk. ALWAYS SPEAK, read the screen to know what to say";
σ stuck detector ON; force automatico τ OFF; hold OFF; sticky OFF; finestra basic 4000/3500; blink ON; Whisper large-v3-turbo;
estrattore flash-lite harness v3; DB: aprile con 1, 2, 3, 20, 25, 28 occupati (il 20: 15, 18, 19, 21).

## Conversazione (2 min 43 s)
5.8   "Hello, how are you?"            -> nessun evento; omni "I'm good, thank you. How can I help you today?"
15.7  "I'd like to book a call."       -> set(book)             schermo: BOOK: ? | WHICH MONTH?        omni "Sure, which month would you like to book?"
26.1  "I'd like to book in April."     -> set(book, april)      schermo: BOOK: APRIL | WHICH DAY?      omni "Okay, which day would you like to book?"
37.5  "I don't know, when is it available?" -> set(check)       schermo: IS IT FREE: APRIL | FREE, EXCEPT 1, 2, 3, 20, 25, 28 | WHICH DAY?
                                          omni "It's available except for the 1st, 2nd, 3rd, 20th, 25th, and 28th."  (LEGGE il mese)
47.7  σ: stuck silent -> "Which day in April would you like?" -> giallo + force -> omni "Which day would you like?" (+0.6 s)
55.6  "Um..."                          -> nessun evento, nessun force (giusto)
59.1  "20"                             -> set(day 20)           schermo: APRIL 20, ALL DAY: FREE? | YES, EXCEPT 3 PM, 6 PM, 7 PM, 9 PM | BOOK IT?
                                          omni "It's available all day except for 3:00 PM, 6:00 PM, 7:00 PM, 9:00 PM"  (LEGGE il parziale, polarita' giusta)
74.1  "Ummm, yes."                     -> yes -> COLLECTING book april 20   schermo: BOOK: APRIL 20 | WHAT TIME?   omni "What time..."
83.5  "uh seven"                       -> set(time 19:00) -> DONE TAKEN     schermo: BOOK APRIL 20, 7 PM? | TAKEN   omni "I'm sorry, 7:00 PM is taken."
91.7  "When is it free?"               -> set(check) da DONE (riparte da zero: bug #2 noto)   schermo: IS IT FREE: ? | WHICH MONTH?   omni "Which month?"
      σ: stuck ignores_screen -> "April 20th is free except 3 pm, 6 pm, 7 pm, and 9 pm." -> giallo + force -> omni la dice
100.0 "April" -> check april (giorni occupati a schermo); 108.1 "twenty twenty" -> check april 20 parziale; omni lo rilegge giusto
123.0 "so um 2 p.m."                   -> set(time 14:00)       schermo: APRIL 20, 2 PM: FREE? | YES | BOOK IT?
      omni "Okay, I'll book it for you."  -> σ claim booking_confirmed -> DB: ROSSO "NOTHING BOOKED YET" + force
      -> omni "Sorry, nothing is booked yet."  -> σ: stuck false_claim, aiuto "April 20th at 2 PM is free. Shall I book it?"
      -> giallo, ma NESSUN altro force: un solo aiuto tra due battute del cliente ("tocca al cliente")
159.8 "Yes, book it."                  -> yes -> DONE BOOKED april 20 14:00 (scritto)   omni "Okay, it's booked."

## Cosa ha funzionato (misurato)
- Prenotazione scritta giusta, zero scritture sbagliate; rosso del DB esatto e corretto a voce dall'omni entro 1 s.
- Lo schermo domanda/risposta letto correttamente in tutti gli stati: mese, giorno parziale ("except 3 PM, 6 PM..."), TAKEN, BOOKED.
- σ: 12 giudizi, 3 stuck fondati (silenzio dopo una domanda, schermo ignorato, annuncio falso), 3 verdetti stantii scartati
  (la FSM era cambiata durante il giudizio), 0 falsi allarmi sui filler ("Um...", "Ummm, yes").
- force_speak: 3 forzature, turno aperto a +0,6 / +0,6 / +0,7 s, contenuto = la frase di aiuto o lo schermo; nessun loop
  (dopo "Sorry, nothing is booked yet" il secondo aiuto e' rimasto solo sullo schermo finche' non ha parlato il cliente).
- Latenze: estrattore 1,0-1,4 s (due punte a 3,2-3,9 s per l'ASR), σ 0,8-1,2 s, risposta informata 1,5-3 s.
- Residui noti: "When is it free?" dopo un TAKEN riparte da zero (bug #2, aggirato chiedendo di nuovo mese e giorno);
  l'omni dice "I'll book it for you" prima del si' (il rosso lo corregge); una σ a 6,6 s (cloud) scartata come stantia.
