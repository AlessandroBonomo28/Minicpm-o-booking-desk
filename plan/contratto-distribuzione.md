# Contratto di distribuzione — da compilare PRIMA di ogni corsa di training

> Nato il 22/08/2026 dal fallimento di it07 in demo (degenerazione col preset) e dalla
> critica di Alessandro: "dovevi aspettartelo... ragionando con il paper e la struttura
> di MiniCPM-o 4.5, sappiamo come è stato addestrato questo modello".
>
> **Principio**: il modello vede in training una distribuzione di contesti; in deployment
> ne vede un'altra. OGNI differenza va enumerata qui prima di toccare la GPU, e per
> ciascuna si sceglie: ELIMINATA (training allineato al deployment) o GIUSTIFICATA per
> iscritto (perché è innocua, con la ragione strutturale). Un LoRA lega l'adattamento al
> contesto su cui è addestrato: più passi accumula, più è fragile fuori da quel contesto.
> Le voci di questo contratto si deducono dal paper e dal codice, non dagli esperimenti —
> gli esperimenti servono solo a verificare, non a scoprire.

## Cosa dice la struttura del modello (paper, Figura 2 + §2)

Il contesto duplex è: **Multimodal System Prompt = Text System Prompt + Reference Audio**,
poi il flusso di unità. Il reference audio è un componente strutturale (il paper: "can
accept multimodal system prompts that contain both text and reference audio, thus
supporting voice cloning"; il decoder vocale genera "based on the reference audio in the
multimodal system prompt"). Il modello è stato addestrato con quel prefisso presente e
variabile. Qualunque training che lo ometta o lo fissi sta campionando un angolo della
distribuzione — e il LoRA si lega a quell'angolo.

## Il contratto — stato al 22/08/2026

| # | dimensione | training (fino a it07) | deployment (demo) | verdetto |
|---|---|---|---|---|
| 1 | system prompt | fisso: "Streaming Omni Conversation." | preset italiano (lungo, registro, istruzioni) | ❌ **ELIMINARE**: addestrare col prompt del preset (`--system-prompt`) |
| 2 | reference audio | assente | `ref_it_test1.wav` (~8s) nel contesto | ❌ **ELIMINARE**: addestrare con lo stesso ref (`--ref-audio`) |
| 3 | reset della cache audio | mai (finestre ≤60 unità, cache mai piena) | `audio_past_key_values > 1500` → **reset a metà sessione** (visto nella repro col prompt lungo) | ⚠️ GIUSTIFICATA per ora: evento raro e post-reset il contesto torna simile all'inizio-sessione; da rivalutare se il degrado in demo compare dopo minuti |
| 4 | audio in ingresso | canale utente del corpus (podcast, campo lontano) + registrazioni di Alessandro | microfono di Alessandro (70,8% energia <300 Hz, misurato in via-minicpm) | ⚠️ GIUSTIFICATA in parte: i dati identità SONO il suo microfono; il corpus no. Leva futura: filtro/augmentation acustica sul corpus |
| 5 | force_listen warmup | non emulato | primi N chunk forzati a listen | ✅ innocuo: maschera solo l'avvio, nessun gradiente coinvolto |
| 6 | penalty/sampling | teacher forcing (nessun sampling) | penalty 1.15, T=0.7, top-k/p | ✅ knob di sola inferenza, calibrati sul base; da rimisurare solo se si cambiano |
| 7 | cap testo per chunk | target ≤26-28 char, parole intere | 28 char + grazia word-aligned | ✅ allineati (20/08) |
| 8 | canale/formato audio | 16 kHz mono lato utente | 16 kHz mono microfono | ✅ allineati (fix mixdown, 20/08) |
| 9 | silenzio post-turno | dati identità: coda di silenzio + gap | l'utente tace quando vuole | ✅ coperto dal mix identità+conversazione continua |
| 10 | concatenazione del testo tra chunk | unità codificate da sole (primo token SENZA spazio) | frontend concatena VERBATIM (`+=`) → parole incollate "chetu" | ❌ **ELIMINATA (22/08 sera)**: unità di continuazione codificate con spazio iniziale (it_09); e l'harness ora concatena verbatim come la demo (il vecchio `" ".join` mascherava il difetto) |
| 11 | modalità della pagina demo | unità solo-audio (`/audio_duplex`): nessun token video | **Omni** (`/omni`) inserisce in OGNI unità `<image>`+64 embedding visivi+`</image>` prima dell'audio | ❌ **CONFERMATA CAUSA DI LOOP (02/09, replay 3 bracci)**: frame nero uniforme → loop 0.61 e 22/24 parole incollate; solo-audio → sano. Da eliminare addestrando le unità con il blocco visivo (frame costanti/uniformi/vari) e gateando in contesto Omni |

## Regole operative

1. **Prima di ogni corsa**: rileggere questa tabella, aggiornarla se demo/preset/codice
   sono cambiati, e riportare nel log della corsa la riga "contratto verificato il ...".
2. **Ogni gate di valutazione esiste in DUE condizioni**: contesto di training E contesto
   di deployment (prompt+ref del preset). Un candidato si promuove solo se passa entrambe.
3. **Se si cambia il preset della demo** (prompt o voce), il contratto va ricompilato e il
   modello in produzione va rivalidato nel nuovo contesto: per il LoRA il preset È parte
   del modello.
4. Variare il contesto in training (più prompt/ref diversi) è la leva per la ROBUSTEZZA;
   fissarlo su quello del deployment è la leva per la FEDELTÀ. Con dati piccoli si sceglie
   la fedeltà (questa fase); la robustezza richiede dati su più contesti (fase futura).

## Registro

- 22/08 — creato; righe 1-2 eliminate con `--system-prompt`/`--ref-audio` nel trainer;
  corsa correttiva `duplex_it_08` = ricetta it_07 + contesto di deployment.
