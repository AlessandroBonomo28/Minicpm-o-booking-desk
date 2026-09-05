# Calendario — assistente vocale duplex italiano

> Roadmap operativa concordata il 21/08/2026. **Questo file si aggiorna man mano**: ogni
> voce passa a ✅ (fatto, con esito) o viene rivista con la data nuova e il perché.
> I dettagli tecnici stanno in `plan/audit-20agosto-fable.md` e `plan/stadio-identita.md`.

## Il traguardo

**v1 (comportamento)** = in un test dal vivo di Alessandro: parole intere, risponde
all'utente (niente eco in apertura, niente auto-dialogo, niente appropriazione del nome),
niente loop, non monologa oltre misura, pertinente in italiano.
**v2 (voce)** = v1 + pronuncia italiana accettabile all'ascolto (modulo TTS, percorso
separato che non tocca l'LLM).

Fuori perimetro (dichiarato): backchannel a densità umana (limite strutturale del formato
a 1 Hz), scala dati `mie-ore` (solo se la v1 mostra limiti colmabili con più dati).

---

## Ven 21/08 — corsa strutturale + preparazione stadio-ruolo

- [x] Corpus v6 (canale utente, turn_eos veri, maschere corrette) — fatto (notte)
- [x] `duplex_it_03` da zero + selezione blocco 4 + test dal vivo #1 — fatto; emersi
      loop-che-ignora-interruzioni, eco in apertura, auto-dialogo nel silenzio
