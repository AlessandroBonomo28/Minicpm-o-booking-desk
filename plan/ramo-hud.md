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
