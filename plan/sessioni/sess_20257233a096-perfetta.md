# Sessione sess_20257233a096 — 08/09 ~18:49, ramo FORCESPEAK-BETAGAMMA @ 449011a — "run perfetta" (Alessandro)
Config: prompt "You are in duplex mode... You are the operator of a booking desk. ALWAYS SPEAK, read the screen to know what to say";
σ ON, σ in corsa ON, τ OFF, hold OFF, sticky OFF, finestra basic 4000/3500, Whisper large-v3-turbo, estrattore flash-lite harness v3.
DB: aprile con 1, 2, 3, 15, 20, 25, 28 occupati (parziali), novembre vuoto.

## Conversazione (4 min 13 s, due prenotazioni scritte: april 4 15:00, november 15 18:00; zero scritture sbagliate)
6.4   "Hello, how are you?"                    omni "I'm fine. How can I help you?"
16.5  "I don't know what can you do?"          omni "I can help you book your tickets or hotel room" -> σ STUCK off_context -> giallo
      "I can only book a time slot. Which day would you like?" + force -> omni la dice (+2.0 s). Secondo stuck a 28.6 non forzato (6 s).
41.4  "I'd like to book..." -> set(book)        schermo BOOK: ? | WHICH MONTH?   omni "Okay. Which month?"
47.8  "in April" -> set(april)                  BOOK: APRIL | WHICH DAY?         omni "April. Which day?"
56.2  "I don't know which one are available" -> set(book, day PICK) -> la MACCHINA propone il 4: BOOK: APRIL 4? | DOES THAT WORK?
      omni "Okay. April 4th. Does that work?"  (σ: claim slot_free 4 = la proposta gia' a schermo -> nessun frame nuovo)
68.2  "What are all the days [available] in April?" -> set(check, april, any)   FREE: APRIL | FREE, EXCEPT 1, 2, 3, 15, 20, 25, 28 | WHICH DAY?
      omni "Okay. Free except 1, 2, 3, 15, 20, 25, 28. Which day?"  (8 s, legge la riga UNA volta: niente elenco, niente taglio)
81.5  "Ummm..." -> set(april, any) = invariato (allucinazione innocua dell'estrattore su un filler)
85.4  "Pick one, I don't know." -> set(day PICK) -> risultato diretto: APRIL 4, ALL DAY | FREE | WHAT TIME?   omni lo legge
101.0 "I don't know which time are free" -> set(time PICK): in CONFIRM check non c'e' ora da proporre (verifica) -> invariato; omni "All day free. What time?"
111.7 "At 15." -> CONFIRM check april 4 15:00   APRIL 4, 3 PM | FREE | SHALL I BOOK IT?   omni "April 4th, 3 p.m. free. Shall I book it?"
121.5 "Um, okay, yes." -> yes -> DONE BOOKED april 4 15:00   omni "April 4th, 3 p.m. booked. Anything else?"
134.1 "Can you check availability for March?" -> check march (mese a schermo)  omni legge le eccezioni di marzo (12 s)
      146.2 σ in corsa a 10 s: ok (sta leggendo la riga)  -> NESSUN TAGLIO (giusto)
143.6/146.7 "No, actually... for November" (detto SOPRA il turno di marzo) -> check november  FREE: NOVEMBER | ALL DAYS FREE | WHICH DAY?
      σ a fine turno: STUCK ignores_screen (il turno finiva su marzo, lo schermo era gia' novembre) -> aiuto + force -> omni
      "Free for November, all days free. Which day would you like?" (+0.8 s)
160.7 "I don't know." / 163.8 "is it from" -> nulla; 165.1 σ no_reply: STUCK silent -> force -> omni ripete la domanda del giorno
181.7 "the 15" -> CONFIRM check november 15 all-day   omni "November 15th, all day free. What time?"
      (190.1 giallo CHECK THE SCREEN: readback time="any" di σ ("all day") contro 'all-day' del record: falso allarme innocuo, da normalizzare)
194-197 "Um..." "Ummm..." -> 199.6 σ no_reply STUCK silent -> force; 200.2 "yeah at 18" -> CONFIRM 18:00   omni "6 p.m. free. Shall I book it?"
211.2 "uh yes yes" -> yes -> DONE BOOKED november 15 18:00   omni "booked. Anything else?"
223-226 "Ah, good... Thank you." -> omni ripete "booked. Anything else?" -> σ STUCK repeating -> force -> "Please tell me what you need."
240.8 "No, I don't need anything anymore." -> "Okay." ; 251.7 "bye bye" -> "Bye bye."

## Cosa ha funzionato (misurato)
- "Scegli tu": due volte (56.2 e 85.4) la macchina ha proposto il 4 e l'omni ha letto la proposta; nessun elenco, nessuna invenzione.
- σ: 4 force, tutti fondati (off_context, cambio di mese sopra il turno, silenzio x2, ripetizione); 2 stantii scartati; 2 timeout cloud innocui.
- σ in corsa: 1 controllo (marzo, 10 s), ok: il taglio non e' scattato su un turno sano. Nessun turno oltre i 12 s.
- Schermo: letto in tutti gli stati; risultato diretto della proposta (APRIL 4, ALL DAY / FREE / WHAT TIME?) capito al volo.

## Da annotare
- 190.1: readback time="any" -> giallo CHECK THE SCREEN (falso allarme): normalizzare 'any'/'all day' nel confronto dei readback.
- 101.0: "which time are free" in verifica -> set(time pick) senza effetto (in una verifica l'ora non si propone): l'omni ha comunque chiesto l'ora, fine.
- Una volta la pronuncia e' uscita cinese (audio, non testo: nel registro e nel backend non c'e' un carattere CJK): vedi spiegazione in chat/calendar.
- Cifre ancora spezzate nel parlato ("2 8", "3 1st", "Sha ll", "book ed"): tokenizer a cifre + TTS a unita' di 1 s (upstream).
