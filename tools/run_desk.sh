#!/usr/bin/env bash
# Booking desk launcher: speech backend (MiniCPM-o 4.5) + side ASR + extractor/judge service + worker + gateway.
# Idempotent: stops a previous instance first. The backend takes ~4 minutes to load.
#
#   bash tools/run_desk.sh
#
# Environment (all optional):
#   PY              python with the demo requirements (default: python on PATH, e.g. the activated conda env)
#   ASR_PYTHON      python with openai-whisper for the side ASR (default: $PY)
#   MODEL_PATH      MiniCPM-o 4.5 weights (default: models/MiniCPM-o-4_5, from openbmb/MiniCPM-o-4_5 on Hugging Face)
#   GPU_ID          CUDA device (default: 0)
#   HUD_ASR         side-ASR profile: turbo = Whisper large-v3-turbo + cloud extractor only (default)
#                                     small = Whisper small + local Qwen3-1.7B fallback (needs models/Qwen3-1.7B)
#   TOOL_AGENT_ENV  file with TA_API_KEY / TA_BASE_URL / TA_MODEL for the extractor and the judge
#                   (default: ~/.config/tool_agent.env; a .env in the repository root is read too)
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PY="${PY:-python}"
export ASR_PYTHON="${ASR_PYTHON:-$PY}"
MODEL_PATH="${MODEL_PATH:-models/MiniCPM-o-4_5}"
GPU_ID="${GPU_ID:-0}"
LOGS="$ROOT/logs_demo"; mkdir -p "$LOGS"
for f in "${TOOL_AGENT_ENV:-$HOME/.config/tool_agent.env}" "$ROOT/.env"; do
  if [ -f "$f" ]; then set -a; . "$f"; set +a; fi
done
[ -d "$MODEL_PATH" ] || { echo "MODEL_PATH not found: $MODEL_PATH (download openbmb/MiniCPM-o-4_5 from Hugging Face)"; exit 1; }
[ -n "${TA_API_KEY:-}${TA_OPENAI_API_KEY:-}" ] || echo "warning: no TA_API_KEY in the environment: the extractor and the judge will not start (see README, Running it)"

pkill -f "py_backend.server" 2>/dev/null
pkill -f "worker.py --host" 2>/dev/null
pkill -f "gateway.py --host" 2>/dev/null
pkill -f "tool_agent_server" 2>/dev/null
pkill -f "asr_server.py" 2>/dev/null
sleep 3

echo "=== speech backend: MiniCPM-o 4.5 from $MODEL_PATH (loads in ~4 min) — $(date '+%H:%M')"
setsid "$PY" -m py_backend.server \
    --host 0.0.0.0 --port 22500 --gpu-id "$GPU_ID" \
    --model-path "$MODEL_PATH" \
    > "$LOGS/backend.log" 2>&1 < /dev/null &
BACKPID=$!
for i in $(seq 1 90); do
  curl -sf http://127.0.0.1:22500/health >/dev/null 2>&1 && break
  kill -0 "$BACKPID" 2>/dev/null || { echo "BACKEND DIED"; tail -15 "$LOGS/backend.log"; exit 1; }
  sleep 5
done
curl -sf http://127.0.0.1:22500/health >/dev/null || { echo "BACKEND NOT RESPONDING"; exit 1; }

echo "=== side ASR + extractor/judge service (profile ${HUD_ASR:-turbo}) — $(date '+%H:%M')"
bash tools/switch_asr_profile.sh "${HUD_ASR:-turbo}" > "$LOGS/asr_profile.log" 2>&1

echo "=== worker + gateway — $(date '+%H:%M')"
setsid "$PY" worker.py --host 0.0.0.0 --port 22400 --gpu-id "$GPU_ID" \
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

for i in $(seq 1 40); do curl -sf http://127.0.0.1:22700/health >/dev/null 2>&1 && break; sleep 3; done
echo "--- checks — $(date '+%H:%M')"
curl -sf http://127.0.0.1:22710/health >/dev/null && echo "side ASR: OK" || { echo "side ASR: KO"; tail -3 "$LOGS/asr_server.log"; }
curl -sf http://127.0.0.1:22700/health >/dev/null && echo "extractor/judge: OK" || { echo "extractor/judge: KO"; tail -3 "$LOGS/tool_agent.log"; }
curl -sf http://127.0.0.1:22400/health >/dev/null && echo "worker: OK" || echo "worker: KO"
curl -skf https://127.0.0.1:8006/ >/dev/null && echo "gateway: OK" || echo "gateway: KO"
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader 2>/dev/null
echo "BOOKING DESK UP — https://localhost:8006/static/hud/hud.html  (bookings: https://localhost:8006/static/hud/db.html) — $(date '+%H:%M')"
