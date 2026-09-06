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
