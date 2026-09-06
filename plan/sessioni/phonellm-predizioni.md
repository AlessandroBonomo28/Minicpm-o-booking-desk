# Ramo phonellm — predizioni scritte PRIMA di misurare (06/09)
Domanda: un modello addestrato alle tool call telefoniche (PhoneLLM = Nemotron 3 Nano 30B-A3B + SFT Pipecat) fa meglio di
flash-lite come ESTRATTORE del nostro contratto (set/yes/no/cancel + riga di stato)?
Banco: regressione base (55 + 3 casi nuovi = 58) e dialogo (24 + 4 nuovi = 28), stesso prompt PROMPT_API, stesso contesto (6 righe).
Passo 1 (oggi, gratis): CONTROLLO con la BASE di PhoneLLM, nvidia/nemotron-3-nano-30b-a3b via Cline.
Passo 2 (serve un hosting: Modal o Featherless): PhoneLLM vero.

Predizioni:
- flash-lite sui set estesi: base 55/58 (fallira' "next free slot" come dal vivo), dialogo 25/28 ("yeah so did you check" e
  "Which one?" come dal vivo), ~0,9 s a chiamata.
- Nemotron base (generalista, 3,5B attivi, thinking forse non disattivabile via Cline): base 42-48/58, dialogo 15-20/28,
  1,5-3 s a chiamata se pensa, ~1 s se no.
- PhoneLLM (se lo misureremo): sopra la base di 5-10 punti sulla disciplina (domande non sono si', niente valori dal contesto),
  non necessariamente sopra flash-lite sulla normalizzazione (mesi/ordinali/ore) perche' allenato su altri strumenti.
Criterio: si prosegue con PhoneLLM dal vivo solo se batte flash-lite su ENTRAMBI i set, a latenza <= 1,2 s.

## Esiti passo 1 (06/09 13:35) — rapporti in logs_demo/extractor_eval/
| estrattore | base (58) | dialogo ctx0 (28) | dialogo ctx3 (28) | latenza |
|---|---|---|---|---|
| flash-lite (produzione) | 52 | 24 | 24 | 0,90 s |
| Nemotron 3 Nano base (via Cline, extra reasoning off) | 48 | 22 | 19 | 1,20 s |
Predizione: rispettata (base 42-48 previsti, 48 misurati; dialogo 15-20 previsti, 19-22 misurati).
Dove cade la base: disciplina, non normalizzazione. "Hello, how are you?" / "Thank you, bye!" / "pizza" -> cancel;
"Hmm, let me think" -> copia i valori dalla riga dell'operatore; "Which one?" -> set(april); "yeah so did you check" -> yes;
"15" -> giorno invece di ora. Sono ESATTAMENTE i difetti che la SFT di PhoneLLM dichiara di curare (tool call al momento
giusto, niente "fatto" senza fare). Quindi PhoneLLM parte da 48/22 e deve guadagnare >4 e >2 per pareggiare flash-lite.
Passo 2: serve un endpoint (Modal ufficiale, o Featherless con tool call nel testo). Criterio invariato: dal vivo solo se
batte flash-lite su entrambi i set a <= 1,2 s.
