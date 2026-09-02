#!/usr/bin/env bash
# Demo ORIGINALE (02/09): modello BASE (nessun --pt-path) + CODICE UPSTREAM PURO
# (worktree git al commit 50b0865, senza i nostri fix di decodifica). E' la demo
# esattamente come esce dal repo OpenBMB; in piu' c'e' solo il preset italiano
# (prompt+voce) come opzione nella UI. Delay riproduzione: default upstream 200ms
# (600 va messo a mano nel pannello).
# Uso: bash tools/run_demo_base.sh      (l'altro mondo: bash tools/run_demo_v13.sh)
set -uo pipefail
PY=/home/alex/miniconda3/envs/minicpm/bin/python
MAIN=/home/alex/progetti/MiniCPM-o-Demo
W=/home/alex/progetti/MiniCPM-o-Demo-upstream-puro
LOGS=$MAIN/logs_demo
cd "$W"; mkdir -p "$LOGS"

pkill -f "py_backend.server" 2>/dev/null
pkill -f "worker.py --host" 2>/dev/null
pkill -f "gateway.py --host" 2>/dev/null
sleep 3

echo "=== backend BASE, codice upstream puro (carica ~4 min) — $(date '+%H:%M')"
setsid "$PY" -m py_backend.server --host 0.0.0.0 --port 22500 --gpu-id 0 \
    --model-path "$MAIN/modelli/MiniCPM-o-4_5" \
    > "$LOGS/backend.log" 2>&1 < /dev/null &
BACKPID=$!
for i in $(seq 1 90); do
  curl -sf http://127.0.0.1:22500/health >/dev/null 2>&1 && break
  kill -0 "$BACKPID" 2>/dev/null || { echo "BACKEND MORTO"; tail -15 "$LOGS/backend.log"; exit 1; }
  sleep 5
done
curl -sf http://127.0.0.1:22500/health >/dev/null || { echo "BACKEND NON RISPONDE"; exit 1; }

echo "=== worker + gateway — $(date '+%H:%M')"
setsid "$PY" worker.py --host 0.0.0.0 --port 22400 --gpu-id 0 \
    --backend-server-url http://127.0.0.1:22500 > "$LOGS/worker.log" 2>&1 < /dev/null &
sleep 4
setsid "$PY" gateway.py --host 0.0.0.0 --port 8006 --internal-port 8007 --https \
    --ssl-certfile "$MAIN/certs/cert.pem" --ssl-keyfile "$MAIN/certs/key.pem" \
    > "$LOGS/gateway.log" 2>&1 < /dev/null &
sleep 6
curl -s -X PUT -H "content-type: application/json" \
    --data '{"endpoint":"127.0.0.1:22400","gpu_group":"gpu-0"}' \
    http://127.0.0.1:8007/internal/workers/worker-0 >/dev/null

echo "--- verifiche — $(date '+%H:%M')"
curl -sf http://127.0.0.1:22400/health >/dev/null && echo "worker: OK" || echo "worker: KO"
curl -skf https://127.0.0.1:8006/ >/dev/null && echo "gateway: OK" || echo "gateway: KO"
grep -c "Loading extra weights" "$LOGS/backend.log" | sed 's/^/pt caricati (deve essere 0): /'
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader
echo "DEMO BASE (upstream puro) SU — https://localhost:8006/audio_duplex — $(date '+%H:%M')"
