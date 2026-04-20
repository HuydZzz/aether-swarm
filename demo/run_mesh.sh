#!/usr/bin/env bash
# Spawn an 8-agent heterogeneous AETHER mesh.
#
# Prereqs:
#   - FoxMQ broker reachable (default 127.0.0.1:1883)
#   - VERTEX_USER and VERTEX_PASS exported
#
# Usage:
#   export VERTEX_USER=demo
#   export VERTEX_PASS=demo
#   ./demo/run_mesh.sh
#
# Logs go to logs/<agent-id>.log. Use `tail -f logs/*.log` to watch them all,
# or run `python -m demo.dashboard` in another terminal for the live view.

set -euo pipefail

cd "$(dirname "$0")/.."

if [ -z "${VERTEX_USER:-}" ]; then
  echo "ERROR: VERTEX_USER must be set." >&2
  exit 2
fi

mkdir -p logs
PIDS=()
trap 'echo "stopping mesh..."; for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done' EXIT INT TERM

spawn() {
  local id=$1; shift
  python3 -m src.aether_agent --agent-id "$id" "$@" >"logs/${id}.log" 2>&1 &
  PIDS+=($!)
  echo "  spawned $id (pid $!)"
  sleep 0.2
}

echo "AETHER mesh starting — 8 agents heterogeneous"
spawn coord-01    --role coordinator --x   0 --y   0 --seed-tasks 6
spawn drone-01    --role drone        --x   3 --y   3
spawn drone-02    --role drone        --x  -4 --y   2
spawn drone-03    --role drone        --x   5 --y  -3
spawn amr-01      --role amr          --x   0 --y   5
spawn amr-02      --role amr          --x  -3 --y  -3
spawn iot-01      --role iot_sensor   --x  10 --y   0
spawn iot-02      --role iot_sensor   --x  -8 --y   8

echo
echo "mesh up. open another terminal and run:"
echo "  VERTEX_USER=$VERTEX_USER VERTEX_PASS=\$VERTEX_PASS python3 -m demo.dashboard"
echo
echo "trigger chaos with:"
echo "  python3 -m demo.chaos kill drone-01"
echo "  python3 -m demo.chaos fault iot-01 power_loss"
echo "  python3 -m demo.chaos byzantine-on amr-02"
echo
echo "Ctrl-C to stop the mesh."

wait
