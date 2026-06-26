#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../frontend"
pnpm install
pnpm dev
