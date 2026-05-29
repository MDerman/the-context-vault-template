#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INVOICE_NUMBER="${1:-1}"

python3 "${SCRIPT_DIR}/generate_invoice.py" \
  --mode openclaw \
  --invoice-number "${INVOICE_NUMBER}" \
  --client you \
  --item "5x Mac Mini + apple tax" 10000
