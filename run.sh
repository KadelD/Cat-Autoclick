#!/usr/bin/env bash
# Launch Cat Autoclick from a local virtualenv.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -x .venv/bin/python && ! -x .venv/Scripts/python.exe ]]; then
  echo "Creating virtualenv..."
  python3 -m venv .venv
  if [[ -x .venv/Scripts/python.exe ]]; then
    .venv/Scripts/python.exe -m pip install -r requirements.txt
  else
    .venv/bin/python -m pip install -r requirements.txt
  fi
fi

if [[ -x .venv/Scripts/python.exe ]]; then
  exec .venv/Scripts/python.exe main.py "$@"
fi
exec .venv/bin/python main.py "$@"
