#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".vendor-312" ]; then
  echo "Missing .vendor-312. Install dependencies with:"
  echo "/opt/homebrew/Cellar/python@3.12/3.12.12/bin/python3.12 -m pip install --target .vendor-312 -r requirements.txt"
  exit 1
fi

export PYTHONPATH=".vendor-312${PYTHONPATH:+:$PYTHONPATH}"
exec /opt/homebrew/Cellar/python@3.12/3.12.12/bin/python3.12 checkers_advisor_tk.py
