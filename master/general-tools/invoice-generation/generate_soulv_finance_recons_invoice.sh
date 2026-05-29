#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INVOICE_NUMBER="2026_04_Soulv_Invoice_15"

python3 "${SCRIPT_DIR}/generate_invoice.py" \
  --mode personal \
  --invoice-number "${INVOICE_NUMBER}" \
  --client soulv \
  --item "Finance Recons @ Flash (42.50 hours x R650)" 27300.00 
