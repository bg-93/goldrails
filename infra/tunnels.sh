#!/usr/bin/env bash
# Open one IAP tunnel per served model, resolved from the VM's metadata. Usage: infra/tunnels.sh [up|down|status]
# Each tunnel retries until its model server is listening, so `up` can run before the models finish loading.
set -euo pipefail
cd "$(dirname "$0")/.."
PIDFILE=/tmp/gold-rails-tunnels.pids
ports() { lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | awk '/127.0.0.1:(80[0-9][0-9]|8791)/{sub(".*:","",$9); print $9}' | sort -u | tr '\n' ' '; }
case "${1:-up}" in
  up)
    : > "$PIDFILE"
    uv run python -c "from goldrails_bench.endpoints import tunnel_commands; print('\n'.join(tunnel_commands()))" | while read -r cmd; do
      nohup bash -c "until $cmd >/dev/null 2>&1; do sleep 15; done" >/dev/null 2>&1 & echo $! >> "$PIDFILE"; echo "tunnel: $cmd"
    done
    sleep 8; echo "listening locally on: $(ports)(others retry every 15s until their server is up)" ;;
  down)
    if [ -f "$PIDFILE" ]; then while read -r p; do pkill -P "$p" 2>/dev/null || true; kill "$p" 2>/dev/null || true; done < "$PIDFILE"; rm -f "$PIDFILE"; fi
    pkill -f "start-iap-tunnel gold-rails-serve" 2>/dev/null || true; echo "tunnels down" ;;
  status) echo "listening locally on: $(ports)" ;;
esac
