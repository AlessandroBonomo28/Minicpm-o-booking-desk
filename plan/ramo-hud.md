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
