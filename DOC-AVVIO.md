# DOC-AVVIO — come avviare la demo a mano e passare tra i due "rami"

Aggiornato: 02/09/2026. Tutto quello che c'è qui **vive in git, non in Claude**: se Claude
sparisce, questi comandi funzionano uguale.

---

## 1. Cosa sono i due "rami" (in realtà: due cartelle della stessa repository)

Non sono due fork e non sono due repository. È **una sola repository git** con **due
cartelle di lavoro** (git *worktree*) agganciate allo stesso `.git`:

| Cartella | Commit/branch | Cosa contiene | Modello che usa |
|---|---|---|---|
| `/home/alex/progetti/MiniCPM-o-Demo` | branch `main` (il nostro lavoro) | codice upstream **+ i nostri fix di decodifica** (penalità anti-ripetizione col segno giusto e a 1.15, token di ascolto corretto, taglio a confine di parola) + preset italiani + script | **v1.3** (`training/releases/v1_3_voce_intera/it11_b12_merged.pt`) |
| `/home/alex/progetti/MiniCPM-o-Demo-upstream-puro` | commit `50b0865` (l'upstream OpenBMB da cui siamo partiti) | codice **puro**, zero modifiche; in più solo i preset italiani (file non tracciati) e il link a `modelli/` | **base** (nessun pt: il MiniCPM-o 4.5 originale) |

Perché due cartelle: i nostri fix di decodifica cambiano il campionamento per *qualunque*
peso; per avere "l'originale vero" servono pesi base **e** codice puro. Con due cartelle si
passa dall'uno all'altro senza revert.

Comandi git utili (da `/home/alex/progetti/MiniCPM-o-Demo`):

```bash
git worktree list          # mostra le due cartelle e a che commit stanno
git log --oneline -15      # la storia del nostro lavoro (main)
git branch                 # i branch (c'è anche fix-decodifica-italiani, un salvataggio dei fix)
```

Per ricreare la cartella "puro" se venisse cancellata:

```bash
cd /home/alex/progetti/MiniCPM-o-Demo
git worktree add ../MiniCPM-o-Demo-upstream-puro 50b0865
cp assets/presets/audio_duplex/italiano*.yaml ../MiniCPM-o-Demo-upstream-puro/assets/presets/audio_duplex/
mkdir -p ../MiniCPM-o-Demo-upstream-puro/assets/presets/omni ../MiniCPM-o-Demo-upstream-puro/assets/ref_audio
cp assets/presets/omni/italiano*.yaml ../MiniCPM-o-Demo-upstream-puro/assets/presets/omni/
cp assets/ref_audio/ref_it_test1.wav ../MiniCPM-o-Demo-upstream-puro/assets/ref_audio/
ln -sfn /home/alex/progetti/MiniCPM-o-Demo/modelli ../MiniCPM-o-Demo-upstream-puro/modelli
```

Per eliminarla (non tocca nulla del ramo principale):

```bash
git worktree remove ../MiniCPM-o-Demo-upstream-puro
```

---

## 2. Avvio con gli script (il modo normale)

Sempre da `/home/alex/progetti/MiniCPM-o-Demo`. Ogni script **spegne da solo** l'altro
stack (stessa GPU, stesse porte), quindi per "switchare" basta lanciare l'altro script.

### Ramo italiano (nostri fix + pesi v1.3)

```bash
bash tools/run_demo_v13.sh
```

### Ramo originale (codice puro + modello base)

```bash
bash tools/run_demo_base.sh
```


### Ramo HUD (sperimentale: frame come segnale + tool calling con modello separato)

```bash
bash tools/run_demo_hud.sh
```
→ codice del ramo italiano + **pesi BASE** + tool agent Qwen3-1.7B (porta 22700). Pagina: `https://localhost:8006/static/hud/hud.html`. Doc: `plan/ramo-hud.md`.

Tempi: 1-4 minuti (il caricamento dei pesi dipende dalla cache del disco). Lo script
stampa le verifiche alla fine (`worker: OK`, `gateway: OK`, `DEMO ... SU`).
Log in `logs_demo/` (`backend.log`, `worker.log`, `gateway.log`, `launch.log`).

Per non perdere lo stack se chiudi il terminale, lancialo così:

```bash
setsid bash tools/run_demo_v13.sh > logs_demo/launch.log 2>&1 < /dev/null & disown
tail -f logs_demo/launch.log      # per seguire l'avvio (Ctrl+C esce dal tail, non dallo stack)
```

Poi apri **https://localhost:8006** (certificato self-signed: accetta l'avviso del browser).

- `https://localhost:8006/audio_duplex` → **Audio Full-Duplex** (solo audio; il contesto su cui abbiamo addestrato)
- `https://localhost:8006/omni` → **Omni Full-Duplex** (audio + webcam)

Preset disponibili nel pannello: `Chiamata in italiano` (prompt lungo, quello del training v1.3,
penalità 1.05), `Italiano (prompt nativo)` (`Streaming Omni Conversation. Parla sempre in italiano.`,
penalità 1.0), `English Call`, `中文通话`.

---

## 3. Avvio manuale, comando per comando (se vuoi capire cosa fa lo script)

Sono 3 processi + 1 registrazione. `PY` è l'ambiente conda `minicpm`.

```bash
PY=/home/alex/miniconda3/envs/minicpm/bin/python
cd /home/alex/progetti/MiniCPM-o-Demo            # oppure: cd /home/alex/progetti/MiniCPM-o-Demo-upstream-puro
```

**1) Backend** (carica il modello sulla GPU; è il processo lento):

