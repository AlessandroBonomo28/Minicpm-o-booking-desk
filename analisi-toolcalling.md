# Tool calling a lato dell'omni — sviluppo, misure e decisioni (03–05/09/2026)

Sintesi ragionata di `plan/ramo-hud.md` sul solo tema "estrattore di richieste" (tool calling). Il modello vocale
(MiniCPM-o 4.5) non fa tool calling nativo (testato 03/09: ha template e token `<tool_call>` ma inventa la risposta):
il tool calling lo fa un **modello separato** che legge la trascrizione dell'utente e alimenta una macchina a stati;
l'omni vede lo stato sullo schermo (frame).

## 1. Architettura finale
```
VAD (browser, fine della battuta) → ASR whisper small GPU (0,05-0,3 s) → estrattore: request(intent, month, day, time)
→ FSM nel gateway (stati IDLE / COLLECTING / CONFIRM / DONE) → schermo (frame con il chunk successivo) → l'omni legge
```
- **L'estrattore non tiene stato**: riceve SOLO la battuta corrente + una riga di stato. La FSM (codice) fa merge dei
  campi, decide cosa manca, valida (mese = nome, giorno 1-31, ora HH:MM), esegue sul DB, transita.
- **Campi indipendenti dall'ordine** (mese, giorno, ora arrivano in qualunque combinazione); mese parziale
  (`DATE: APRIL ?`), giorno parziale (`DATE: ? 2`), campo respinto → ri-chiesto; un numero secco è la risposta alla
  domanda che lo schermo sta facendo (giorno, poi ora); un solo numero non è insieme giorno e ora.
- **CONFIRM** (verifica con posto libero): lo stato porta la data offerta → "yes"/"that day"/"the 6th"/"at 3 pm" si
  risolvono da stato + frase. **DONE** (chiuso): nessun valore all'estrattore. COLLECTING: solo i nomi dei campi.
- Regressioni: `tools/tool_agent_eval.py` (55 casi base) e `tools/tool_agent_eval_dialog.py` (20 casi di dialogo),
  entrambe con punteggio "effettivo" (dopo le regole di instradamento della FSM).

## 2. Come ci siamo arrivati: i cinque errori dello stesso tipo (Qwen3-1.7B)
Ogni ingresso in più è diventato una fonte da cui copiare valori, nonostante il prompt lo vietasse:
| ingresso dato al modello | errore osservato | rimedio (strutturale) |
|---|---|---|
| righe dell'operatore | "let me think" → check(May 5, 9) preso dall'operatore | tolte |
| battute utente precedenti | "is it free?" → check(May, 15) dai turni prima | solo la battuta corrente |
| campi dell'ultimo esito nello stato | "thank you" → book(April 2, 15:00) → doppione | DONE senza valori |
| date d'esempio nel prompt | "book a visit" → date "March 31" | niente esempi copiabili |
| campo obbligatorio nello schema | ora inventata 00:00 | campi nullable, intent con enum |
Altri: tre strumenti separati → riempiva a forza ("none", frase intera) → **un solo strumento** `request(intent∈{none,
check,book,cancel}, month|null, day|null, time|null)`; ordinali scambiati per mesi ("third" → March) → regola nella FSM;
"20" nel campo mese → instradamento; "the 2nd" → day e time insieme → regola "un numero solo".
Lezione: per un 1,7B la regola scritta non regge, togliere l'ingresso sì. Struttura prima dell'intelligenza.

