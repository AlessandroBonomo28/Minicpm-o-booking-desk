#!/usr/bin/env bash
# Demo HUD (ramo sperimentale, 03/09): CODICE del ramo italiano (fix decodifica +
# pagina /static/hud/hud.html) con i pesi BASE (nessun --pt-path): v1.3 con i token
# video degenera (calendario, via 5). Uso: bash tools/run_demo_hud.sh
set -uo pipefail
PY=/home/alex/miniconda3/envs/minicpm/bin/python
ROOT=/home/alex/progetti/MiniCPM-o-Demo
LOGS=$ROOT/logs_demo
PT=""  # HUD: pesi BASE (v1.3 con i frame degenera, vedi calendario via 5)
cd "$ROOT"; mkdir -p "$LOGS"

pkill -f "py_backend.server" 2>/dev/null
pkill -f "worker.py --host" 2>/dev/null
pkill -f "gateway.py --host" 2>/dev/null
pkill -f "cascade_tts_server" 2>/dev/null
sleep 3

echo "=== backend BASE + codice ramo italiano, pagina HUD (carica ~4 min) — $(date '+%H:%M')"
setsid "$PY" -m py_backend.server \
    --host 0.0.0.0 --port 22500 --gpu-id 0 \
    --model-path ./modelli/MiniCPM-o-4_5 \
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
    --backend-server-url http://127.0.0.1:22500 \
    > "$LOGS/worker.log" 2>&1 < /dev/null &
sleep 4
setsid "$PY" gateway.py --host 0.0.0.0 --port 8006 --internal-port 8007 --https \
    --ssl-certfile certs/cert.pem --ssl-keyfile certs/key.pem \
    > "$LOGS/gateway.log" 2>&1 < /dev/null &
sleep 6
curl -s -X PUT -H "content-type: application/json" \
    --data '{"endpoint":"127.0.0.1:22400","gpu_group":"gpu-0"}' \
    http://127.0.0.1:8007/internal/workers/worker-0 >/dev/null

echo "--- verifiche — $(date '+%H:%M')"
curl -sf http://127.0.0.1:22400/health >/dev/null && echo "worker: OK" || echo "worker: KO"
curl -skf https://127.0.0.1:8006/ >/dev/null && echo "gateway: OK" || echo "gateway: KO"
grep -iE "weights loaded|missing|unexpected" "$LOGS/backend.log" | tail -3
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader
free -g | head -2
echo "DEMO HUD SU — https://localhost:8006/static/hud/hud.html — $(date '+%H:%M')"
