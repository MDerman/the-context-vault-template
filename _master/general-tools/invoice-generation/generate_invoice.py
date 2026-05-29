#!/usr/bin/env python3
"""Invoice CLI + vector PDF renderer."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from reportlab.lib.colors import black, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


CENT = Decimal("0.01")
SCRIPT_DIR = Path(__file__).resolve().parent
CONSTANTS_PATH = SCRIPT_DIR / "invoice.constants.json"
OUTPUT_DIR = SCRIPT_DIR / "output"


class SafeFormatDict(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return ""


@dataclass(frozen=True)
class LineItem:
    description: str
    amount: Decimal


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def parse_amount(raw_value: str) -> Decimal:
    cleaned = raw_value.strip().replace(",", "")
    if cleaned.upper().startswith("R"):
        cleaned = cleaned[1:].strip()
    if not cleaned:
        raise ValueError("Item amount cannot be empty.")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid item amount: {raw_value!r}") from exc
    if amount < 0:
        raise ValueError(f"Item amount must be non-negative: {raw_value!r}")
    return quantize_money(amount)


def format_money(value: Decimal, symbol: str) -> str:
    return f"{symbol} {value:,.2f}"


def format_number(value: Decimal) -> str:
    return f"{value:,.2f}"


def format_template(value: Any, context: dict[str, str]) -> str:
    try:
        return str(value).format_map(SafeFormatDict(context))
    except Exception:
        return str(value)


def load_constants() -> dict[str, Any]:
    if not CONSTANTS_PATH.exists():
        raise ValueError(f"Constants file not found: {CONSTANTS_PATH}")
    with CONSTANTS_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    required = [
        "invoice_modes",
        "clients",
        "labels",
        "layout",
        "fonts",
    ]
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"Missing required constant keys: {', '.join(missing)}")
    if not isinstance(data["clients"], list) or not data["clients"]:
        raise ValueError("Constants key 'clients' must be a non-empty array.")
    if not isinstance(data["invoice_modes"], dict) or not data["invoice_modes"]:
        raise ValueError("Constants key 'invoice_modes' must be a non-empty object.")
    return data


def resolve_font(alias: str, candidates: list[str], fallback: str) -> str:
    if alias in pdfmetrics.getRegisteredFontNames():
        return alias
    for candidate in candidates:
        font_path = Path(candidate).expanduser()
        if not font_path.exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont(alias, str(font_path)))
            return alias
        except Exception:
            continue
    return fallback


def resolve_configured_font(
    fonts: dict[str, Any],
    alias: str,
    config_key: str,
    legacy_candidates_key: str,
    legacy_fallback_key: str,
    default_fallback: str,
) -> str:
    config_value = fonts.get(config_key)
    if isinstance(config_value, dict):
        candidates = [str(candidate) for candidate in config_value.get("candidates", [])]
        fallback = str(config_value.get("fallback", default_fallback))
        return resolve_font(alias=alias, candidates=candidates, fallback=fallback)
    candidates = [str(candidate) for candidate in fonts.get(legacy_candidates_key, [])]
    fallback = str(fonts.get(legacy_fallback_key, default_fallback))
    return resolve_font(alias=alias, candidates=candidates, fallback=fallback)


def text_fit(c: canvas.Canvas, text: str, font_name: str, font_size: float, max_width: float) -> str:
    if pdfmetrics.stringWidth(text, font_name, font_size) <= max_width:
        return text
    trimmed = text
    while trimmed:
        trimmed = trimmed[:-1]
        candidate = f"{trimmed}..."
        if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
            return candidate
    return "..."


def fit_font_size(
    text: str, font_name: str, preferred_size: float, max_width: float, min_size: float = 14.0
) -> float:
    size = preferred_size
    while size > min_size:
        if pdfmetrics.stringWidth(text, font_name, size) <= max_width:
            return size
        size -= 1
    return min_size


def split_line_to_width(text: str, font_name: str, font_size: float, max_width: float) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate one-page invoice PDF using constants from invoice.constants.json."
    )
    parser.add_argument("--invoice-number", type=str, help="Invoice number, e.g. 001845")
    parser.add_argument("--mode", type=str, help="Invoice mode from invoice.constants.json invoice_modes keys")
    parser.add_argument("--client", type=str, help="Client short name from invoice.constants.json clients[].name")
    parser.add_argument(
        "--item",
        action="append",
        nargs=2,
        metavar=("DESCRIPTION", "AMOUNT"),
        help='Repeatable line item pair: --item "Description" 3500',
    )
    return parser.parse_args()


def get_mode_map(constants: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mode_map: dict[str, dict[str, Any]] = {}
    for mode_name, mode_data in constants["invoice_modes"].items():
        if not isinstance(mode_data, dict):
            raise ValueError(f"Invalid mode {mode_name!r}; expected object.")
        required_mode_keys = ["brand", "business", "payment", "footer", "invoice_defaults"]
        missing_mode_keys = [key for key in required_mode_keys if key not in mode_data]
        if missing_mode_keys:
            missing = ", ".join(missing_mode_keys)
            raise ValueError(f"Mode {mode_name!r} is missing required keys: {missing}")
        mode_map[str(mode_name)] = mode_data
    if not mode_map:
        raise ValueError("No invoice modes configured.")
    return mode_map


def prompt_mode_name(mode_map: dict[str, dict[str, Any]]) -> str:
    available = ", ".join(sorted(mode_map.keys()))
    print(f"Available modes: {available}")
    while True:
        selected = input("Mode: ").strip()
        if selected in mode_map:
            return selected
        print(f"Invalid mode. Choose one of: {available}", file=sys.stderr)


def collect_mode_name(constants: dict[str, Any], raw_mode_name: str | None) -> str:
    mode_map = get_mode_map(constants)
    default_mode = str(constants.get("default_mode", "")).strip()
    if raw_mode_name is None:
        if default_mode and default_mode in mode_map:
            return default_mode
        return prompt_mode_name(mode_map)
    selected = raw_mode_name.strip()
    if not selected:
        raise ValueError("Mode cannot be empty.")
    if selected not in mode_map:
        available = ", ".join(sorted(mode_map.keys()))
        raise ValueError(f"Unknown mode {selected!r}. Valid modes: {available}")
    return selected


def resolve_mode_constants(constants: dict[str, Any], mode_name: str) -> dict[str, Any]:
    mode_map = get_mode_map(constants)
    mode_data = mode_map[mode_name]
    merged = dict(constants)
    merged.update(mode_data)
    return merged


def prompt_invoice_number() -> str:
    while True:
        invoice_number = input("Invoice number: ").strip()
        if invoice_number:
            return invoice_number
        print("Invoice number cannot be empty.", file=sys.stderr)


def prompt_items() -> list[LineItem]:
    print("Add line items. Leave description blank to finish.")
    items: list[LineItem] = []
    while True:
        description = input(f"Item {len(items) + 1} description: ").strip()
        if not description:
            if items:
                return items
            print("At least one line item is required.", file=sys.stderr)
            continue
        amount_raw = input("Amount (ZAR): ").strip()
        try:
            amount = parse_amount(amount_raw)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            continue
        items.append(LineItem(description=description, amount=amount))


def get_client_map(constants: dict[str, Any]) -> dict[str, str]:
    client_map: dict[str, str] = {}
    for index, client in enumerate(constants["clients"]):
        if not isinstance(client, dict):
            raise ValueError(f"Invalid client entry at index {index}; expected object.")
        name = str(client.get("name", "")).strip()
        display_name = str(client.get("display_name", "")).strip()
        if not name or not display_name:
            raise ValueError(f"Client entry at index {index} must include non-empty name and display_name.")
        client_map[name] = display_name
    return client_map


def prompt_client_name(client_map: dict[str, str]) -> str:
    available = ", ".join(sorted(client_map.keys()))
    print(f"Available clients: {available}")
    while True:
        selected = input("Client name: ").strip()
        if selected in client_map:
            return selected
        print(f"Invalid client name. Choose one of: {available}", file=sys.stderr)


def collect_client_name(constants: dict[str, Any], raw_client_name: str | None) -> str:
    client_map = get_client_map(constants)
    if raw_client_name is None:
        return prompt_client_name(client_map)
    selected = raw_client_name.strip()
    if not selected:
        raise ValueError("Client name cannot be empty.")
    if selected not in client_map:
        available = ", ".join(sorted(client_map.keys()))
        raise ValueError(f"Unknown client {selected!r}. Valid clients: {available}")
    return selected


def normalize_invoice_number(raw_value: str) -> str:
    invoice_number = raw_value.strip()
    if not invoice_number:
        raise ValueError("Invoice number cannot be empty.")
    if "/" in invoice_number or "\\" in invoice_number:
        raise ValueError("Invoice number cannot contain path separators.")
    return invoice_number


def collect_items(arg_items: list[list[str]] | None) -> list[LineItem]:
    if not arg_items:
        return prompt_items()
    parsed: list[LineItem] = []
    for raw_description, raw_amount in arg_items:
        description = raw_description.strip()
        if not description:
            raise ValueError("Item description cannot be empty.")
        parsed.append(LineItem(description=description, amount=parse_amount(raw_amount)))
    if not parsed:
        raise ValueError("At least one line item is required.")
    return parsed


def compute_totals(items: list[LineItem], discount: Decimal, vat_rate_percent: Decimal) -> dict[str, Decimal]:
    subtotal = quantize_money(sum((item.amount for item in items), start=Decimal("0.00")))
    discount = quantize_money(discount)
    net_subtotal = quantize_money(subtotal - discount)
    vat_amount = quantize_money(net_subtotal * (vat_rate_percent / Decimal("100")))
    total = quantize_money(net_subtotal + vat_amount)
    return {
        "subtotal": subtotal,
        "discount": discount,
        "net_subtotal": net_subtotal,
        "vat_amount": vat_amount,
        "total": total,
        "balance_due": total,
    }


def parse_iso_date(raw_value: str) -> date | None:
    raw = raw_value.strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def format_date_readable(value: date) -> str:
    return f"{value.day} {value.strftime('%B %Y')}"


def render_invoice(
    constants: dict[str, Any],
    invoice_number: str,
    client_display_name: str,
    items: list[LineItem],
    output_path: Path,
) -> None:
    labels = constants["labels"]
    brand = constants["brand"]
    business = constants["business"]
    payment = constants["payment"]
    footer = constants["footer"]
    defaults = constants["invoice_defaults"]
    layout = constants["layout"]
    fonts = constants["fonts"]

    vat_rate_percent = Decimal(str(defaults.get("vat_rate_percent", 0)))
    discount_amount = Decimal(str(defaults.get("discount_amount", 0)))
    currency_symbol = str(defaults.get("currency_symbol", "R"))
    issue_date_iso = str(defaults.get("issue_date_iso", "")).strip()
    parsed_issue_date = parse_iso_date(issue_date_iso)
    issue_date = str(defaults.get("issue_date_display", "")).strip()
    if not issue_date and parsed_issue_date:
        issue_date = format_date_readable(parsed_issue_date)
    payment_terms_days = int(defaults.get("payment_terms_days", 0) or 0)
    due_date_display = str(defaults.get("due_date_display", "")).strip()
    if not due_date_display and parsed_issue_date and payment_terms_days > 0:
        due_date_display = format_date_readable(parsed_issue_date + timedelta(days=payment_terms_days))

    totals = compute_totals(items, discount_amount, vat_rate_percent)

    page_width = float(layout["page"]["width"])
    page_height = float(layout["page"]["height"])
    margins = layout["margins"]
    coords = layout["coordinates"]
    columns = layout["columns"]
    rows = layout["row_heights"]
    font_sizes = layout["font_sizes"]
    max_items = int(layout["limits"]["max_items"])
    if len(items) > max_items:
        raise ValueError(f"Too many line items ({len(items)}). Maximum supported is {max_items}.")

    left = float(margins["left"])
    right = page_width - float(margins["right"])

    heading_font = resolve_configured_font(
        fonts=fonts,
        alias="InvoiceHeading",
        config_key="headingFont",
        legacy_candidates_key="bold_candidates",
        legacy_fallback_key="fallback_bold",
        default_fallback="Helvetica-Bold",
    )
    body_font = resolve_configured_font(
        fonts=fonts,
        alias="InvoiceBody",
        config_key="bodyFont",
        legacy_candidates_key="regular_candidates",
        legacy_fallback_key="fallback_regular",
        default_fallback="Helvetica",
    )

    client_context = {
        "invoice_number": invoice_number,
        "client_display_name": client_display_name,
        "issue_date": issue_date,
        "issue_date_iso": issue_date_iso,
        "payment_terms_days": str(payment_terms_days),
        "due_date": due_date_display,
        "currency_code": str(defaults.get("currency_code", "")).strip(),
        "currency_symbol": currency_symbol,
    }

    registration_line = ""
    vat_line = ""
    if bool(business.get("show_registration_number", False)):
        registration_line = str(business.get("registration_number", "")).strip()
    if bool(business.get("show_vat_number", False)):
        vat_line = str(business.get("vat_number", "")).strip()
    client_context["registration_line"] = registration_line
    client_context["vat_line"] = vat_line

    c = canvas.Canvas(str(output_path), pagesize=(page_width, page_height))
    c.setFillColor(black)
    c.rect(0, 0, page_width, page_height, fill=1, stroke=0)
    c.setFillColor(white)
    c.setStrokeColor(white)
    c.setLineWidth(float(layout.get("line_width", 1.0)))

    company_name = str(brand.get("company_name", ""))
    if bool(brand.get("use_brackets", False)):
        company_name = f"[{company_name}]"
    masthead_font_size = fit_font_size(
        text=company_name,
        font_name=heading_font,
        preferred_size=float(font_sizes["brand"]),
        max_width=right - left,
        min_size=18.0,
    )
    c.setFont(heading_font, masthead_font_size)
    c.drawString(left, float(coords["masthead_y"]), company_name)

    invoice_title = str(labels["invoice"])
    invoice_title_size = float(font_sizes["invoice_title"])
    invoice_title_y = float(coords["invoice_title_y"])
    c.setFont(heading_font, invoice_title_size)
    c.drawRightString(right, invoice_title_y, invoice_title)

    meta_y = float(coords["metadata_y"])
    meta_size = float(font_sizes["meta"])
    meta_gap = float(columns.get("meta_gap", 16))
    meta_col1_x = float(columns.get("meta_col1_x", columns.get("meta_date_x", left)))
    invoice_left_x = right - pdfmetrics.stringWidth(invoice_title, heading_font, invoice_title_size)
    meta_col1_text = format_template(
        labels.get("meta_col1_format", "{issue_date}  [#{invoice_number}]"),
        client_context,
    )
    meta_col2_text = format_template(
        labels.get("meta_col2_format", labels.get("meta_client_format", "{client_display_name}")),
        client_context,
    )
    meta_max_width = max(24.0, invoice_left_x - meta_col1_x - 18.0)
    min_meta_size = 7.0
    while meta_size > min_meta_size:
        col1_width = pdfmetrics.stringWidth(meta_col1_text, body_font, meta_size)
        col2_width = pdfmetrics.stringWidth(meta_col2_text, body_font, meta_size)
        if col1_width + meta_gap + col2_width <= meta_max_width:
            break
        meta_size -= 0.5
    c.setFont(body_font, meta_size)
    col1_width = pdfmetrics.stringWidth(meta_col1_text, body_font, meta_size)
    meta_col2_x = meta_col1_x + col1_width + meta_gap
    c.drawString(meta_col1_x, meta_y, meta_col1_text)
    c.drawString(meta_col2_x, meta_y, meta_col2_text)

    c.line(left, float(coords["table_divider_y"]), right, float(coords["table_divider_y"]))
    c.setFont(body_font, float(font_sizes["table"]))
    row_y = float(coords["table_start_y"])
    desc_width = float(columns["table_qty_x"]) - float(columns["table_description_x"]) - 20
    for item in items:
        line_tax = quantize_money(item.amount * (vat_rate_percent / Decimal("100")))
        c.drawString(
            float(columns["table_description_x"]),
            row_y,
            text_fit(c, item.description, body_font, float(font_sizes["table"]), desc_width),
        )
        c.drawRightString(float(columns["table_qty_x"]), row_y, "1")
        c.drawRightString(float(columns["table_rate_x"]), row_y, format_number(item.amount))
        c.drawRightString(float(columns["table_tax_x"]), row_y, format_number(line_tax))
        c.drawRightString(float(columns["table_total_x"]), row_y, format_number(item.amount))
        row_y -= float(rows["table"])

    totals_rows: list[tuple[str, str]] = [
        (str(labels["subtotal"]), format_money(totals["subtotal"], currency_symbol)),
        (str(labels["discount"]), format_money(totals["discount"], currency_symbol)),
    ]
    if vat_rate_percent > 0:
        vat_label = f'{labels["vat"]} ({vat_rate_percent:,.2f}%)'
        totals_rows.append((vat_label, format_money(totals["vat_amount"], currency_symbol)))
    totals_rows.append((str(labels["total"]), format_money(totals["total"], currency_symbol)))

    c.setFont(heading_font, float(font_sizes["totals"]))
    totals_y = float(coords["totals_start_y"])
    for row_label, row_value in totals_rows:
        c.drawString(float(columns["totals_label_x"]), totals_y, row_label)
        c.drawRightString(float(columns["totals_value_x"]), totals_y, row_value)
        totals_y -= float(rows["totals"])
    c.drawString(
        float(columns["totals_label_x"]),
        totals_y - 8,
        format_template(str(labels["balance_due"]), client_context),
    )
    c.drawRightString(
        float(columns["totals_value_x"]),
        totals_y - 8,
        format_money(totals["balance_due"], currency_symbol),
    )

    bottom_y = float(coords["bottom_section_y"])
    bottom_line_y = float(coords.get("bottom_divider_y", bottom_y + 18))
    c.line(left, bottom_line_y, right, bottom_line_y)

    payment_x = float(columns["payment_x"])
    payment_heading_size = float(font_sizes.get("payment_heading", font_sizes["section_title"]))
    terms_heading_size = float(font_sizes.get("terms_heading", font_sizes["section_title"]))
    payment_heading_y = float(coords.get("payment_heading_y", bottom_y))
    terms_heading_y = float(coords.get("terms_heading_y", bottom_y))
    payment_bank_x = float(columns.get("payment_bank_x", payment_x))
    terms_x = float(columns["terms_x"])
    payment_contact_x = float(columns.get("payment_contact_x", payment_x + ((terms_x - payment_x) / 2.0)))
    payment_bank_width = max(24.0, payment_contact_x - payment_bank_x - 18.0)
    payment_contact_width = max(24.0, terms_x - payment_contact_x - 18.0)

    c.setFont(heading_font, payment_heading_size)
    c.drawString(payment_x, payment_heading_y, str(payment.get("heading", labels["payment"])))
    c.setFont(body_font, float(font_sizes["section_body"]))
    payment_line_start = payment_heading_y - float(rows.get("payment_after_heading", rows["payment"]))
    bank_lines: list[str] = []
    bank_lines.extend(payment.get("header_meta_lines", []))
    bank_lines.extend(payment.get("bank_detail_lines", payment.get("detail_lines", [])))
    contact_lines = payment.get("contact_detail_lines", [])

    payment_bank_y = payment_line_start
    for line in bank_lines:
        rendered = format_template(line, client_context).strip()
        if rendered:
            for wrapped in split_line_to_width(
                rendered, body_font, float(font_sizes["section_body"]), payment_bank_width
            ):
                c.drawString(payment_bank_x, payment_bank_y, wrapped)
                payment_bank_y -= float(rows["payment"])

    payment_contact_y = payment_line_start
    for line in contact_lines:
        rendered = format_template(line, client_context).strip()
        if rendered:
            for wrapped in split_line_to_width(
                rendered, body_font, float(font_sizes["section_body"]), payment_contact_width
            ):
                c.drawString(payment_contact_x, payment_contact_y, wrapped)
                payment_contact_y -= float(rows["payment"])

    terms_width = right - terms_x
    c.setFont(heading_font, terms_heading_size)
    c.drawString(terms_x, terms_heading_y, str(labels["terms"]))
    c.setFont(body_font, float(font_sizes["terms"]))
    terms_y = terms_heading_y - float(rows.get("terms_after_heading", rows["terms"]))
    for line in business.get("legal_terms", []):
        rendered = format_template(line, client_context).strip()
        if not rendered:
            continue
        for wrapped in split_line_to_width(rendered, body_font, float(font_sizes["terms"]), terms_width):
            c.drawString(terms_x, terms_y, wrapped)
            terms_y -= float(rows["terms"])

    c.line(left, float(coords["footer_divider_y"]), right, float(coords["footer_divider_y"]))
    footer_y_start = float(coords["footer_text_y"])
    footer_x_keys = ["footer_col_1_x", "footer_col_2_x", "footer_col_3_x", "footer_col_4_x"]
    c.setFont(body_font, float(font_sizes["footer"]))
    for index, x_key in enumerate(footer_x_keys):
        if index >= len(footer.get("columns", [])):
            continue
        column = footer["columns"][index]
        current_y = footer_y_start
        for line in column.get("lines", []):
            rendered = format_template(line, client_context).strip()
            if rendered:
                c.drawString(float(columns[x_key]), current_y, rendered)
                current_y -= float(rows["footer"])

    c.showPage()
    c.save()


def main() -> int:
    args = parse_args()
    constants = load_constants()
    mode_name = collect_mode_name(constants, args.mode)
    resolved_constants = resolve_mode_constants(constants, mode_name)
    client_map = get_client_map(resolved_constants)

    raw_invoice_number = args.invoice_number if args.invoice_number is not None else prompt_invoice_number()
    invoice_number = normalize_invoice_number(raw_invoice_number)
    client_name = collect_client_name(resolved_constants, args.client)
    client_display_name = client_map[client_name]
    items = collect_items(args.item)
    if not items:
        raise ValueError("At least one line item is required.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"invoice-{invoice_number}.pdf"

    render_invoice(
        constants=resolved_constants,
        invoice_number=invoice_number,
        client_display_name=client_display_name,
        items=items,
        output_path=output_path,
    )
    print(f"Invoice generated: {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        raise SystemExit(1)
