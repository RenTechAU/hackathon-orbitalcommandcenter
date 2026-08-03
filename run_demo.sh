#!/usr/bin/env bash
#
# One command to run the demo. Handles the boring setup for you:
#   - makes sure Docker is up
#   - makes sure FalkorDB (the memory database) is running
#   - runs the app with the right Python (the .venv one that has falkordb)
#
# Usage:  ./run_demo.sh
#
set -e
cd "$(dirname "$0")"

echo "==> checking Docker is running..."
if ! docker info >/dev/null 2>&1; then
  echo "    Docker isn't up. Launching Docker Desktop (wait ~30s, then re-run)..."
  open -a Docker || true
  exit 1
fi

echo "==> making sure FalkorDB is running..."
if ! docker ps --filter name=falkordb --format '{{.Names}}' | grep -q falkordb; then
  docker rm -f falkordb >/dev/null 2>&1 || true
  docker run -d --name falkordb -p 6379:6379 falkordb/falkordb >/dev/null
  sleep 4
  echo "    started FalkorDB"
else
  echo "    already running"
fi

echo "==> running the demo..."
echo
.venv/bin/python src/main.py
