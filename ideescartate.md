# Idee scartate (con il perché) — così non le riproponiamo

Regola: qui finiscono le idee che abbiamo valutato e deciso di NON fare. Se una torna in
discussione, prima si rilegge la motivazione.

## 03/09/2026 — velocizzare ASR → testo → tool call (ramo HUD)

Decisione di Alessandro: si fa SOLO **VAD nel browser + trigger sul turno dell'utente +
ASR streaming su GPU**. Scartato tutto il resto:

- **Prefiltro deterministico** (regex "c'è una data/ora nel testo?" prima di chiamare il modello
  piccolo). Scartato: crea casini nel testing — non si sa quando scatta e quando no; meglio
  un comportamento uniforme (il modello viene sempre consultato) anche se costa qualche
  decimo di secondo.
- **Decisione in due passi** (1 token di classificazione, poi ~30 token di estrazione, al posto
  della chiamata aperta). Scartata: complessità in più per un guadagno (~1 s) non prioritario ora.
- **Cache del prompt con vLLM/SGLang** per il modello piccolo. Scartata: un servizio in più da
  installare e tenere su per ~0,3-0,5 s a chiamata.
- **Iniezione del frame lato server** (bypassare il giro browser → gateway → worker per portare
  l'HUD all'omni). Scartata: vale qualche decimo di secondo in media, richiede di toccare il
  backend. Il "pavimento" di 0-1 s è il clock a 1 Hz dell'omni e resta comunque.
- **Sidecar più grande** (Qwen3-4B/8B) per il tool calling. Non scartato del tutto: ultima
  leva, solo se il 1.7B con contesto giusto continua a sbagliare.
