#!/usr/bin/env bash
# Profilo dell'orecchio laterale (ramo HUD), scelto dalla UI o dal launcher:
#   turbo : Whisper large-v3-turbo (~1,6 GB) + estrattore cloud SENZA fallback locale (libera i 3,5 GB di Qwen3-1.7B)
#   small : Whisper small (~1 GB) + estrattore cloud CON fallback locale Qwen3-1.7B
# Uso: bash tools/switch_asr_profile.sh turbo|small   (riavvia solo ASR e tool agent; backend, worker e gateway restano)
set -u
PROFILE="${1:-turbo}"
cd "$(dirname "$0")/.."
LOGS=logs_demo; mkdir -p "$LOGS"
PY=/home/alex/miniconda3/envs/minicpm/bin/python
PYASR=/home/alex/miniconda3/envs/cosyvoice2/bin/python
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
echo "profilo $PROFILE: asr $(curl -s http://127.0.0.1:22710/health) · tool agent $(curl -s http://127.0.0.1:22700/health)"