## 3. Prompt: lungo vs minimo (misurato 05/09)
Ricerca: la doc Qwen mette la specifica nello schema, non nel system prompt, e per i casi ostinati indica il
fine-tuning; Rasa (task-oriented in produzione, stato + ultimo messaggio → comandi) impone "valori esattamente come
detti, niente conversioni" (le fa il codice); benchmark indipendente: Qwen3 1,7B 0,67 sotto 0,6B e 4B (0,88);
on-device 2026: Qwen3-4B / Gemma 4 E4B / Phi-4-mini high-80 su BFCL, tutti >95% dopo QLoRA con 600 esempi.
| prompt (Qwen3-1.7B locale) | base 55 | dialogo 20 |
|---|---|---|
| lungo, regole nel testo | 55 | 15 (falsi positivi: "let me think", "yes" dopo conferma) |
| **minimo (4 righe), contratto nello schema, valori verbatim** | 52 | 17 |
Adottato il minimo: le conversioni (ore a parole, ordinali) stanno nel gateway. L'aritmetica ("the next day") resta
fuori con l'1,7B in ogni caso. Rumore di misura ±1 (GPU non deterministica).

## 4. Cloud (provider Cline, endpoint OpenAI-compatible `https://api.cline.bot/api/v1`, chiave in `~/.config/tool_agent.env`)
Sonda su 4 casi difficili, 7 modelli (05/09):
| modello | latenza | +1 sul giorno | copia dopo prenotazione | "yes" offerta | "the second of April" |
|---|---|---|---|---|---|
| google/gemini-3.5-flash-lite | 0,9 s | ✓ | no | ✓ | ✓ (intento check) |
| anthropic/claude-haiku-4.5 | 1,0-1,4 s | ✓ | copia | ✓ | ✓ |
| minimax/minimax-m3:free | 1,1 s | ✓ | no | ✓ | ✓ |
| qwen/qwen3.8-flash | 1,3-1,5 s | ✓ | no | ✓ | ✓ |
| anthropic/claude-sonnet-5 | 1,7 s | ✓ | copia | ✓ | ✓ |
| openai/gpt-5.6-sol | 1,6-4,4 s | ✓ | no | ✓ | ✓ |
| google/gemini-3.8-flash | 1,4-3 s | ✓ | risposta vuota | ✓ | errore |
Anche Haiku e Sonnet copiano i valori mostrati: la struttura (DONE senza valori) serve con qualsiasi modello.

Regressioni complete con **gemini-3.5-flash-lite**:
| prompt | base 55 | dialogo 20 | latenza media |
|---|---|---|---|
| minimo (verbatim) | 53 | 16 (17 con 3 righe di dialogo) | 1,0 s |
| **smart** (risolvi riferimenti, calcola +1, converti) | 51 | **18** | 1,0 s |
Il prompt verbatim spegne l'intelligenza del cloud ("the day after" copiato alla lettera); lo smart la usa.
Residui cloud: a volte NESSUNA chiamata nonostante `tool_choice` forzato ("No, I want a book for May" → niente);
"I don't need you anymore" → cancel (in DONE: innocuo). Costo: flash-lite riportato 0 dall'API; qwen3.8-flash
0,0001 $/chiamata; gpt-5.6-sol 0,001 $.

**Latenza**: locale 0,8 s (0,5-1,0); flash-lite 0,9-1,0; Haiku 1,0-1,4; Sonnet 1,7; GPT fino a 4,4. Sul flusso:
fine battuta → frame ≈ 1,0 s locale, 1,1 flash-lite, 1,3 Haiku; l'omni apre bocca dopo 1-2 s: il margine si assottiglia,
non si rompe; un picco di rete (3-4 s) riporta l'effetto "let me check… ah, è libero".

## 5. Verdetto (05/09)
- La struttura era necessaria in ogni caso: un modello grande con lo stato posto male sbaglia uguale.
- Il cloud compra **generalizzazione** (meno sorprese su frasi mai viste, meno regole da ricamare), non correttezza
  sui casi noti: sulla regressione +1/+3 casi. Il giudizio vero è il numero di sorprese nelle sessioni dal vivo.
- Configurazione attuale: `--backend cline` con `google/gemini-3.5-flash-lite` e prompt smart (da
  `~/.config/tool_agent.env`: TA_API_KEY, TA_MODEL, TA_PROMPT), Qwen3-1.7B locale caricato come **fallback**
  automatico se l'API non risponde entro 4 s. Deroga al "tutto locale": le trascrizioni delle frasi dell'utente escono
  dalla macchina.
