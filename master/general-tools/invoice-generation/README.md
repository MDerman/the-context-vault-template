# Invoice CLI + Vector PDF Generator

This folder contains a Python CLI that generates a one-page invoice PDF using vector drawing (no background image).

## Setup

```bash
cd ~/Code/impression/resources/invoices
python3 -m pip install -r requirements.txt
```

## Usage

```bash
python3 ~/Code/impression/resources/invoices/generate_invoice.py \
  --mode business \
  --invoice-number 001845 \
  --client soulv \
  --item "Project Item One" 3500 \
  --item "Project Item Two" 3500
```

`--item` is repeatable and always takes two values:

```bash
--item "<description>" <amount>
```

If `--invoice-number`, `--client`, `--mode` (when no default mode is configured), or all `--item` flags are missing, the CLI prompts interactively.

## Mode Selection

`--mode` must match an `invoice_modes` key in `invoice.constants.json`.

Current configured modes:

- `business`
- `personal`

## Client Selection

`--client` must match `clients[].name` from `invoice.constants.json`.

The invoice renders `clients[].display_name`.

Current configured clients:

- `soulv` -> `Soulv Software (Pty) Ltd`

## Output

The generated PDF is written to:

`~/Code/impression/resources/invoices/output/invoice-<invoiceNumber>.pdf`

Example:

`~/Code/impression/resources/invoices/output/invoice-001845.pdf`

## Runtime Inputs

Only these values are dynamic at runtime:

1. Invoice number
2. Mode (`--mode <mode>`)
3. Client (`--client <name>`)
4. One or more line items (`description + amount`)

All other invoice text and layout settings come from:

`~/Code/impression/resources/invoices/invoice.constants.json`

## Constants Schema

`invoice.constants.json` has these top-level keys:

- `default_mode`: mode used when `--mode` is omitted.
- `invoice_modes`: mode-specific brand/business/payment/footer/defaults blocks.
- `clients`: runtime-selectable clients (`name` + `display_name`).
- `labels`: metadata/totals/balance/section labels (`BALANCE DUE (R)`).
- `layout`: page size and all fixed coordinates/columns/row heights/font sizes.
- `fonts`: separate `headingFont` and `bodyFont` candidate lists with fallbacks.

## VAT Behavior

- When `invoice_defaults.vat_rate_percent` is `0`, the VAT row is hidden.
- When `invoice_defaults.vat_rate_percent` is greater than `0`, the VAT row is shown and included in totals.

## Privacy Flags

Inside each mode's `business` block:

- `show_registration_number`
- `show_vat_number`

Both default to `false`. When `false`, those fields do not render in the footer column placeholders.

## Due Date / Terms

Inside each mode's `invoice_defaults`:

- `issue_date_iso` (`YYYY-MM-DD`)
- `issue_date_display`
- `payment_terms_days`

`due_date` can be computed from `issue_date_iso + payment_terms_days` and used in payment text templates.

## Validation / Smoke Check

Generate:

```bash
python3 ~/Code/impression/resources/invoices/generate_invoice.py \
  --mode business \
  --invoice-number 001845 \
  --client soulv \
  --item "Project Item One" 3500 \
  --item "Project Item Two" 3500
```

Optional text extraction check:

```bash
python3 - <<'PY'
from pypdf import PdfReader
pdf = "~/Code/impression/resources/invoices/output/invoice-001845.pdf"
text = "\n".join(page.extract_text() or "" for page in PdfReader(pdf).pages)
for needle in ["001845", "INVOICE", "BALANCE DUE (R)"]:
    print(needle, "=>", needle in text)
PY
```

## Reusable Script

This repo now includes:

`~/Code/impression/resources/invoices/generate_soulv_finance_recons_invoice.sh`

Run it:

```bash
~/Code/impression/resources/invoices/generate_soulv_finance_recons_invoice.sh
```

Optional invoice number override:

```bash
~/Code/impression/resources/invoices/generate_soulv_finance_recons_invoice.sh SOULV-2026-03-02-ALT
```
