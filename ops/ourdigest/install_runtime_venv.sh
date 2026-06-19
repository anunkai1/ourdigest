#!/usr/bin/env bash
# Create venv and install ourdigest in editable mode with dev extras.
set -euo pipefail

cd "$(dirname "$0")/../.."

PY="${PYTHON:-python3}"
$PY -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"

echo
echo "ourdigest installed at $(pwd)/.venv"
echo "Next steps:"
echo "  cp config.example.yaml config.yaml"
echo "  cp .env.example .env  &&  edit .env with OPENAI_BASE_URL + OPENAI_API_KEY"
echo "  export OURDIGEST_CONFIG=$(pwd)/config.yaml"
echo "  .venv/bin/ourdigest fetch    # one-shot refresh"
echo "  .venv/bin/ourdigest serve    # start the HTTP server"
