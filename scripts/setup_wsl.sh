#!/usr/bin/env bash
# Set up eqasim-france v1.5.0 inside WSL (Ubuntu). Run from the pilot folder:
#   bash scripts/setup_wsl.sh
# Population synthesis only: no Java, no MATSim.
set -euo pipefail

PILOT="$(cd "$(dirname "$0")/.." && pwd)"     # the project folder
CODE="$HOME/eqasim-france"                     # kept on the Linux side: much faster than /mnt/c

mkdir -p "$PILOT/data" "$PILOT/output" "$HOME/eqasim-cache"

if [ ! -d "$CODE" ]; then
  git clone --branch v1.5.0 --depth 1 https://github.com/eqasim-org/eqasim-france "$CODE"
fi

if ! command -v uv >/dev/null; then
  echo "uv is not installed. Install it first: https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
fi

cd "$CODE" && uv sync
uv run python "$PILOT/configs/make_configs.py" "$PILOT" 0.1

echo
echo "Ready. Smoke test (0.1% sample) once the data folder is filled:"
echo "  cd $CODE && uv run -m synpp $PILOT/configs/A_entd_local.yml"
