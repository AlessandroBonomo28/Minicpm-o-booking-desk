# Ramo force-speak (07/09) — indagine sui modi per far parlare l'omni e sul contesto iniettato

## 1. I token del duplex e cosa si puo' iniettare
Nel modello (`MiniCPMO45/modeling_minicpmo_unified.py` l.4315-4350) i token di controllo sono:
`<unit>` `</unit>` (confini dell'unita' da 1 s), `<image>...</image>`, `<|listen|>`, `<|speak|>`, `<|tts_bos|>`, `<|tts_eos|>`,
`<|chunk_eos|>`, `<|chunk_tts_eos|>`, `<|turn_eos|>`, `<|tts_pad|>`.
- **Non esiste un token "fine turno del cliente".** Il paper (§3.1-3.2) e' esplicito: il cliente entra nel flusso solo come
  env-audio, "no longer treated as a privileged conversational role"; l'unita' e' g_k = [v_k; a_k; o_k] (visione, audio, uscita).
  Il passaggio del turno all'omni e' la SUA decisione `<|listen|>`/`<|speak|>` a inizio uscita di ogni unita' (LS formulation).
- `<|turn_eos|>` e' il token con cui l'OMNI chiude il proprio turno di parlato; `force_listen` lo inietta per chiudergli la bocca
  (l.5092-5108). Iniettarlo a turno gia' chiuso non "passa il turno": e' un no-op semantico.
- Quindi "passare il turno all'omni" = forzare `<|speak|>` alla decisione: e' `force_speak_override` (commit 31b5d52), lo specchio
  esatto di `force_listen_override`. La sequenza che ne esce (`<|speak|>` a j=0, poi testo) e' quella di ogni onset naturale
  (backend.log: 2365 righe `j=0 SPECIAL id=151706 '<|speak|>'`).
- `set_break_event` e' l'interruzione (barge-in): ferma il parlato, non lo avvia.
- `listen_prob_scale` (config di sessione, gia' nel processor: l.2201 di utils.py moltiplica il LOGIT di `<|listen|>`) e' una leva
  morbida: <1 rende il parlato piu' probabile a ogni unita'. Effetto collaterale: interrompe di piu' il cliente. Da misurare a parte.

## 2. Pulsanti nella pagina HUD (questo ramo)
- **Parla ora (force_speak)**: il prossimo chunk porta `force_speak=true`; se a j=0 il modello campiona `<|listen|>` con turno
  chiuso, il server lo sostituisce con `<|speak|>`. Il registro scrive "FORCE_SPEAK inviato con il chunk #N" e, 3 s dopo,
  "turno aperto a +x s" oppure "NESSUN TESTO" (turno vuoto `<|speak|><|turn_eos|>` o ignorato). Precedenza a force_listen e ai
  primi 3 chunk (avvio protetto). Prova offline interrotta dal crash di WSL: un solo campione, fondato
  ("Booking for October 7th at 4 p.m.? Is that correct?" con lo schermo WAIT FOR USER CONFIRMATION).
- **Stimolo audio**: il prossimo chunk manda `static/hud/cues/cue.wav` (16 kHz mono, <= 1 s) al posto del microfono: il canale
  su cui il modello e' addestrato a decidere. Il clip va registrato: `python tools/rec_app/server.py --port 8020`, una frase tipo
  "So?" o "Well?", poi copiare il wav in `static/hud/cues/cue.wav`. Se force_speak produce turni vuoti, questo e' il piano B.

## 3. Context injection e sticky context (da indagare dopo, qui il progetto)
Due modi per dare all'omni gli stessi valori dell'HUD come TESTO invece che come pixel (64 token di visione per frame):
- **(a) Testo dentro l'unita'.** In `streaming_prefill` (l.4614+) l'unita' e' `<unit>` + embed immagine + embed audio; si potrebbe
  fare `decoder.feed(embed_tokens(ids))` con una riga tipo `screen: NEW BOOKING, DATE: OCTOBER 7, MISSING: TIME` prima dell'audio.
  Fuori dal contratto di addestramento (nell'unita' non c'e' mai testo in ingresso): rischio che il modello lo tratti come
  propria uscita o lo continui. Costo ~20 token per unita' invece di 64.
- **(b) Sticky context = la regione "previous:" di upstream.** Il modo finestra `context` registra il prompt come
  `[prefix] [previous: <testo>] [suffix] [units...]` e a ogni taglio ricostruisce la regione con
  `decoder._rebuild_cache_with_previous(token_ids)` (utils.py l.1560-1690): un forward SOLO sui nuovi token + suffisso, e le
  unita' restanti vengono reindicizzate (RoPE) senza ricalcolo. E' esattamente una primitiva di iniezione di testo nel
  contesto protetto, refresh a comando, che il modello upstream tollera per costruzione (serve a conservare il testo generato).
  Progetto: metodo `duplex_set_context(text)` nel modello -> backend -> server (`input.context_text` sull'input.append, applicato
  prima del prefill) -> client che manda il testo dello schermo quando il CONTENUTO cambia (stessa impronta usata per il
  frame evento). Il testo dello schermo sta cosi' subito dopo il prompt, sempre, anche dopo i tagli. Costo: un forward di
  ~30 token quando cambia lo stato, zero token per unita'. Da provare da solo (senza frame) e insieme ai frame.
  Predizione: il contenuto delle risposte migliora o resta uguale (il testo e' il canale nativo dell'LLM); il "quando" non
  cambia (resta acustico: F1 della giuria). Non e' una modifica al modello: usa un metodo che esiste.
- Esperimento gratis prima di tutto: modo finestra `context` cosi' com'e' (`sliding_window_mode: 'context'`, 24 unita',
  500 token di previous): l'omni conserva il proprio testo generato nella regione protetta dopo i tagli. Variabile singola.