- Fuori scopo dell'estrattore (restano): l'omni che parla solo dopo un frame e si zittisce, il "one moment please"
  davanti a MISSING, gli errori ASR.

## 6. Due prompt: LOCAL_PROMPT e PROMPT_API (05/09)
- **LOCAL_PROMPT** (Qwen3-1.7B): 4 righe, valori verbatim, SOLO la battuta corrente (ogni riga in più è una fonte di copie).
- **PROMPT_API** (cloud): dice cos'è il sistema (operatore vocale, ASR con errori tipici), chiede di convertire (mese in
  nome, giorno in numero, ora HH:MM), di risolvere i riferimenti da STATO e dalle **ultime righe del dialogo, operatore
  compreso** (la pagina ne manda fino a 8, il servizio ne usa 6: `TA_CONTEXT`), di calcolare ±1 sul giorno offerto, e di
  non inventare dopo una richiesta chiusa. Selezione: `TA_PROMPT=api` nel file di ambiente, automatica con `--backend cline`.
| gemini-3.5-flash-lite | base 55 | dialogo 20 | latenza |
|---|---|---|---|
| prompt minimo (verbatim) | 53 | 16-17 | 1,0 s |
| prompt smart, senza dialogo | 51 | 18 | 1,0 s |
| **PROMPT_API + dialogo** | 52 | **19** | 1,0 s |
Residui: "is it free?" subito dopo una prenotazione → nessuna chiamata (ambiguo, accettabile); "No, I want a book for May"
→ nessuna chiamata nonostante `tool_choice` forzato (flash-lite a volte non chiama: da tenere d'occhio, se pesa si prova
qwen3.8-flash o haiku con lo stesso prompt); "tomorrow" → giorno 'tomorrow' respinto → chiede la data (accettabile).

