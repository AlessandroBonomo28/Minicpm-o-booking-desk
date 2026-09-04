# Ramo sperimentale HUD — il frame come segnale di evento asincrono

Stato: **costruito, in attesa del test interattivo di Alessandro** (03/09/2026).
Spec di riferimento: messaggio di Alessandro del 02/09 (flusso "controllo un attimo → HUD cambia → riprende").

## Cosa c'è

- Pagina: `https://localhost:8006/static/hud/hud.html` (file `static/hud/hud.html`, `static/hud/hud-app.js`).
  Nessuna modifica al backend: usa il protocollo normale (`input.append` con `audio` + `video_frames` opzionali, mode=video).
- Launcher: `bash tools/run_demo_hud.sh` = codice del ramo italiano (serve la pagina) + **pesi BASE**
  (v1.3 con i token video degenera: calendario, via di sviluppo 5).
- Schermo operatore: canvas 448×448, semaforo a 5 stati — IDLE (grigio) / VERIFICA IN CORSO (giallo, con eco
  della richiesta) / LIBERO (verde) / OCCUPATO (rosso) / ERRORE-TIMEOUT (rosso). Testo grande, niente griglie.
- Gate sul cambio: hash dello stato; il frame viene allegato **solo** al primo chunk audio dopo un cambio
  (opzione: frame IDLE iniziale una volta all'avvio).
- Simulatore backend: data/ora, esito scelto, ritardo N secondi. Avvio **manuale** (bottone) o **automatico**
  (regex sul testo del modello, default `controll|verific|un attimo|un momento|guardo`).
- Registro eventi: "FRAME INVIATO" e "REAZIONE +x s" al primo testo del modello dopo ogni frame → misura del Test 1.
- Prompt di default (modificabile in pagina): prompt nativo + ruolo "operatore di sportello" in italiano.

## Protocollo di test (Test 1 — il frame innesca la ripresa?)

1. Avvia lo stack: `bash tools/run_demo_hud.sh` (attendi `DEMO HUD SU`). Cuffie.
2. Apri la pagina, "Avvia sessione". Chiedi: *"È libero il 31 marzo alle 15?"*
3. Il modello dovrebbe dire "controllo un attimo" → l'auto-trigger porta l'HUD a VERIFICA IN CORSO (frame 1)
   → dopo N s esito (frame 2). Se non lo dice, usa il bottone "Avvia verifica".
4. Leggi il registro: dopo il frame 2, il modello riprende **da solo** e cita LIBERO/OCCUPATO? entro quanti secondi?
   Ripeti con esito OCCUPATO e con ERRORE. Poi due richieste in rapida successione (attribuzione, §6 spec).
5. Variante: spunta "frame iniziale" spenta (il modello non sa dello schermo finché non cambia).

Criterio (spec §8): Test 1 passa se la ripresa avviene ed è coerente con l'esito; Test 2 (stessa cosa con
iniezione di TESTO invece del frame) **non è ancora costruito**: richiede un'estensione del backend (un campo
`input.text` da inserire nell'unità) e va fatto solo dopo il verdetto sul Test 1.

## Risultati

