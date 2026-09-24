#!/usr/bin/env bash
# Drive transcribe_to_captions.py to completion.
#
# The worker exits 75 whenever it stops early (audio budget reached, or an MPS OOM
# left the pool unusable). Each restart gets a fresh MPS pool and resumes from the
# S3 skip-list plus any per-window checkpoint, so no audio is re-transcribed.
set -uo pipefail
cd "$(dirname "$0")/.."

LOG_DIR=/tmp/sermon-captions
mkdir -p "$LOG_DIR"
RUNLOG="$LOG_DIR/captions.log"

say() { echo "$(date '+%F %T') $*" | tee -a "$RUNLOG"; }

say "=== starting: $* ==="
pass=0
while true; do
    pass=$((pass + 1))
    venv/bin/python3 scripts/transcribe_to_captions.py "$@" >>"$RUNLOG" 2>&1
    rc=$?
    case $rc in
        0)  say "=== complete after $pass passes ==="; exit 0 ;;
        75) : ;;  # more work remains, restart with a fresh pool
        *)  say "=== worker exited $rc on pass $pass; retrying in 60s ==="; sleep 60 ;;
    esac
done