```bash
# ramo italiano: con i pesi v1.3
$PY -m py_backend.server --host 0.0.0.0 --port 22500 --gpu-id 0 \
    --model-path ./modelli/MiniCPM-o-4_5 \
    --pt-path training/releases/v1_3_voce_intera/it11_b12_merged.pt

# ramo originale (dalla cartella upstream-puro): SENZA --pt-path
$PY -m py_backend.server --host 0.0.0.0 --port 22500 --gpu-id 0 \
    --model-path /home/alex/progetti/MiniCPM-o-Demo/modelli/MiniCPM-o-4_5
```

Aspetta che risponda: `curl -sf http://127.0.0.1:22500/health && echo pronto`.

**2) Worker** (fa da ponte tra gateway e backend):

```bash
$PY worker.py --host 0.0.0.0 --port 22400 --gpu-id 0 --backend-server-url http://127.0.0.1:22500
```

**3) Gateway** (il sito web, HTTPS):

```bash
$PY gateway.py --host 0.0.0.0 --port 8006 --internal-port 8007 --https \
    --ssl-certfile /home/alex/progetti/MiniCPM-o-Demo/certs/cert.pem \
    --ssl-keyfile  /home/alex/progetti/MiniCPM-o-Demo/certs/key.pem
```

**4) Registrazione del worker nel gateway** (senza questa il sito dice "no worker"):

```bash
curl -s -X PUT -H "content-type: application/json" \
    --data '{"endpoint":"127.0.0.1:22400","gpu_group":"gpu-0"}' \
    http://127.0.0.1:8007/internal/workers/worker-0
```

Ogni processo va lanciato in un terminale suo (o con `setsid ... & disown` come sopra).

---

## 4. Switch tra i rami

- **Con gli script**: lancia l'altro script, fine (spegne il precedente).
- **A mano**: ferma i tre processi, poi rilancia dalla *cartella dell'altro ramo*:

```bash
pkill -f py_backend.server; pkill -f "worker.py --host"; pkill -f "gateway.py --host"
```

Attenzione: **non** puoi tenere i due rami accesi insieme (un modello occupa ~23 GB su 32).

Per capire quale ramo sta girando:

```bash
pgrep -a -f py_backend.server | grep -o "pt-path [^ ]*" || echo "nessun --pt-path: sta girando il BASE"
grep "Weights loaded" logs_demo/backend.log | tail -1     # v1.3: 'missing: 1015, unexpected: 0'; base: riga assente
```

---

## 5. Controlli rapidi e problemi noti

```bash
curl -sf http://127.0.0.1:22500/health && echo backend:OK
curl -sf http://127.0.0.1:22400/health && echo worker:OK
curl -skf https://127.0.0.1:8006/ >/dev/null && echo gateway:OK
curl -sk https://127.0.0.1:8006/workers | grep -o '"status":"[a-z_]*"'   # idle = libero, duplex_active = sessione in corso
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader
```

- **"WebSocket connection failed"** nel browser → il gateway non è su, o il backend sta ancora caricando: guarda `logs_demo/launch.log`.
- **"si stacca Ubuntu" / WSL riavviato** → tutto muore (i processi non sopravvivono a un riavvio di WSL): rilancia lo script. I fix di caricamento a bassa RAM sono nel ramo italiano; nel ramo puro il caricamento è quello originale (picco RAM alto: non lanciare altro pesante insieme).
- **Il preset nuovo non compare** → i preset si caricano all'avvio del gateway: riavvia solo il gateway (passo 3 + 4).
- **Non si fa interrompere / sbrodola** → prima di tutto: cuffie (l'eco dagli altoparlanti rientra nel mic), poi `Length Penalty` a 1.0-1.05 (più alto = turni più lunghi e interruzione più difficile, lo dice anche la FAQ upstream), e microfono di Windows senza "miglioramenti audio".
- **Registrazioni delle sessioni** (audio + eventi, utili per capire cosa è successo): `data/sessions/<id>/` nella cartella del ramo che stava girando.
