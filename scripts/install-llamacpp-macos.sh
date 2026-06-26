#!/usr/bin/env bash
set -euo pipefail

if command -v llama-server >/dev/null 2>&1; then
  echo "llama-server already installed: $(command -v llama-server)"
  exit 0
fi

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required to install llama.cpp on this Mac." >&2
  exit 1
fi

brew install llama.cpp
command -v llama-server
