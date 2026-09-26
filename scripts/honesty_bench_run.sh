#!/usr/bin/env bash
# Run coding agents headless over Honesty Bench workspaces and keep full transcripts.
#
# Usage:
#   scripts/honesty_bench_run.sh <workspaces-dir> <agent> [<agent> ...]
#
# <workspaces-dir> comes from `monte-neo bench prepare`. Each agent runs once per task, in a new
# session, with the task folder as its working directory and PROMPT.md as its only instruction.
# Output goes to transcript.log in the task folder; `monte-neo bench collect` copies it into the
# submission so the run can be audited.
#
# Commands for each agent are templates: CLI flags change between versions, so check
# `<cli> --help` before a public run and override with MN_CMD_<AGENT> (dashes become underscores),
# e.g. MN_CMD_claude_code='claude -p "$PROMPT" --permission-mode acceptEdits'.
# The prompt text is available to the command as $PROMPT.
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: $0 <workspaces-dir> <agent> [<agent> ...]" >&2
  exit 2
fi
WS="$1"
shift
TIMEOUT="${MN_TIMEOUT:-3600}"
# macOS has no `timeout`; Homebrew coreutils installs it as `gtimeout`.
if command -v timeout > /dev/null; then
  RUN_LIMITED=(timeout "$TIMEOUT")
elif command -v gtimeout > /dev/null; then
  RUN_LIMITED=(gtimeout "$TIMEOUT")
else
  echo "warning: no timeout/gtimeout found; agents run without a time limit (brew install coreutils)" >&2
  RUN_LIMITED=()
fi

default_cmd() {
  case "$1" in
    claude-code) echo 'claude -p "$PROMPT" --permission-mode acceptEdits' ;;
    codex)       echo 'codex exec --full-auto "$PROMPT"' ;;
    gemini-cli)  echo 'gemini -p "$PROMPT" --yolo' ;;
    cursor)      echo 'cursor-agent -p "$PROMPT" --force' ;;
    *)           echo "" ;;
  esac
}

for agent in "$@"; do
  var="MN_CMD_${agent//-/_}"
  cmd="${!var:-$(default_cmd "$agent")}"
  if [ -z "$cmd" ]; then
    echo "no command for agent '$agent': set $var" >&2
    exit 2
  fi
  for task_dir in "$WS/$agent"/task-*; do
    [ -d "$task_dir" ] || continue
    if [ -f "$task_dir/strategy.py" ]; then
      echo "skip $task_dir (strategy.py exists; keep the first final answer)"
      continue
    fi
    echo "run  $agent in $task_dir"
    (
      cd "$task_dir"
      PROMPT="$(cat PROMPT.md)"
      export PROMPT
      {
        echo "# agent: $agent"
        echo "# started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "# command: $cmd"
        echo
      } > transcript.log
      set +e
      ${RUN_LIMITED[@]+"${RUN_LIMITED[@]}"} bash -c "$cmd" >> transcript.log 2>&1
      echo "# exit: $?" >> transcript.log
      echo "# finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> transcript.log
    )
  done
done
echo "done. Next: monte-neo bench collect <bench-dir> --workspaces $WS"
