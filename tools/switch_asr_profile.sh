#!/usr/bin/env bash
# Side-ASR profile, chosen from the UI or by the launcher:
#   turbo : Whisper large-v3-turbo (~1.6 GB) + cloud extractor WITHOUT local fallback (frees the 3.5 GB of Qwen3-1.7B)
#   small : Whisper small (~1 GB) + cloud extractor WITH the local Qwen3-1.7B fallback
# Usage: bash tools/switch_asr_profile.sh turbo|small   (restarts only the ASR and the extractor; backend, worker and gateway stay up)
# Environment: PY (python with the demo requirements, default: python), ASR_PYTHON (python with openai-whisper, default: $PY),
#              TA_API_KEY / TA_BASE_URL / TA_MODEL for the cloud extractor (see tools/tool_agent_server.py)
set -u
PROFILE="${1:-turbo}"
cd "$(dirname "$0")/.."
LOGS=logs_demo; mkdir -p "$LOGS"
PY="${PY:-python}"
PYASR="${ASR_PYTHON:-$PY}"
echo "$PROFILE" > "$LOGS/asr_profile"
pkill -f "^[^ ]*python tools/asr_server.py" 2>/dev/null
pkill -f "^[^ ]*python tools/tool_agent_server.py" 2>/dev/null
sleep 2
if [ "$PROFILE" = "turbo" ]; then
  setsid "$PYASR" tools/asr_server.py --port 22710 --model large-v3-turbo --device cuda > "$LOGS/asr_server.log" 2>&1 < /dev/null &
  setsid "$PY" tools/tool_agent_server.py --port 22700 --backend cline --no-local > "$LOGS/tool_agent.log" 2>&1 < /dev/null &
else
  setsid "$PYASR" tools/asr_server.py --port 22710 --model small --device cuda > "$LOGS/asr_server.log" 2>&1 < /dev/null &
  setsid "$PY" tools/tool_agent_server.py --port 22700 --backend cline > "$LOGS/tool_agent.log" 2>&1 < /dev/null &
fi
for i in $(seq 1 90); do curl -sf http://127.0.0.1:22710/health >/dev/null 2>&1 && curl -sf http://127.0.0.1:22700/health >/dev/null 2>&1 && break; sleep 2; done
echo "profile $PROFILE: asr $(curl -s http://127.0.0.1:22710/health) · tool agent $(curl -s http://127.0.0.1:22700/health)"