- [x] Decisione: niente pezze (breaker rimosso) → cura nel training
- [x] Trainer: supervisione `chunk_eos`/`turn_eos` + holdout + audio identità
- [x] Bersagli maestro (ancorato + cancello d'accordo): 104/160, qualità ispezionata
- [x] **15:40** — `duplex_it_04` completata. Metriche sui blocchi: **loop 0-1/18 su
      TUTTA la corsa** (it_03 aveva 4/18 — la supervisione eos ha funzionato),
      impersonazione stabile a 1/18 (it_03 finiva a 5/18), frammentazione 0-2/1000,
      risposte che si ACCORCIANO coi passi (85→63 char: sta imparando a fermarsi) e
      nessun degrado nei blocchi tardi, per la prima volta.
- [x] **17:20** — eval comportamentale su holdout: **`duplex_it_04` BOCCIATA** al
      cancello. La supervisione eos a peso pieno rende il modello quasi muto nella
      conversazione continua (speak 0.00-0.07 vs 0.66 umano) — invisibile nelle eval a
      domanda+silenzio, intercettato dall'holdout prima di promuovere. Notizia buona
      inattesa: su holdout **it03_b4 non monologa** (speak 0.508 vs 0.658 umano, TOR
      0.645) — l'eccesso di parola era in parte artefatto del campione; il problema
      residuo e' il RUOLO (auto-dialogo, eco), competenza dello stadio-ruolo.
      **Conseguenze**: base per lo stadio-ruolo = it03_b4 (non it04); trainer con
      `--eos-weight` per future corse corpus (~0.2, mai piu' peso pieno); date INVARIATE
      (it04 era un miglioramento parallelo, non un prerequisito dello stadio-ruolo).
- [x] **18:30** — bersagli rigenerati dopo DUE bug trovati nei cancelli del maestro
      (`tion$` che uccideva l'inglese; `<think>` mai chiuso che buttava risposte buone):
      **117 bersagli** (111 IT + 6 EN buoni, ispezionati; 2 meta-risposte EN eliminate).
      Dati stadio-ruolo: 136 esempi (106 IT + 30 EN replicati, ~1:3.5 — non 1:1: pochi
      bersagli EN di qualita'; il sensore anti-oblio resta l'eval sulle clip EN escluse).
      Le 8 clip dell'eval ESCLUSE dal training (prima erano dentro: eval era in-sample).
- [x] **18:40-19:15** — corsa stadio-ruolo `duplex_it_05` completata: metriche di
      CONTENUTO perfette (impersonazione 0/18 negli ultimi 5 blocchi, loop 0 ovunque,
      inglese stabile — il ruolo si impara). MA **bocciata al gate holdout**: muta in
      conversazione continua (speak 0.000), pur rispondendo bene nel formato
      domanda+silenzio. Stesso sintomo di it04, unica variabile comune: la
      **supervisione eos** (it03, sano su holdout, non l'aveva).
- [x] **19:30-22:00** — `duplex_it_06` (= it05 senza supervisione eos): contenuto ok,
      ma **muta anche lei su holdout** (speak 0.000). Verdetto dell'esperimento a
      variabile singola: la causa del mutismo dello stadio-ruolo e' il **FORMATO** dei
      dati identita' (ascolta-tutto → parla-solo-nel-silenzio), non la supervisione eos.
      Due cause di mutismo ora confermate indipendentemente: eos-supervision sul corpus
      (it04 vs it03) e formato QA puro (it06 vs it03).
- [x] **22:15** — attivato il piano B: file misto 50/50 (136 identita' + 136 finestre di
      conversazione continua v6, solo lato train). **`duplex_it_07` accodata per la
      notte** (parte a gate it06 finito): stessa ricetta, mix, poi gate holdout
      automatico sui blocchi 8 e 12. Risultati pronti per sabato mattina.

## Sab 22/08 — verdetto stadio-ruolo

- [x] **02:30 (notte)** — `duplex_it_07` (mix 50/50) COMPLETATA e **PASSA TUTTI I
      CANCELLI** al blocco 12: impersonazione **0/18**, loop 0, frammentazione ~1,
      inglese intatto, e su holdout **parla** (speak 0.400, TOR 0.618 — vicino a
      it03_b4 e ben sopra il base). Risposte qualitative da assistente vero
      ("Certo, potrebbe essere un errore di password... Hai controllato...?").
      Probe finale it03_b8: la loquacita' libera DECADE coi passi accumulati anche su
      solo corpus (0.508→0.225 da 300 a 600 passi) — il formato QA la accelerava
      soltanto; il mix la PROTEGGE (it07 a 600 passi accumulati: 0.400). Tre cause
      isolate in tre esperimenti a variabile singola, tutte documentate.
- [x] **02:45** — merge di it07_b12 e demo preparata.
- [x] **Mattina** — test dal vivo #2 su it07_b12: **FALLITO** (eco degenere, "senza
      freni"). Causa trovata col metodo nuovo: contesto di training (prompt 4 parole,
      zero ref audio) ≠ contesto demo (preset = prompt 419 char + ref audio) — deducibile
      dalla Figura 2 del paper, confermato dalla repro (stesso ckpt: 0.400 nel contesto
      training, 0.892 logorroico col preset). Da qui: `plan/modus-operandi.md`,
      `plan/contratto-distribuzione.md`, `CLAUDE.md`, `--context-preset` in trainer/eval.
- [x] **11:10-15:30** — `duplex_it_08` = ricetta it_07 ma ADDESTRATA NEL CONTESTO DEL
      PRESET. Gate nel contesto demo: b12 con TOR 0.957 (= umano), speak 0.875.
      Anteprima del test dal vivo (8 clip-sonda di Alessandro, contesto demo, free-run):
      **b12: impersonazione 0/8, loop 0/8**, risposte da assistente su tutte le sonde
      (b8 scartato: 2 impersonazioni vere). Merged: `it08_b12_merged.pt`, demo su.
- [x] **~17:30 — Test dal vivo #3 su it08_b12: 🎯 V1 COMPORTAMENTALE ACCETTATA**
      (verdetto di Alessandro: "figo, ci sta" — con 2 giorni di anticipo sul piano).
      7 turni coerenti, ruolo mai perso ("Mi chiamo Assistente, sono qui per aiutarti"),
      segue i cambi di argomento, ricorda il contesto, zero loop, zero auto-dialogo.
      Difetti residui indicati da Alessandro: (1) parole INCOLLATE ai confini di chunk
      ("chetu", "ideabellissima") — diagnosi immediata: il trainer codifica le unita' di
      continuazione senza spazio iniziale, il frontend concatena verbatim; e' l'altra
      faccia della vecchia frammentazione; (2) pronuncia ancora cinese-inglese (fase v2).
- [x] **17:52** — `duplex_it_09` lanciata = it_08 + spazio iniziale sulle unita' di
      continuazione (variabile singola). Gate automatico a fine corsa (~21:45).
- [x] **18:00** — corsa **pronuncia `pron_02`** accodata dopo il gate: TTS 348M, LLM
      congelato (componibile con qualunque checkpoint LLM), 2000 passi, ckpt ogni 400,
      sidecar acustici copiati in locale. Gira nella notte.

- [x] **21:50** — gate + misura spazi di it_09: **b12 = 100% confini corretti (49/49)**
      (b8 a 70% = stato di transizione: a 300 passi la nuova convenzione ha vinto sulla
      vecchia — niente rifondazione della lignaggio). Comportamento in linea con it08.
      Scoperto e corretto per strada: l'harness faceva `strip()+" ".join` e MASCHERAVA
      le incollature (riga 10 del contratto); ora concatena verbatim come la demo.
      Merged: `it09_b12_merged.pt`. Corsa pronuncia `pron_02` partita (~22:00), nella
      notte, checkpoint ogni 400 passi.

## Dom 23/08 — verifica finale v1 + ascolto pronuncia

- [x] Mattina: **test #4 su it09_b12 — parziale**: turno 1 pulito, ma dal turno 2
      incollature ("puoifare") e nei turni lunghi auto-dialogo; troncamento da reset
      cache audio a 1500 (riga 3 contratto: giustificazione sbagliata → da eliminare).
      Verdetto pronuncia su pron_02: **non migliorata** — ma corsa sporca (3 variabili
      mie non controllate: canale fisso, contesto vecchio, dati v6 con pochi target).
      V1 (it08_b12) **archiviata read-only** in training/releases/v1_comportamentale/
      su richiesta di Alessandro.
- [x] **10:40-14:45** — `duplex_it_10` = it_09 + dati identita' MULTI-TURNO (80 sessioni
      2-4 scambi) + nuovo **gate multi-turno**. ESITO: **tutti i gate verdi** —
      confini 104/104 (100%) su ogni indice di turno, auto-dialogo 0/9, impersonazione
      reale 0/9 (2 flag = falsi positivi ispezionati), TOR 0.957 = umano.
      Merged `it10_b12_merged.pt`, demo su.
- [x] **Test dal vivo #5 su it10_b12**: comprensione perfetta, ruolo tenuto su 5 turni,
      spazi quasi perfetti. Difetto dominante rimasto: **la voce tronca la frase**
      (testo completo, audio a metà). Diagnosi strutturale: densità testo insegnata
      (23 char/unita') ~doppia della velocità della bocca (isocronia 25 token=1s) +
      valvola tts_pad mezza morta nel fork. Decisione con Alessandro: **doppio binario**
      (fix nativo + prototipo cascata CosyVoice2) e poi training lungo.

- [x] **Pomeriggio (23/08)** — lavoro sul troncamento voce, con esiti:
      (a) indagine tts_pad/flush COMPLETATA: il flush prima del reset e' GIA' corretto
      nel fork (sospetto archiviato dopo lettura); la valvola `tts_pad` e' proibita dal
      fork alla nascita (riga 4333) — riabilitarla resta un'opzione, solo se servira';
      il TTS e' autoregressivo lungo il turno e il ritardo accumulato viene tagliato a
      fine turno → **la densita' del testo e' l'intero fix** (audit §9septies);
      (b) dati identita' **v3 a densita' parlato reale** (11 char/unita' vs 23) pronti;
      (c) corsa **it_11** partita ma UCCISA da un riavvio WSL al blocco 2 — da rilanciare;
      (d) scoperto che l'install CosyVoice2 e' difettoso (genera 3x i token, mai
      validato all'orecchio a suo tempo): per un'eventuale cascata il motore e' XTTS v2.
      [Il piano settimanale autonomo del 23/08 e' stato ANNULLATO da Alessandro insieme
      al vincolo internet e alle sveglie: si prosegue col piano classico qui sotto.]
- [x] **23:20 (anticipato a sabato notte)** — `pron_02` completata in 65 min (2000 passi,
      loss acustica 6.1→2.8) e campioni d'ascolto GIA' generati per baseline + 5
      checkpoint (5 frasi diagnostiche ciascuno):
      **C:\Users\alecy\Desktop\ascolto_pronuncia\** (baseline/, step000400..step002000).
      Demo su con it09_b12, pronta per il test #4.
- [ ] Alessandro: **test dal vivo #4** (https://localhost:8006/audio_duplex) → conferma v1
      + **ascolto della cartella** → dirmi il checkpoint preferito.
- [ ] Poi: integrazione TTS scelto nel demo (come caricare tts.pt accanto al pt LLM) →
      demo completa v1+voce.

## Dom 23/08 — buffer di iterazione

- [ ] Una corsa correttiva completa + analisi ci sta in giornata (~6h a giro).
      Se sabato è andato bene: si salta, o secondo test con calma.

## Piano da qui in avanti (aggiornato 23/08 sera, dopo l'annullamento del piano speciale)

**Stato: la v1 comportamentale e' FATTA e archiviata** (it08_b12 accettata; it10_b12 la
supera su multi-turno ed e' il candidato corrente). Restano i due assi voce.

- [x] **1. it_11 — fix del troncamento voce: ✅ CONDIZIONE OTTIMA (23/08, 21:15)**.
      Tutti i gate verdi su DUE repliche indipendenti: **voce/unita' 1.00-1.13**
      (prima: frasi tagliate), confini 100% su ogni turno, auto-dialogo 0/9,
      impersonazione reale 0, comportamentale sano (speak 0.858, TOR 0.891).
      **Archiviata**: `training/releases/v1_3_voce_intera/` (read-only). Demo su.
      Strumenti versionati nel repo: `training/run_role_stage.sh`,
      `training/multiturn_gate.py` (misura voce/unita'; fix: leggere audio_data
      base64, non audio_waveform). [Lezione: /tmp muore coi riavvii → strumenti in repo.]
- [ ] **2. Test dal vivo su it_11** → se regge, promozione a default demo (v1.2).
- [x] **3. pron_03 — BOCCIATA all'ascolto (01/09)** e l'audit adversariale (workflow,
      4 lettori + verificatori) ha trovato PERCHE': tre errori strutturali confermati —
      (a) 🔴 bersagli acustici dal canale FISSO 0 su corpus bidirezionale → meta'
      training coi token del parlante sbagliato (55% run di silenzio: la loss crollava
      su prior banali, "emetti cio' che senti" = analogo acustico del mixdown);
      (b) training per-unita' isolata vs inferenza a KV incatenata sul turno;
      (c) etichette testo/audio sfasate ai confini. Dettagli: audit §9octies.
- [x] **3bis. pron_04 — COMPLETATA (01/09, 21:23)**: sidecar a 2 canali su TUTTI i
      10.362 wav del corpus (fatti una volta per sempre), 6000 passi a turno intero,
      loss finale ~4.9 (niente crollo sospetto: il compito era vero), 6 checkpoint,
      campioni verificati (pesi caricati "mancanti 0" x6) in
      **C:\Users\alecy\Desktop\ascolto_pron04\** + baseline. Demo v1.3 su.
      IN ATTESA DELL'ORECCHIO DI ALESSANDRO → decide strada A (scala pron) o B (XTTS).
      (piano originario della corsa:
      sidecar rigenerati a 2 CANALI (target = canale dell'agente della finestra) +
      training A TURNO INTERO interleaved = equivalente esatto dell'inferenza.
      Segnale gia' visto allo smoke: loss iniziale 4-7 che NON crolla subito = il
      compito ora e' vero. Catena automatica: sidecar → 6000 passi → campioni in
      C:\Users\alecy\Desktop\ascolto_pron04\ → demo v1.3 su.
      *Cancello: orecchio di Alessandro.*
- [ ] **4. Se l'orecchio boccia anche pron_03**: decisione cascata con XTTS v2
      (l'install CosyVoice2 e' difettoso; XTTS ha cache locale e fu giudicato
      accettabile all'ascolto) — scelta d'architettura da fare INSIEME, non pezza.

- [ ] **5. Omni italiano — training con blocco visivo (via appuntata il 02/09, NON lanciata
      per scelta di Alessandro)**. Causa misurata: v1.3 in Omni degenera (loop 0.61,
      22/24 parole incollate) perche' ogni unita' Omni contiene `<image>`+64 embedding
      visivi+`</image>` prima dell'audio, sequenza mai vista dalla LoRA (solo-audio).
      Piano quando si decidera' di farlo:
      1. trainer: inserire il blocco visivo nell'unita' (dopo `<unit>`, prima dei 10
         embedding audio), token visivi NON supervisionati (~20 righe);
      2. fotogrammi: mix uniformi (nero/grigio: il caso che rompe) + costanti realistici +
         qualche frame vario;
      3. corsa: stadio-ruolo dall'adapter it11, ~300 passi (<1 h);
      4. gate: quelli audio invariati + gate in contesto Omni col replay a frame
         (`tools/replay/replay_omni_frames.py`, bracci reale/nero/solo-audio);
      5. predizione: frame nero da loop 0.61 → ~0, incollate 22/24 → ~0, audio puro invariato.
      Nel frattempo Omni+v1.3 si usa con camera scoperta e scena reale (braccio A: regge).

---

## Incertezze dichiarate (per leggere i ritardi, se arrivano)

1. Finora OGNI corsa ha rivelato qualcosa di nuovo — è il metodo, non un incidente: ogni
   giro chiude una causa. Il buffer di domenica esiste per questo. Se emerge un problema
   di categoria nuova, lunedì slitta e viene scritto QUI subito.
2. Lo stadio-ruolo è la scommessa del piano: meccanismo giusto (precedente Moshi), primo
   tentativo con ~104+20 esempi. Se servono più dati: bersagli anche dal lato-utente del
   corpus (pipeline pronta, +1 giorno).
3. I cancelli che nessuna metrica sostituisce sono i test dal vivo di Alessandro
   (~15 min l'uno: sabato, lunedì, e all'ascolto della voce).

## Registro aggiornamenti

- 21/08 — creato (Fable), dopo l'audit e la corsa duplex_it_03.
- 02/09 — **Demo ibrida consegnata** (pron_04 + opzione XTTS): spunta "XTTS (ita)" nella
  UI (attiva = doppiatore esterno XTTS frase-per-frase; spenta = TTS interno pron_04).
  Backend con pt combinato `training/runs/pron_04/v13_pron04_merged.pt` (llm it11_b12 +
  tts pron_04, missing 821/unexpected 0). Verdetto orecchio su pron_04: "più
  italianizzato ma non sufficiente" → ibrido come da decisione (input+decisione nativi,
  laringe esterna).
- 02/09 — **Risolta la serie di "disconnessi WSL"**: non era la webapp né la VRAM — il
  caricamento del modello materializzava ~30GB in RAM CPU su VM da 31GB (misurato con
  verbale OOM del kernel). Due fix di causa committati: `torch.load(..., mmap=True)` per
  i pt (570850a) e `from_pretrained` in bf16 + `low_cpu_mem_usage` (282c434) → picco
  boot da ~30GB a **3.9GB**, boot da ~4min a ~30s. Lanciatori durevoli nel repo:
  `tools/run_demo_hybrid.sh` (ibrida) e `tools/run_demo_v13.sh` (controllo v1.3);
  log in `logs_demo/`.
- 02/09 (notte) — **XTTS SCARTATO da Alessandro** ("fa un casino con la WSL"): rimosso
  da backend, UI e script d'avvio (commit 60c4545). La demo default torna alla v1.3
  pura (it11_b12, TTS interno, delay 600ms di default). L'asse voce si risolve SOLO
  per via nativa (training). `tools/cascade_tts_server.py` resta come strumento fuori
  dalla demo. Nota: i pesi v1.3 sono intoccati (file read-only del 23/08); i fix di
  caricamento RAM restano perche' curano i crash WSL e non toccano i valori dei pesi.
- 02/09 (notte, 03-04) — **A/B risolutivo sulla "regressione"**: Alessandro sentiva loop
  e mancate interruzioni; sospettava i cambi backend. Revert letterale all'epoca buona →
  invariato; strip a upstream PURO → PEGGIO (loop "È tutto bene? È tutto bene?",
  frammenti "forn ire"), come da predizione scritta: i fix decodifica (segno penalità
  ripetizione + 1.15, taglio a confine parola, listen_id corretto) SERVONO → ripristinati.
  Causa vera dei sintomi, misurata dalle registrazioni sessione: **microfono Windows** —
  zeri digitali a raffiche su Firefox E Brave (28/43 chunk), eco della voce AI dagli
  altoparlanti (correlazione 0.51-0.59 col mic). Da fare: disattivare "miglioramenti
  audio" di Windows / provare cuffie. Il modello v1.3, a input pulito, ascolta e
  risponde a tono (sess_c0ac33: 48 ascolti/51).
- 02/09 (notte, ~04:30) — **A/B base vs v1.3 sull'interruzione, misurato**: il BASE
  upstream ignora il barge-in esattamente come v1.3 (Lx3 poi Sx22 con la voce di
  Alessandro nei chunk mic) → nessuna regressione nostra; il barge-in a meta' frase
  non e' nel platform (per questo esiste il bottone Force Listen). Il "si interrompe
  bene" del periodo buono era turn-taking rapido (turni corti, length_penalty 1.05),
  non barge-in. Eventuale barge-in vero = potenziamento futuro via cedimenti reali
  del corpus (sonde artificiali rifiutate da Alessandro). Demo ripristinata: v1.3 +
  fix decodifica + 600ms.
- 02/09 (pomeriggio) — **Due mondi per la demo**: `tools/run_demo_v13.sh` (nostri fix +
  pesi v1.3) e `tools/run_demo_base.sh` (modello base + CODICE UPSTREAM PURO, via
  worktree git `../MiniCPM-o-Demo-upstream-puro` al commit 50b0865: i fix di decodifica
  alterano il campionamento per qualunque peso, quindi "originale" = pesi base E codice
  puro). Il preset nella UI cambia solo prompt/voce/taratura, mai i pesi. Consegnato
  anche il PDF divulgativo `docs/recap-minicpm-o-italiano.pdf` (sez. 2b: 2.6 vs 4.5).
- 02/09 (sera) — **SCOPERTA MODALITA'**: Alessandro ha testato finora la pagina Audio
  Duplex (`/audio_duplex`, mode=audio) — che E' il contesto di tutto il nostro
  training/gate — ma trova che la pagina Omni (`/omni`, mode=video: stesso loop 1Hz +
  un fotogramma webcam per unita', length_penalty default 1.0, preset nativo inglese)
  "funziona davvero a turni". La pagina Half-duplex e' a turni per costruzione (VAD
  server, il client non manda audio mentre l'AI parla). CONSEGUENZA: se la modalita'
  d'uso diventa Omni, il contratto di distribuzione cambia (token video in ogni unita')
  e v1.3 va ri-gateata in quel contesto. Aggiunto preset italiano per Omni (4e0cd1b) e
  applicazione del length_penalty da preset nella pagina Omni.
- 02/09 (sera) — **Prompt nativo vince, misurato dal vivo**: pagina Audio + "Streaming Omni
  Conversation." → turni max 9-14 s, ascolto dominante (L 70-77 vs S 25-40), cedimenti
  33-60% con latenza 0.7-1.4 s; con il prompt lungo turni 17-23 s; Omni+nativo monologhi
  26-42 s. Il replay a 3 bracci (interruzioni asincrone) non lo vedeva: dal vivo il timing
  adattivo di Alessandro conta. Lezione strutturale: il prompt di deploy deve stare vicino
  al contesto di training del base (3 parole). Aggiunto preset "Italiano (prompt nativo)"
  in audio_duplex e omni, entrambi gli alberi. Da valutare: ri-addestrare v1.x con
  contesto nativo+riga lingua invece del paragrafo di istruzioni.
- 02/09 (sera) — **Perché Omni "risponde mentre parla" e Audio no** (paper §4.3 + FAQ
  upstream): i dati full-duplex di training contengono SEMPRE il video (segmenti a bassa
  rilevanza audio-visiva scartati) → le unità solo-audio sono fuori distribuzione per il
  riflesso "rispondi a domande nuove mentre parli"; la FAQ lo ammette ("may not
  immediately respond… while speaking", solo per Audio; e "LP 1.3 → interruption
  difficult"). Le mie metriche misuravano il CEDERE il turno (nessuna pagina forte),
  non il virare sul contenuto. PROSSIMO ESPERIMENTO (variabile singola): fotogramma
  COSTANTE in ogni unità dalla pagina Audio (nello screenshot Omni la webcam era
  coperta e andava comunque meglio) → se basta la presenza dei token video, si porta
  nel training set (unità italiane + frame fisso).
- 02/09 (sera, 17:45) — **Omni + v1.3 va in loop: causa isolata con replay a 3 bracci**
  (stessa sessione italiana di Alessandro rimandata al backend v1.3): solo-audio →
  sano (loop 0.00, giunzioni incollate 0/7); fotogrammi reali (camera scura) → sano
  (0.00, 1/20); **fotogramma NERO uniforme → degenera** (loop 0.61, 22/24 parole
  incollate, 25 speak/3 listen) = la firma vista dal vivo. La LoRA non ha mai visto
  `<unit><image>V64</image>audio`: con un'immagine uniforme l'embedding visivo spinge
  l'LLM adattato in un attrattore ripetitivo e rompe la convenzione degli spazi.
  Cura strutturale: addestrare le unità italiane CON il blocco visivo (frame costanti +
  uniformi + qualche frame vario), stadio-ruolo da it11 (~300 passi), gate anche in
  contesto Omni (replay con frame). Strumenti di replay salvati in tools/replay/.
- 03/09 — **Ramo HUD costruito** (spec di Alessandro: il frame come clock, non come store):
  pagina `static/hud/hud.html` (schermo operatore a 5 stati, frame SOLO al cambio, simulatore
  backend con esito/ritardo, auto-trigger sul testo del modello, registro "REAZIONE +x s"),
  launcher `tools/run_demo_hud.sh` (codice ramo ita + pesi BASE), doc `plan/ramo-hud.md`.
  Nessuna modifica al backend. In attesa del test interattivo di Alessandro (Test 1).
  Test 2 (iniezione di testo) NON costruito: richiede estensione del backend, dopo il verdetto.
- 03/09 — **Tool calling nativo su MiniCPM-o 4.5: testato, NO.** Il tokenizer ha template e token
  `<tool_call>`/`<tool_response>` (eredità Qwen3-8B) ma con il blocco `<tools>` esatto il base
  inventa la risposta invece di chiamare la funzione (3 sonde). Via percorribile: frase-segnale
  nello stream di testo ("controllo un attimo" → il backend agisce) + ritorno via HUD (ramo HUD).
- 04/09 — **Ramo HUD, laterale veloce**: VAD nel browser + trigger sul turno utente + ASR GPU
  (decisione di Alessandro; il resto in `ideescartate.md`). NPU Intel AI Boost verificata: c'è,
  ma invisibile da WSL → piano B via servizio Windows/OpenVINO se la VRAM stringe.
- 04/09 (sera) — **Ramo HUD: FSM della prenotazione specificata** in `plan/ramo-hud.md` (stati,
  frame per stato, contratto dell'estrattore, D8-D11, predizioni P1-P4). Decisioni: FSM nel codice
  (il 1,7B estrae soltanto), HUD = stato non istruzione, campi raccolti mostrati, niente stato
  "prendi tempo" (RESULT diretto: misura a lato sui silenzi di 30 s). Da implementare in 5 passi;
  gate = test dal vivo di Alessandro, cuffie obbligatorie.
- 04/09 (sera) — **FSM della prenotazione implementata** (gateway + estrattore + pagina HUD + db.html), provata a
  tavolino con curl e con testi scritti. Scoperta strutturale: con tre strumenti separati il 1,7B riempie i campi a
  forza; con UN solo strumento `request(intent, date|null, time|null)` e SOLO le righe dell'utente in ingresso
  smette (dettagli e limiti in `plan/ramo-hud.md`). Gate: test dal vivo D8-D11 di Alessandro (cuffie).
- 04/09 (16:00) — **P2 passata dal vivo**: l'omni chiede data e ora seguendo MISSING sullo schermo e annuncia
  l'esito. Difetto a valle ("the second of April" non canonicalizzato → CONFIRMED falso) corretto alla radice:
  FSM accetta solo campi validi (altrimenti richiede), estrattore emette "Month D", normalizzatore con numeri a
  parole. S1-mini valutato e rimandato (motivi in plan/ramo-hud.md). DB azzerato per le prove pulite.
- 04/09 (17:30) — **Contesto misurato** (~18 tok/s, 3.5k in 3 min) e **finestra scorrevole duplex accesa per
  sessione** (upstream l'aveva a off; 8k era solo l'auto-stop del client). Pannello HUD mostra KV e scorrimenti.
  Prossimo: basic vs off a variabile singola, poi soglie più basse se il degrado del minuto 2-3 resta.
- 04/09 (19:30) — **Sessione da 6,5 min coerente** con trp 1,0 + finestra basic (4 tagli, nessun degrado): la
  penalità di ripetizione era la causa dello sbrodolamento. Timeout gateway video 300→900 s. Richiesta su
  **tre campi indipendenti** (mese/giorno/ora, ordine libero) in estrattore e FSM; regressione dell'estrattore
  `tools/tool_agent_eval.py` 55/55. Prossimo: puntatore senza valore per "yes"/"that day".
- 05/09 — **Stati CONFIRM/DONE**: l'estrattore risolve "yes"/"that day" leggendo l'offerta dallo STATO (15/20 sul
  set di dialogo, contro 13/20 con le righe di dialogo che riportano le copie). Il silenzio a fine sessione non è
  KV/timeout: l'omni parla solo dopo un frame, e sempre meno (test basic vs off da fare). Regressioni 55/55 e 15/20.
- 05/09 — **Architettura teorica scritta** (`docs/architettura-hud-algebra.pdf`): HUD come linguaggio, eventi come
  algebra; piano del ramo `omni-eventi` (solo scritto). Senza toccare l'omni: decisione anticipata alla pausa,
  schermo a due metà (da giudicare dal vivo); decodifica vincolata misurata e scartata (44 vs 47). Estrattore:
  tre strumenti fissi + stato di conferma per le prenotazioni, cloud flash-lite 51/55 e 24/24.
- 05/09 (pom.) — Decimo test: ping-pong mese/giorno → due correzioni nell'algebra (merge sempre in raccolta; slot
  occupato = campo respinto, ore libere nello stato). Schermo a due metà di default. Decisione anticipata alla
  pausa confermata dal vivo (frame a 0,3-0,6 s dalla fine della frase).
