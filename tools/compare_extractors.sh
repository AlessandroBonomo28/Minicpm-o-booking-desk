#!/usr/bin/env bash
# Ramo phonellm (06/09): stesso banco di prova per estrattori diversi. Riavvia l'estrattore sul backend/modello dato,
# esegue le due regressioni via gateway e salva il rapporto in logs_demo/extractor_eval/<etichetta>.txt
#   tools/compare_extractors.sh <etichetta> <backend: cline|openai> <modello> [altri argomenti del server, es. --no-think]
# Alla fine NON ripristina il backend: rilanciare tools/switch_asr_profile.sh turbo (o questo script con flash-lite).
set -u
cd "$(dirname "$0")/.."
LABEL="$1"; BACKEND="$2"; MODEL="$3"; shift 3
PY=/home/alex/miniconda3/envs/minicpm/bin/python
OUT=logs_demo/extractor_eval; mkdir -p "$OUT"
kill $(pgrep -f "^[^ ]*python tools/tool_agent_server.py") 2>/dev/null; sleep 1
setsid "$PY" tools/tool_agent_server.py --backend "$BACKEND" --cloud-model "$MODEL" --no-local "$@" > logs_demo/tool_agent.log 2>&1 < /dev/null &
for i in $(seq 1 60); do curl -sf http://127.0.0.1:22700/health >/dev/null 2>&1 && break; sleep 1; done
{
  echo "== $LABEL · backend $BACKEND · modello $MODEL · argomenti: $* · $(date '+%Y-%m-%d %H:%M')"
  head -3 logs_demo/tool_agent.log
  echo; echo "### regressione base (tools/tool_agent_eval.py)"; "$PY" tools/tool_agent_eval.py 2>&1
  echo; echo "### regressione dialogo (tools/tool_agent_eval_dialog.py)"; "$PY" tools/tool_agent_eval_dialog.py 2>&1
  echo; echo "### errori del provider"; grep -c "cloud non disponibile" logs_demo/tool_agent.log
} | tee "$OUT/$LABEL.txt"