(da compilare con i test di Alessandro: reazione sì/no, latenza, coerenza con l'esito, attribuzione)

## Rischi aperti (dalla spec)

- accumulo dei frame in KV (pochi frame per sessione: irrilevante per il test, da gestire in produzione);
- attribuzione della risposta in ritardo (mitigata dall'eco della richiesta nell'HUD);
- il modello base potrebbe descrivere lo schermo invece di "usarlo" (visto nel replay: "Il video è in totale
  oscurità…") → il prompt deve dirgli cosa fare con lo schermo, non cosa c'è.

## Sonda tool calling nativo (03/09, modello base, turn-based via gateway)

Prompt di sistema con il blocco `<tools>` ESATTO del chat template Qwen3 (presente nel tokenizer di
MiniCPM-o 4.5, con i token speciali `<tool_call>`/`<tool_response>`), funzione `check_availability(date,time)`.
- "È libero il 31 marzo alle 15:00?" → **nessun `<tool_call>`**: risponde inventando ("Certamente, il 31 marzo alle 15:00 è disponibile").
- "Buongiorno, come va?" → chiacchiera normale (corretto).
- "Vorrei prenotare per il 2 aprile alle 10." → **nessun `<tool_call>`**: chiede conferma a parole.
Verdetto: la grammatica dei tool esiste nel tokenizer/template (ereditata da Qwen3-8B) ma il modello omni
NON la usa: il comportamento di chiamata è stato smussato dal training omni. Il tool calling va costruito
fuori dal modello (estrazione dallo stream di testo / frase-segnale) — coerente con la spec §6.

## Tool calling con MODELLO SEPARATO (decisione di Alessandro, 03/09)

L'omni non chiama tool (sonda sopra). Il tool calling lo fa un modello a parte, nato per questo:
- `tools/tool_agent_server.py` (porta 22700, env minicpm): **Qwen3-1.7B** (stessa famiglia del cervello,
  tool calling nativo via chat template, ~3.4 GB bf16 sulla stessa GPU accanto all'omni).
  `POST /decide {transcript:[{role,text}]}` → `{tool_calls:[{name,arguments}], raw}`. Funzione di default
  `check_availability(date,time)`; prompt: chiama SOLO se l'operatore sta per verificare data+ora precise.
- Gateway (ramo italiano): proxy `POST /api/tool_agent/decide` → 22700 (la pagina è HTTPS, niente mixed content).
- Pagina HUD, selettore "Trigger": **modello separato** (default) / regex / solo manuale. Nel modo "modello
  separato" il testo dell'omni (turno che si assesta, ~1.2 s senza nuovi delta) viene mandato al tool agent;
  se risponde `check_availability`, data/ora estratte finiscono sull'HUD (eco della richiesta) e parte la
  verifica simulata → frame. Il registro mostra `TOOL AGENT (x s): check_availability({...})`.
- Launcher `tools/run_demo_hud.sh` avvia anche il tool agent (dopo il backend) e ne verifica la salute.
Limite noto: la "trascrizione utente" non esiste nell'e2e (l'omni non produce ASR); il tool agent legge il
testo dell'omni, che di norma ripete data e ora. Se servisse l'ASR lato tool agent, è un'aggiunta separata.

### Prove del tool agent (03/09, Qwen3-1.7B, via proxy del gateway)
| Testo dell'operatore | Decisione | Latenza |
|---|---|---|
| "verifico subito per il 2 aprile alle dieci e mezza" | check_availability(2 aprile, **10:30**) | 1.6 s |
| "controllo un attimo per il 5 maggio alle nove e un quarto" | check_availability(5 maggio, **09:15**) | 0.9 s |
| "guardo se domani alle tre del pomeriggio è libero" | check_availability(domani, **15:00**) | 0.6 s |
| "controllo un attimo il 31 marzo alle 15" | check_availability(31 marzo, 15:00) | 0.8 s |
| "mi dica pure la data e l'ora che preferisce" | nessuna azione | 0.2 s |
(prima delle regole sull'ora nel prompt, "dieci e mezza" veniva reso 15:00: corretto con regole+esempi.)

### Lingua del test: INGLESE (decisione di Alessandro, 03/09)
Il test si fa nella distribuzione nativa del base: prompt come l'English Call del ramo originale ("You are in
duplex mode…" + ruolo di operatore), voce di riferimento inglese (preset English Call), schermo in inglese
(BOOKING DESK / CHECKING... / AVAILABLE / BOOKED / ERROR), tool agent con regole per gli orari parlati in inglese.
Prove EN: "let me check March 31st at 3 pm" → (March 31st, 15:00) 1.9 s; "April 2nd, half past ten" → 10:30;
"tomorrow at quarter past nine" → 09:15; "Hi there! How can I help?" → nessuna azione (0.1 s).

## Caso d'uso unico e protocollo di test standard (03/09)

**Caso d'uso**: sportello prenotazioni, UNA funzione `check_availability(date, time)`, UNO schermo a semaforo
(CHECKING → AVAILABLE / BOOKED / ERROR). Prompt essenziale (3 frasi):
*"You are in duplex mode, where you can listen and speak at the same time. You work at a booking desk. When the
user asks about a date and time, say "let me check" and wait. When the screen shows the result, read it out."*

**Sistema semplificato**: omni (parla/ascolta) · tool agent Qwen3-1.7B (decide la chiamata) + ASR whisper-small
sugli ultimi 12 s del microfono (così il tool agent legge ANCHE le parole dell'utente: prima leggeva solo l'omni e
"Let me check." da solo non bastava) · schermo HUD (frame solo al cambio).

**Domande standard** (in inglese, una per sessione salvo D5; esito scelto prima nel pannello):
| # | Cosa dire | Esito impostato | Comportamento atteso |
|---|---|---|---|
| D1 | "Is March 31st at 3 pm available?" | AVAILABLE | dice "let me check" → tace → al frame dell'esito riprende da solo e dice che è disponibile |
| D2 | "Is March 31st at 3 pm available?" | BOOKED | come D1, ma dice che è occupato |
| D3 | "Is March 31st at 3 pm available?" | ERROR | come D1, ma segnala l'errore (non inventa) |
| D4 | "Is April 2nd at half past ten free?" | AVAILABLE | tool agent estrae `April 2nd, 10:30`; HUD mostra 10:30 |
| D5 | "Is March 31st at 3 pm available?" … poi subito "And April 3rd at 9?" | AVAILABLE / BOOKED | due verifiche in fila, ogni risposta attribuita alla data giusta |
| D6 | "How are you today?" | — | chiacchiera, NESSUNA verifica avviata |
| D7 | "Is March 31st at 3 pm available?" poi, durante CHECKING: "Actually, never mind." | AVAILABLE | vediamo cosa fa quando il frame arriva dopo un ripensamento |

**Feedback che serve, per ogni domanda**: (a) ha detto "let me check"? (b) è stato zitto durante CHECKING?
(c) al frame dell'esito ha parlato DA SOLO (senza che tu parlassi) e dopo quanti secondi (registro: REAZIONE +x s)?
(d) l'esito detto è quello sullo schermo? (e) data/ora sull'HUD giuste (registro: TOOL AGENT …)?
(f) qualsiasi cosa strana (loop, silenzio lungo, risposta a una domanda vecchia).

## Pagina "stato del gestionale" (03/09)
`https://localhost:8006/static/hud/db.html` — sola lettura, si aggiorna ogni secondo: stato corrente dello
schermo HUD, slot conosciuti (data, ora, LIBERO/OCCUPATO, ultima verifica), registro delle verifiche (quando,
richiesta, esito, avviata da: modello separato/regex/manuale, ritardo). Sorgente: `GET /api/hud_db` (gateway del
ramo italiano, persistito in `data/hud_db.json`); la pagina HUD scrive a ogni verifica (`/api/hud_db/check`)
e a ogni cambio di schermo (`/api/hud_db/hud_state`). `POST /api/hud_db/reset` azzera.
Aggiornamento: `db.html` ha ora la **form delle prenotazioni** (data, ora, nome → slot OCCUPATO; "Libera" lo
riapre). La verifica dell'HUD di default legge il gestionale (`outcome=auto`: prenotato → BOOKED, altrimenti
AVAILABLE); "forza AVAILABLE/BOOKED" e "simula ERROR" restano nel pannello HUD per gli esperimenti. Date e ore
normalizzate lato server come le estrae il tool agent ("March 31st"→march 31, "3 pm"→15:00, "15"→15:00).
Aggiornamento (03/09 sera): campo ora **libero** nel form ("3 pm", "3:00", "all day", "3-17", vuoto = tutto il
giorno). Sul server: normalizzazione solo per far combaciare la verifica (orario singolo, intervallo, giornata;
1-7 senza am/pm = pomeriggio); la stringa scritta resta (`time_raw`) ed è quella mostrata sull'HUD:
**BOOKED ALL DAY / BOOKED 3 PM / BOOKED 3-17**. Verifica senza ora = giornata: AVAILABLE (nessuna
prenotazione) / PARTLY BOOKED con l'elenco / BOOKED ALL DAY. Il tool agent non inventa più l'ora: `time`
facoltativo nello schema (domanda senza ora → verifica della giornata).

## 04/09 — laterale veloce: VAD nel browser + trigger sul turno dell'utente + ASR su GPU
- **VAD nel browser** (energia, fettine da 100 ms tramite un secondo nodo del capture-worklet): soglia,
  silenzio di fine turno (600 ms) e voce minima (300 ms) regolabili in pagina; 300 ms di pre-roll.
- **Trigger = fine del TUO turno**: la battuta appena finita (solo quella) va al tool agent; il testo dell'omni
  è solo contesto (mai trigger) → i falsi positivi da domande/annunci dell'operatore spariscono per costruzione.
- **ASR su GPU** (whisper small, fp16): trascrive solo la battuta (3-5 s). Tempi riportati nel registro:
  `ASR x s + LLM y s = z s`.
- Scartati (vedi `ideescartate.md`): prefiltro, due passi, cache vLLM, iniezione lato server. Piano B se la
  VRAM stringe: ASR sulla NPU Intel AI Boost (Core Ultra 9 285K) da un servizio Windows con OpenVINO.

## 04/09 — Macchina a stati della prenotazione (FSM): specifica PRIMA dell'implementazione

Origine: proposta di Alessandro ("vorrei prenotare una visita" → il tool agent trova che manca la data → l'HUD lo
mostra → l'omni chiede la data → l'utente la dà → chiamata vera → attesa → risultato annunciato; annullabile a voce
in ogni momento), confrontata con il riscontro di Gemini e con quanto misurato qui. Decisioni prese:

1. **La FSM la fa il codice (gateway), non il modello da 1,7B.** Qwen3-1.7B resta un *estrattore per turno*:
   dice cosa ha chiesto l'utente in QUESTA battuta (intento + campi effettivamente detti). Il merge con quanto
   già raccolto, il calcolo di cosa manca, l'esecuzione sul DB e la transizione sono deterministici e testabili
   con `curl`, senza GPU. Motivo misurato: quando lo schema obbligava un campo, il 1,7B lo inventava (00:00);
   quando il campo è diventato facoltativo ha smesso. Ogni "obbligo" sta quindi nella FSM, non nello schema.
2. **L'HUD resta STATO, mai istruzione.** Il frame mostra cosa è raccolto e cosa manca (`MISSING: DATE`), non
   frasi per l'omni ("chiedi in modo naturale…"): il modello è addestrato a osservare i frame, non a eseguirli, e
   quando lo schermo cambia tende a leggerlo ad alta voce (Test 1) → testo lungo = lettura lunga e goffa.
   L'unica istruzione vive nel system prompt, statica.
3. **Campi già raccolti: SÌ sullo schermo** (risposta alla domanda di Alessandro). Sono parte dello stato; l'ASR
   (whisper small) può sbagliare un numero e così l'utente/Alessandro lo vede e lo corregge a voce; db.html
   mostra la stessa cosa.
4. **Niente stato "prendi tempo"** (proposta Gemini): è il nostro CHECKING, dove abbiamo visto i silenzi di 30 s.
   Con il DB locale l'esecuzione dura millisecondi → dal turno dell'utente si va DIRETTI a RESULT (~0,6 s +
   allineamento al chunk). CHECKING compare solo se il backend è davvero lento (ritardo simulato > 0).
   Niente stato "TOOL_TRIGGERED": durerebbe 0,6 s, meno di un frame, l'omni non lo vedrebbe mai.
5. Race "risponde prima del frame": misurata piccola (decisione 0,6 s; l'omni apre bocca dopo 1-2 s) → il frame
   arriva prima o insieme alla sua prima parola. Non si aggiunge nulla per gestirla; si osserva nei test.
6. **Cuffie obbligatorie**: il VAD è sul microfono; con gli altoparlanti la voce dell'omni diventa un "turno
   utente" e l'estrattore legge le parole dell'operatore come se fossero del cliente.

### Stati (FSM nel gateway, persistita in `data/hud_db.json` → `fsm`, visibile in db.html)

| Stato | Contenuto | Entra da | Esce verso |
|---|---|---|---|
| `IDLE` | nessuna richiesta; `note` facoltativa (`REQUEST CANCELLED`) | avvio, reset, `cancel` | `COLLECTING` (book), `RESULT` (check completo) |
| `COLLECTING` | `intent=book`, `slots{date?,time?}`, `missing=[…]` | `book(...)` incompleto | `COLLECTING` (altro campo), `RESULT` (completo → esecuzione), `IDLE` (cancel) |
| `CHECKING` | richiesta in esecuzione (solo con ritardo simulato > 0) | esecuzione | `RESULT` |
| `RESULT` | `intent`, `slots`, `status` ∈ OK / PARTIAL / NO / ERR, `detail` | esecuzione finita | `COLLECTING`/`RESULT` (nuova richiesta), `IDLE` (cancel o reset) |

Regole:
- **Campi richiesti per intento**: `check` → date (time facoltativo = giornata intera, come oggi);
  `book` → date **e** time (una visita ha un'ora). Si chiede UN campo alla volta, in quest'ordine: date, time.
- **Merge**: un campo si sovrascrive solo con un valore non vuoto detto dall'utente; ripetere la data la
  conferma, dirne un'altra la corregge (`"no, the 3rd"` → date = april 3).
- **Esecuzione `book`**: se lo slot è libero → scrive la prenotazione nel DB (nome: `voice`), RESULT OK
  (`CONFIRMED`); se occupato → RESULT NO (`SLOT TAKEN`, dettaglio come oggi), slots svuotati (una nuova
  `book(...)` riparte); errore/timeout → RESULT ERR.
- **`cancel`** da qualunque stato → `IDLE` con `note=REQUEST CANCELLED` (così l'omni ha qualcosa da
  riconoscere; la nota sparisce alla prossima transizione). Nessuna prenotazione scritta.
- `RESULT` **persiste** finché non arriva una nuova richiesta, un cancel o un reset: nessun timeout (sarebbe una
  pezza; se serve un ritorno automatico a IDLE, si discute).
- Normalizzazione di date/ore come oggi (`_hud_norm_date`, `_hud_norm_time`); il testo grezzo dell'utente resta
  nel registro (`user_text`), è lì che Alessandro controlla la precisione dell'ASR.

### Contratto dell'estrattore (tool agent, un turno = una decisione)

Ingresso: stato FSM corrente (intento e campi già raccolti, in chiaro nel prompt), ultime 6 battute dell'UTENTE
(ASR, accumulate nella pagina), ultima battuta dell'operatore (contesto, mai fonte di date). Uscita: al più UNA
chiamata tra `book(date?, time?)`, `check(date?, time?)`, `cancel()`, altrimenti `NO ACTION`.
Regole nel prompt: campi solo se detti dall'utente in questa battuta ("never invent"); se una prenotazione è in
corso e l'utente risponde con un solo dato ("April 2nd"), chiamare `book` con quel solo campo; "never mind /
cancel / forget it" → `cancel`; domanda di disponibilità → `check`; chiacchiere → `NO ACTION`.

Flusso per turno: VAD chiude la battuta → `POST /api/tool_agent/decide` (ASR + estrazione, ~0,6 s) →
`POST /api/hud_fsm/event {tool_calls, user_text}` (gateway: merge, esecuzione DB, nuovo stato) → la pagina
disegna il frame (solo se lo stato è cambiato) → allegato al prossimo chunk da 1 s.

### Formato del frame per stato (448×448, font come oggi: titolo 34, riga1 44, riga2 56/40, riga3 22)

| Stato | Sfondo | Titolo | Riga 1 | Riga 2 | Riga 3 |
|---|---|---|---|---|---|
| IDLE | grigio | `BOOKING DESK` | `waiting for a request` | `` (o `REQUEST CANCELLED` se nota) | |
| COLLECTING, manca la data | blu | `NEW BOOKING` | `DATE: ?` | `MISSING: DATE` | `TIME: 15:00` se già detto |
| COLLECTING, manca l'ora | blu | `NEW BOOKING` | `APRIL 2` | `MISSING: TIME` | |
| CHECKING | giallo | `CHECKING...` | `APRIL 2 15:00` | `please wait` | |
| RESULT check | verde/arancio/rosso | `RESULT` | `APRIL 2 15:00` | `AVAILABLE` / `PARTLY BOOKED` / `BOOKED <time_raw>` | dettaglio |
| RESULT book OK | verde | `BOOKING` | `APRIL 2 15:00` | `CONFIRMED` | |
| RESULT book NO | rosso | `BOOKING` | `APRIL 2 15:00` | `SLOT TAKEN` | dettaglio |
| ERR | rosso scuro | `ERROR / TIMEOUT` | `APRIL 2 15:00` | `request failed` | |

System prompt dell'omni (unica variabile che tocca il modello, statica):
*"You are in duplex mode, where you can listen and speak at the same time. You work at a booking desk. The screen
shows the booking system. When the screen shows MISSING, ask the customer for that item. When the screen shows a
result, tell the customer. Otherwise just talk."*

### Domande standard aggiunte (inglese, cuffie, una sessione per riga salvo dove indicato)

| # | Cosa dire | DB prima | Comportamento atteso |
|---|---|---|---|
| D8 | "I'd like to book a visit." | — | estrattore: `book()` senza campi; HUD `NEW BOOKING / DATE: ? / MISSING: DATE`; l'omni **chiede la data**; nessuna data inventata sull'HUD |
| D9 | (dopo D8) "April 2nd at 3 pm." | april 2 libero | `book(April 2nd, 15:00)` → completo → scritto nel DB → `CONFIRMED`; l'omni lo annuncia da solo; db.html mostra lo slot OCCUPATO |
| D9b | (dopo D8) "April 2nd." poi, alla domanda dell'omni, "at 3 pm" | april 2 libero | due passi: `MISSING: TIME` → l'omni chiede l'ora → `CONFIRMED` |
| D9c | (dopo D8) "April 2nd at 3 pm." | april 2 15:00 già prenotato da db.html | `SLOT TAKEN`; l'omni lo dice e non conferma nulla; DB invariato |
| D10 | (dopo D8, mentre l'omni chiede la data) "Actually, never mind, cancel that." | — | `cancel()` → IDLE `REQUEST CANCELLED`; l'omni si interrompe, prende atto e **non insiste** sulla data; DB invariato |
| D11 | "Is March 31st at 3 pm available?" (= D1) | — | regressione: `check` invariato, RESULT diretto senza CHECKING |

**Predizioni scritte prima dei test** (variabile: frame `MISSING` + riga di prompt; il resto è codice):
- P1 (estrattore): su D8 chiama `book()` senza campi. Rischio: mette `tomorrow` da solo → se succede, è un
  problema dell'estrattore (si vede nel registro), non dell'omni.
- P2 (omni, la vera incognita): al frame `MISSING: DATE` legge lo schermo e chiede la data, probabilmente citando
  lo schermo in modo letterale ("the screen says the date is missing, when would you like to come?").
  Accettabile. Se invece ignora il frame e chiacchiera, la FSM non ha senso e si torna a capire perché.
- P3 (cancel): in Omni mode si interrompe fisicamente; visto `REQUEST CANCELLED` prende atto. Rischio: ripete una
  volta la domanda già generata, poi smette. Se insiste dopo il frame → fallito.
- P4 (misura a lato, non variabile): con RESULT diretto (niente CHECKING) i silenzi di 30 s dopo "let me check"
  dovrebbero sparire su D11, perché non c'è più uno stato che gli dice di aspettare.

**Ordine di implementazione**: (1) FSM + endpoint nel gateway e prova a tavolino con `curl` (senza GPU);
(2) estrattore con i tre strumenti e prova con testi scritti via proxy (come le prove del 03/09);
(3) frame e prompt nella pagina HUD; (4) db.html mostra la FSM; (5) test dal vivo D8 → D10 → D9 → D11.

### 04/09 (sera) — implementazione fatta, passi 1-4; passo 5 (test dal vivo) ad Alessandro
- **Gateway**: `_hud_fsm_apply` + `POST /api/hud_fsm/event`, `GET /api/hud_fsm`, `POST /api/hud_fsm/reset`; esecuzione
  fattorizzata in `_hud_exec_check` / `_hud_exec_book` (book scrive lo slot come OCCUPATO, nome `voice`); `fsm` persistita in
  `data/hud_db.json`; `/api/hud_db/reset` azzera anche la FSM. Provata a tavolino con curl: D8 → COLLECTING (manca date,
  time); "April 2nd" → manca time; "3 pm" → RESULT taken (2 aprile era prenotato tutto il giorno); slot libero → confirmed;
  stesso slot di nuovo → taken; cancel → IDLE `REQUEST CANCELLED` (solo se era in COLLECTING: da RESULT/IDLE pulisce senza
  nota, perché "thanks, bye" non deve far comparire "cancellato" a prenotazione fatta); check → RESULT diretto.
- **Estrattore** (`tools/tool_agent_server.py`), cambiato rispetto alla specifica dopo le prime sonde: con tre strumenti
  separati (`book/check/cancel`) il 1,7B **riempiva i campi a forza** ("date": "March 31" preso dagli esempi del prompt,
  "date": "none", o l'intera frase). Struttura che funziona: **UN solo strumento `request(intent ∈ {book,check,cancel,none},
  date|null, time|null)`**, sempre chiamato: il modello ha sempre qualcosa da riempire (l'intento) e il null è previsto dal
  contratto. In più l'estrattore riceve **SOLO le righe dell'utente** (ultime 4, l'ultima marcata NOW) + la riga di stato
  della FSM: le righe dell'operatore erano una fonte di date ("We have a slot on May 5th at 9" + "Hmm, let me think" →
  check(May 5th, 9)); tolte per costruzione, come il trigger sul turno utente. Niente date d'esempio nel prompt.
  Sonde dopo la modifica (tutte via proxy, testi scritti): D8 → `book()` ✓; "Book me April 2nd at 3 pm" → book(April 2nd,
  15:00) ✓; "April 2nd" in corso → book(date) ✓; "At 3 pm" con data raccolta → book(April 2nd, 15:00) ✓ (copia la data dallo
  stato: innocuo, il merge è idempotente); D10 "Actually, never mind, cancel that" → cancel ✓; D11 "Is March 31st at 3 pm
  available?" → check ✓ (dopo aver chiarito nel prompt che una domanda di disponibilità NON è una prenotazione: prima dava
  book, che avrebbe scritto nel DB); "Do you have anything on June 1st?" → check ✓; "How are you today?" / "Thank you, bye"
  dopo RESULT / operatore-dice-una-data → NO ACTION ✓. Tempi LLM 0,5-1,0 s (prompt più lungo di prima; primo colpo 1,4-1,8 s).
  **Limiti noti**: "No, the 3rd" con aprile nello stato → `March 3rd` (mese inventato: il 1,7B non compone giorno + mese dallo
  stato); "Never mind." secco → none (serve "cancel that"/"forget it"). Si vedono nel registro, non si mitigano.
- **Pagina HUD** (`static/hud/hud-app.js` riscritta): lo schermo è la resa dello stato FSM (tabella dei frame della
  specifica), `applyFsm` (con ritardo simulato > 0 passa da CHECKING, default 0 = RESULT diretto), `fsmEvent`, richiesta
  manuale (`check`/`book` con data/ora scritte, campi vuoti = mancanti), reset FSM, prompt di sistema nuovo (riga MISSING).
  Codice morto del vecchio flusso (anello microfono 12 s, trigger sul testo dell'omni, regex) rimosso. `db.html` mostra la
  FSM (stato, intento, campi, manca, esito, nota, ultima battuta ASR grezza = controllo della precisione delle date).
- Il registro delle verifiche contiene le prove `curl` di oggi (colonna "avviata da": curl).
- **Primo test dal vivo (15:37): l'omni non ha mai parlato — causa trovata nei log, non nel modello.** Tre websocket aperti
  in 140 ms (tre `startSession`: il bottone "Avvia" restava attivo fino a fine avvio, click ripetuti): il primo ha preso
  il worker, gli altri due sono finiti in coda; il microfono spediva alla variabile globale `session` = l'ultima creata
  (in coda) → 40 chunk mai arrivati al backend (nessun `input.append` registrato, backend fermo dopo il prepare); alle
  +42 s il socket in coda è stato chiuso e il contatore si è fermato a 40. Fix strutturale nella pagina: `startSession`
  non rientrante (bottone disabilitato al click) e microfono legato alla propria sessione. L'estrattore+FSM in quel test
  hanno funzionato: "I'd like to book a call" → book() → MISSING date,time; "31 March" → check (frase ambigua, senza
  "book"); "the second of April" → manca time; "At 12" → book(April 2, 12:00) → SLOT TAKEN (2 aprile tutto il giorno).
  Nota ASR: "31 March", "2nd April" trascritti bene. P2 (l'omni chiede la data) resta da verificare.

### 04/09 (16:00) — secondo test dal vivo: P2 PASSATA; difetto a valle sulla data "the second of April"
- **P2 passata**: al frame `MISSING: DATE` l'omni ha chiesto la data ("What date would you like to book your appointment
  for?"), al frame `MISSING: TIME` l'ora ("And what time on the second of April works best?"), al RESULT ha annunciato.
  Reazioni fluide, nessun silenzio lungo (RESULT diretto, senza CHECKING: P4 confermata su questo test).
- **Difetto**: "the second of April" → l'estrattore copiava la data com'era detta (regola "copy as spoken", mia) e il
  normalizzatore conosceva solo i giorni in cifre → chiave `second of april 15:00` ≠ `april 2 all-day` → slot nuovo,
  CONFIRMED falso (l'omni ha letto lo schermo: ha fatto il suo). Tre correzioni:
  1. **Regola FSM: campo obbligatorio = valido, non solo presente.** Data che non si riduce a `month d`, ora che non si
     riduce a `HH:MM` (o intervallo) → campo respinto (`rejected`, visibile in db.html e nel registro come NON CAPITO),
     resta COLLECTING con MISSING → l'omni richiede. Nessuna scrittura nel DB su chiave non canonica, chiunque la produca.
  2. **Contratto dell'estrattore: data in forma "Month D"** (come l'ora in HH:MM), mese dallo stato se detto solo il
     giorno. Sonde: "the second of April" → April 2; "March thirty-first at half past two" → March 31, 2:30 (→ 14:30
     per la convenzione 1-7 = pomeriggio); "the twenty-first of May" → May 21; "No, the 3rd" con aprile → **April 3**
     (prima: March 3rd); "Tomorrow at 9" → tomorrow (respinta dalla FSM → richiede la data) + 09:00.
  3. Normalizzatore del gateway: ordinali e numeri a parole (first…thirty-first) → cifre, per il form e per l'ASR.
  FSM via curl: book("second of april","15") con 2 aprile occupato → **SLOT TAKEN, chiave `april 2`** ✓;
  book("tomorrow") → COLLECTING manca date (respinta "tomorrow") ✓; time "soonish" → manca time ✓.
- **S1-mini (Superwhisper)** valutato su richiesta di Alessandro: normalizzatore post-ASR 0,6B, solo inglese, converte
  date/ore/numeri parlati e autocorrezioni. Non adottato ora: l'ASR non aveva sbagliato, duplica la conversione che
  l'estrattore già fa, terzo modello in catena (+0,2-0,3 s, +1,5 GB su GPU al limite), inutile in italiano. Candidato
  solo se il registro mostra errori sistematici sui numeri parlati dopo il contratto "Month D"; utile in
  `transcribe_sessions.py`.
- **DB azzerato** (slot, registro, FSM) su richiesta: le prove ripartono da zero. Prenotazioni di prova da inserire in
  db.html prima dei test (es. April 2 all day per D9c).
