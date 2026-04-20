#!/bin/bash
#
# Delphi-AHP Pipeline Runner (macOS / Linux)
# Double-click this file or run: bash run.sh
#
cd "$(dirname "$0")"
source .venv/bin/activate
python3 app.py
