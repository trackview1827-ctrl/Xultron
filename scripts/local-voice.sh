#!/data/data/com.termux/files/usr/bin/env bash
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
STATE_DIR=${XULTRON_LOCAL_STT_DIR:-"$ROOT/backend/instance/local-voice"}
WHISPER_ROOT=${XULTRON_WHISPER_ROOT:-"$HOME/.local/src/whisper.cpp"}
BIN=${XULTRON_WHISPER_BIN:-"$WHISPER_ROOT/build/bin/whisper-server"}
MODEL=${XULTRON_WHISPER_MODEL:-"$WHISPER_ROOT/models/ggml-tiny.bin"}
PORT=${XULTRON_LOCAL_STT_PORT:-8766}
THREADS=${XULTRON_LOCAL_STT_THREADS:-2}
PIDFILE="$STATE_DIR/whisper.pid"
LOGFILE="$STATE_DIR/whisper.log"

mkdir -p "$STATE_DIR"

case "${1:-start}" in
  start)
    if [ -s "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      exit 0
    fi
    test -x "$BIN" || { printf 'whisper.cpp binary not found: %s\n' "$BIN" >&2; exit 1; }
    test -f "$MODEL" || { printf 'whisper.cpp model not found: %s\n' "$MODEL" >&2; exit 1; }
    nohup "$BIN" --host 127.0.0.1 --port "$PORT" --model "$MODEL" --threads "$THREADS" --processors 1 --max-context 0 --no-gpu --language auto --public "$WHISPER_ROOT/examples/server/public" >"$LOGFILE" 2>&1 </dev/null &
    printf '%s\n' "$!" > "$PIDFILE"
    ;;
  stop)
    if [ -s "$PIDFILE" ]; then
      kill "$(cat "$PIDFILE")" 2>/dev/null || true
      rm -f "$PIDFILE"
    fi
    ;;
  status)
    if [ -s "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      printf 'running\n'
    else
      printf 'stopped\n'
      exit 1
    fi
    ;;
  *)
    printf 'Usage: %s {start|stop|status}\n' "$0" >&2
    exit 2
    ;;
esac
