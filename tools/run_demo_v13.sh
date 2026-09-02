#!/usr/bin/env bash
# Demo DEFAULT (02/09): backend v1.3 it11_b12_merged.pt (validato dal vivo, TTS
# interno) + server XTTS opzionale avviato DOPO il backend (mai in concorrenza:
# il picco RAM del boot va rispettato). A spunta "XTTS (ita)" spenta (default)
# la sessione e' identica alla v1.3 di sempre; accesa, la voce esce da XTTS.
# Uso: bash tools/run_demo_v13.sh
set -uo pipefail
PY=/home/alex/miniconda3/envs/minicpm/bin/python
PYX=/home/alex/miniconda3/envs/xtts/bin/python
ROOT=/home/alex/progetti/MiniCPM-o-Demo
LOGS=$ROOT/logs_demo
PT=$ROOT/training/releases/v1_3_voce_intera/it11_b12_merged.pt
cd "$ROOT"; mkdir -p "$LOGS"

pkill -f "py_backend.server" 2>/dev/null
pkill -f "worker.py --host" 2>/dev/null
pkill -f "gateway.py --host" 2>/dev/null
pkill -f "cascade_tts_server" 2>/dev/null
sleep 3

echo "=== backend v1.3 (carica ~4 min) — $(date '+%H:%M')"
setsid "$PY" -m py_backend.server \
    --host 0.0.0.0 --port 22500 --gpu-id 0 \
    --model-path ./modelli/MiniCPM-o-4_5 --pt-path "$PT" \
    > "$LOGS/backend.log" 2>&1 < /dev/null &
for i in $(seq 1 90); do
  curl -sf http://127.0.0.1:22500/health >/dev/null 2>&1 && break
  pgrep -f "py_backend.server" >/dev/null || { echo "BACKEND MORTO"; tail -15 "$LOGS/backend.log"; exit 1; }
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

echo "=== XTTS server (dopo il backend, per il picco RAM) — $(date '+%H:%M')"
setsid "$PYX" tools/cascade_tts_server.py --port 22600 --engine xtts \
    > "$LOGS/xtts_server.log" 2>&1 < /dev/null &
for i in $(seq 1 40); do
  curl -sf http://127.0.0.1:22600/health >/dev/null 2>&1 && break; sleep 5
done

echo "--- verifiche — $(date '+%H:%M')"
curl -sf http://127.0.0.1:22600/health >/dev/null && echo "xtts: OK" || { echo "xtts: KO"; tail -5 "$LOGS/xtts_server.log"; }
curl -sf http://127.0.0.1:22400/health >/dev/null && echo "worker: OK" || echo "worker: KO"
curl -skf https://127.0.0.1:8006/ >/dev/null && echo "gateway: OK" || echo "gateway: KO"
grep -iE "weights loaded|missing|unexpected" "$LOGS/backend.log" | tail -3
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader
free -g | head -2
echo "DEMO V13 SU — https://localhost:8006/audio_duplex — $(date '+%H:%M')"