## 7. Operazioni sullo stato invece di valori calcolati (05/09, proposta di Alessandro)
Il modello sceglie l'**operazione**, il codice calcola. Strumenti piccoli e **filtrati per stato** (in IDLE 'yes' non può
diventare una prenotazione; 'the next day' dopo una richiesta chiusa funziona senza che il modello veda la data):
| operazione | stati | il codice |
|---|---|---|
| `new_request(kind, month?, day?, time?)` | tutti | apre una richiesta con i valori detti (verbatim) |
| `provide(month?, day?, time?)` | COLLECTING, CONFIRM | riempie/corregge; intento = quello in corso (in CONFIRM: ri-verifica) |
| `accept(time?)` | CONFIRM | prenota lo slot offerto (chiede l'ora se manca; "yes, at 3 pm" la porta) |
| `decline()` | CONFIRM | chiude l'offerta senza scrivere |
| `cancel()` | COLLECTING | IDLE |
| `shift_day(delta)` | CONFIRM, DONE, COLLECTING con data | nuova verifica su riferimento ± delta (cambio mese gestito), stesso orario |
| `next_free(same_day \| next_days)` | CONFIRM, DONE | ricerca vera nel DB: prossimo slot orario libero (9-18) / primo giorno libero entro 60 |
| `none` | tutti (solo cloud) | nulla; locale: nessuna chiamata = nulla |
Prompt: 2-3 righe (LOCAL_PROMPT / PROMPT_API); riga di stato **senza valori** anche in CONFIRM ("an offer is pending").
| backend | base 55 | dialogo 20 | latenza |
|---|---|---|---|
| gemini-3.5-flash-lite + dialogo | **53** | **20** | 0,9-1,0 s |
| Qwen3-1.7B locale (fallback) | 47 | 17 | 0,5 s |
Cloud: sale da 19 a 20 sul dialogo ("the day after" = shift_day(1), "that day" = accept) con prompt più corto; i due mancati
sono "I need an appointment on May 5th" → check invece di book (ambiguo) e "tomorrow at 9" (giorno respinto → chiede la
data). Locale: senza lo strumento `none` in lista (lo sceglieva anche su "I want to book a desk") 47/55: le operazioni gli
costano di più del vecchio contratto (52), ma il dialogo regge (17). Tutte le operazioni verificate via curl (shift a
cavallo del mese: April 30 +1 → May 1; next_free same_day → 09:00; accept da DONE → nulla).
Configurazione: `--backend cline` (flash-lite, PROMPT_API, dialogo), locale come fallback.

## 8. Semplificazione finale (05/09 notte): tre strumenti fissi, significato dato dallo stato
Alessandro: via le otto operazioni, "book e check availability come prima", tenendo lo stato di conferma. Strumenti:
`book(month?, day?, time?)`, `check_availability(month?, day?, time?)`, `cancel()`; nessuna chiamata = nulla.
Il significato lo decide la FSM: in CONFIRM `book` senza campi = "yes" (accetta l'offerta o conferma la prenotazione, unico
modo di scrivere); campi senza mese nuovo = correzione (si eredita l'offerta, si torna in conferma); mese nuovo = richiesta
nuova; in COLLECTING l'intento in corso non cambia; `cancel` in conferma = "no" (nota BOOKING NOT CONFIRMED).
Ogni prenotazione completa passa da CONFIRM ("WAIT FOR USER CONFIRMATION / BOOKING FOR … / SAY YES TO BOOK").
Aritmetica ("the next day"): non c'è più `shift_day`; il cloud la fa da solo leggendo il dialogo (March 31, April 5), il
locale no (nessuna azione). Misure flash-lite: base 51/55 (mancati: "I need an appointment on May 5th" → check; "book
for May" → check; "tomorrow at 9"; "I don't need you anymore" → cancel in DONE, innocuo), dialogo 24/24.

## 9. Architettura teorica e interventi senza toccare l'omni (05/09)
PDF: `docs/architettura-hud-algebra.pdf` (algebra R/E/A, funzioni ε/δ/ρ, linguaggio dell'HUD, mappa del sistema, cosa
cambierebbe con e senza toccare l'omni, piano del ramo `omni-eventi`). Implementato oggi senza toccare l'omni:
- **Decisione anticipata alla pausa**: alla prima pausa di 300 ms parte ASR + estrattore sull'audio detto finora; a turno
  confermato si applica solo se non si è ripreso a parlare (registro: "decisione anticipata: usata / scartata"). Attesa:
  fine frase → frame da ~1,8 a ~1,2 s. Da confermare dal vivo.
- **Decodifica vincolata (lm-format-enforcer) per il locale**: misurata 44/55 contro 47 libera, dialogo 18/24: il 1,7B
  costretto a riempire il JSON inventa ("Nine" → September 9, "15" → April 15). Spenta di default (TA_CONSTRAINED=1 per
  provarla). Lezione: ogni obbligo dato al piccolo finisce in un'invenzione; la libertà di non chiamare vale più della
  garanzia sintattica.
- **Schermo a due metà** (atto sopra: ASK: DAY / ASK: CONFIRM BOOKING / SAY: BOOKED…, stato sotto), selettore nel pannello
  per il confronto; riga di prompt da aggiungere a mano. Non ancora giudicato.
Non fatti: contratto Set/Answer/Abort (scelta esplicita: tre strumenti), imbuto con conteggi, VAD 800 ms.

## 10. Decimo test dal vivo (05/09): merge sempre in raccolta; lo slot occupato non chiude la richiesta
Sessione sess_8eebe657a3fa: book April 20 15 → occupato → "check when it's available" → la macchina era ripartita da zero
(DONE senza valori) e poi, al "April" detto quando mancava il mese, aveva azzerato il 20 (regola "mese = richiesta
nuova", sbagliata): quattro turni di ping-pong mentre l'omni ricordava tutto. Due correzioni, entrambe dentro l'algebra:
1. **In COLLECTING si fa sempre merge** (un mese detto sovrascrive, non azzera); una richiesta nuova esiste solo da
   IDLE/DONE o dopo un annulla.
2. **Ora occupata = valore respinto dalla validazione contro il DB**, come un "tomorrow" respinto dalla sintassi: la
   richiesta resta in raccolta con mese e giorno tenuti, `ASK: ANOTHER TIME`, e le **ore libere del giorno** nello stato
   (`FREE: 9 10 11 12 14 16 · 15:00 TAKEN`), calcolate dal gestionale: l'imbuto con i conteggi. Giorno tutto pieno →
   si richiede il giorno. DONE resta per: prenotazione scritta, offerta rifiutata, errore, annulla.
Verifica curl della sessione incriminata: book() → April → 20 (FREE: 9…17) → 15 → `ASK: ANOTHER TIME`, 20 e aprile
tenuti → check() vuoto → invariato → "16" → conferma. Merge: check() → 20 → April → CONFIRM April 20.
UI: schermo a due metà di default; prompt di default aggiornato ("the top of the screen tells you what to do next").
Decisione anticipata alla pausa: usata in tutti i turni della sessione (frame a 0,3-0,6 s dalla fine della frase).
Regressioni invariate: cloud 51/55, 24/24.

## 11. L'algebra senza scorciatoie: set / yes / no / cancel (05/09 sera)
Undicesimo test dal vivo (sess_1f532b987f40): dopo "15:00 TAKEN / ASK: TIME" l'omni ha proposto le 16 da solo, l'utente ha
detto "yeah, let's try" (un sì a una domanda che la macchina non aveva fatto), l'omni ha "confermato" senza nessun frame
BOOKED, e più tardi "No, time is…" → `book({})` → in conferma valeva "sì" → prenotazione scritta contro un no.
Due violazioni dell'architettura teorica: (1) E schiacciato: "sì" e "prenota" erano lo stesso gesto (`book` vuoto);
(2) un atto creato dall'attore e non dalla macchina (OFFER 16:00 inventato). La (2) è dell'omni (limite 4 del PDF); la (1)
era nostra ed è chiusa così:
| evento | significato | effetto |
|---|---|---|
| `set(intent?, month?, day?, time?)` | valori detti, copiati | scrive CAMPI, mai nel DB: merge in raccolta, correzione in conferma (si torna in conferma), richiesta nuova da IDLE/DONE (senza intento = verifica); vuoto = nullo |
| `yes()` | sì alla domanda aperta | l'**unico** evento che scrive; fuori da CONFIRM non fa nulla |
| `no()` | no alla domanda aperta | chiude senza scrivere (prenotazione → IDLE "BOOKING NOT CONFIRMED"; offerta → DONE) |
| `cancel()` | abbandono | IDLE |
"yes, at 3 pm" = `set(time)` + nuova conferma (decisione di Alessandro: yes non porta mai valori). Riga di stato senza
valori: dice solo se c'è una domanda sì/no aperta e cosa manca. Lo stato intermedio "occupato → ASK: TIME" è stato tolto
(invitava l'omni a proporre): uno slot occupato chiude la richiesta, come prima. Resta il merge sempre in raccolta.
Verifica curl della sessione: 15 occupato → DONE; `yes` → nulla; set(April 20, 16) → conferma; `no` → chiuso, nulla
scritto; yes(time=17) → set → nuova conferma → `yes` → scritto.
| backend | base 55 | dialogo 24 | latenza |
|---|---|---|---|
| gemini-3.5-flash-lite + dialogo | **53** | **23** | 0,9-1,0 s |
| Qwen3-1.7B locale (fallback) | 48 | 18 | 0,5 s |
Mancati cloud: "tomorrow at 9" (giorno respinto, chiede la data), "I don't need you anymore" → cancel a richiesta chiusa
(innocuo), "the next day" → set(day=31) senza mese → chiede il mese (niente aritmetica, per contratto).

## 12. Orecchio laterale: Whisper large-v3-turbo, fallback locale opzionale (05/09 sera)
L'ASR è l'anello debole ("20 at 16" → "April 2016", "book at 9" → "book 49"); la macchina lo filtra con la validazione
(2016 respinto) e con la conferma prima di scrivere, ma i valori plausibili e sbagliati costano un giro. Decisione di
Alessandro: Whisper **large-v3-turbo** (1,5 GB) al posto di small, e via il fallback locale Qwen3-1.7B (3,5 GB liberati).
Profilo scelto dalla UI ("Orecchio laterale": turbo senza fallback | small con fallback) → `POST /api/hud/asr_profile`
→ `tools/switch_asr_profile.sh` riavvia solo ASR ed estrattore (~1 min); il launcher usa `HUD_ASR` (default turbo).
Misura sulle clip della sessione: sulla clip lunga (10 s) entrambi trascrivono bene "April 20 at 16"; turbo 0,22 s contro
0,78 s di small, logprob migliore (-0,56 contro -0,70). L'errore "2016" dal vivo era sulla battuta corta tagliata dal VAD:
Whisper peggiora sulle clip brevi. Da valutare dopo: confidenza (avg_logprob) come terzo esito del validatore ("dubbio" →
CONFIRM del valore), `initial_prompt` con il lessico dello sportello, audio diretto al modello cloud.
VRAM con il profilo turbo: ~29,3 GB (omni + turbo, senza Qwen).

### 12.1 Contesto e lessico per Whisper: misurati, spenti
Sulle battute vere della sessione sess_2443a727985c (blob 16 kHz con voce): "Hello", "I'd like to book a call", "the 20",
"yeah go ahead" sono trascritte bene in ogni variante; la battuta "April" (trascritta "incredible" dal vivo) è
inintelligibile per Whisper in tutte le varianti ('uh tabs', 'Eyebrill?'), mentre l'omni l'ha capita. Il **lessico come
initial_prompt** fa allucinare su audio povero (frasi in lingue a caso, "I got a new ancient 800 years old"); il **contesto
di 3 s** non aiuta perché il microfono in silenzio manda zeri digitali (Windows attenua) e con il lessico peggiora.
Entrambi restano come opzioni nella richiesta, spenti di default. Conclusione: per le battute corte e povere l'orecchio
laterale non si ripara con Whisper; la via è la ripetizione dell'operatore (`heard`, tentativo + conferma) o l'omni
che emette gli eventi.

## 13. Secondo orecchio: `heard` (05/09 sera), attivabile dalla UI
L'omni sente meglio di Whisper ("April" contro "incredible") ma non produce trascrizioni: produce solo ciò che dice, e
spesso ripete ciò che ha capito ("Got it, April 20th"). A fine turno dell'omni un estrattore separato legge la sua frase
(`/heard`, solo cloud) e ne ricava `heard(month?, day?, time?)`; domande e proposte ("how about 16:00?", "we have 9 or
11") → niente (verificato su 8 frasi). Regole nella FSM, che rendono la macchina più stabile e mai meno:
- solo in raccolta; riempie solo i campi MANCANTI; mai sopra un valore del cliente (il cliente vince, anche dopo);
- il campo riempito è **tentativo** (`APRIL?` sullo schermo, atto `CONFIRM: MONTH`); il `yes` del cliente lo rende solido,
  il `no` lo scarta (torna `ASK: MONTH`); un `set` del cliente sullo stesso campo lo supera;
- **non si esegue né si scrive con un tentativo nel record**: prima la conferma del campo, poi il flusso normale;
- monotono e idempotente: nessuna oscillazione frame → omni → frame.
Il rischio residuo (entrambi gli orecchi sbagliano) costa un "no" al livello del campo, mai una scrittura. Spunta
"Secondo orecchio" nel pannello per provare con e senza. Provato via curl: il caso "April" si allinea in un turno.
Scartati oggi: schermo "NOT UNDERSTOOD" (troppo lungo, e l'omni spesso ha capito), iniezione di token nell'omni
(possibile via backend, rimandata: il prefisso forzato "Let me confirm:" è l'evoluzione se le ripetizioni spontanee
non bastano).
