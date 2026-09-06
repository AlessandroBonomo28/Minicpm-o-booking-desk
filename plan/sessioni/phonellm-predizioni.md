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

## Passo 1b (06/09): "un LLM piu' forte risolve?" — predizioni PRIMA di misurare
- claude-sonnet-5: base 55-57/58, dialogo 26-27/28 (le domande "did you check" e "Which one?" le prende; "Tomorrow at 9" e
  "next free slot" forse no), latenza 1,5-2,5 s a chiamata (troppo per la decisione alla pausa: +1 s percepito).
- gemini-3.5-flash: base 54/58, dialogo 25/28, ~1,1 s.
Cosa NON puo' cambiare un modello piu' forte: slot occupato che chiude la richiesta, atto nascosto/silenzio, ore storpiate dall'omni.
Esito sonnet-5 (13:41): base 55/58, dialogo 27/28 e 27/28, latenza 2,35-2,8 s, 7 chiamate fallite lato provider su 114.
Predizione rispettata su accuratezza e latenza. Prende "did you check", "Which one?", "thank you"; perde "next free slot" e
tre numeri secchi ("15", "The 2nd.", "Tomorrow at 9" -> set vuoto). gemini-3.5-flash NON misurato (Alessandro: gia' noto).

## Passo 2 (06/09 pom.) — HARNESS, non modello (Alessandro: "tutto sta nel dare il giusto contesto")
Sonda: minimax/minimax-m3:free (gratis; batterie con Sonnet/flash solo con autorizzazione).
Harness v2: domanda aperta citata parola per parola con i valori; stato TAKEN esplicito ("what's free" = set check);
TODAY dichiarato; regola "i valori solo dalla riga NOW del cliente"; "domanda/dubbio non e' un si'".
Predizioni PRIMA: minimax legacy base ~46/58, dialogo ~20/28; minimax v2 base +4 (50), dialogo +5 (25): prende "did you check",
"Which one?", "next free slot", "when is free"; rischio: copie dei valori citati (innocue in CONFIRM per idempotenza, ma
misurate come FAIL se compaiono in casi che li vietano).
Nota: minimax-m3:free e' a tetto giornaliero (429/500 via OpenRouter); usato minimax/minimax-m3 a pagamento: ~0,00014 $ a chiamata,
~2 centesimi per giro di banco.

## Esiti passo 2 (06/09 13:45-14:05), minimax-m3, tre giri
| harness | base (58) | dialogo ctx0 (28) | dialogo ctx3 (28) | latenza |
|---|---|---|---|---|
| legacy | 53 | 23 | 21 | 1,4 s |
| v2 (domanda citata, TAKEN esplicito, TODAY, regole valori) | 54 | 25 | 27 | 1,4 s |
| v3 = v2 senza TODAY | 54 | 24 | 25 | 1,4-2,4 s (provider lento, 3 errori) |
Predizione: rispettata in direzione (dialogo +2/+6), sotto sulla base (+1 invece di +4): TODAY faceva copiare la data di oggi
("book a desk" -> september 6), tolto. Rumore tra giri uguali: +-2 casi (temperatura 0 ma provider non deterministico).
Cosa ha sciolto l'harness (legacy -> v2/v3, con contesto): "yeah so did you check" e "Yes, but did you actually check?" non
sono piu' un si'; "Which one?" non porta piu' aprile; "next free slot" diventa check (a volte con la data del record: innocuo
per idempotenza). Resta: "Tomorrow at 9" (data inventata), "next day" senza mese.
Produzione: flash-lite su harness LEGACY finche' Alessandro non autorizza un giro di banco di flash-lite con v3.
