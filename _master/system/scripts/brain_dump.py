#!/usr/bin/env python3
"""Ingest one Apple Note into a vault file, then optionally clear it."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from script_utils import resolve_vault_root


CONFIG_PATH = Path("_master/system/config.json")
DEFAULT_CONFIG = {
    "enabled": True,
    "note_name": "Brain Dump",
    "output_path": "_master/system/inbox/BRAIN_DUMP.md",
    "attachments_path": "_master/system/inbox/BRAIN_DUMP_ATTACHMENTS",
    "copy_attachments": True,
    "clear_after_ingest": False,
    "cleared_note_body": "<div><br></div>",
}


class AppleNotesHTMLToMarkdown(HTMLParser):
    """Small, dependency-free converter for the HTML returned by Apple Notes."""

    BLOCK_TAGS = {"div", "p", "section", "article", "blockquote"}
    BREAK_TAGS = {"br"}
    LIST_TAGS = {"ul", "ol"}
    ITEM_TAGS = {"li"}
    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(
        self,
        attachment_links: dict[str, str] | None = None,
        attachment_fallback_links: list[str] | None = None,
    ) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.href_stack: list[str | None] = []
        self.list_stack: list[str] = []
        self.attachment_links = attachment_links or {}
        self.attachment_fallback_links = attachment_fallback_links or []
        self.used_attachment_links: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self.BLOCK_TAGS:
            self._ensure_blank_line()
        elif tag in self.BREAK_TAGS:
            self._ensure_newline()
        elif tag in self.LIST_TAGS:
            self.list_stack.append(tag)
            self._ensure_blank_line()
        elif tag in self.ITEM_TAGS:
            self._ensure_newline()
            self.parts.append("- ")
        elif tag in self.HEADING_TAGS:
            level = int(tag[1])
            self._ensure_blank_line()
            self.parts.append("#" * level + " ")
        elif tag == "a":
            href = next((value for key, value in attrs if key.lower() == "href"), None)
            self.href_stack.append(href)
        elif tag in {"img", "object", "embed"}:
            src = next((value for key, value in attrs if key.lower() in {"src", "data"}), None)
            if src:
                link = self._attachment_link(src)
                if link:
                    self._ensure_newline()
                    self.parts.append(link)
                    self._ensure_newline()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.BLOCK_TAGS or tag in self.ITEM_TAGS or tag in self.HEADING_TAGS:
            self._ensure_newline()
        elif tag in self.LIST_TAGS:
            if self.list_stack:
                self.list_stack.pop()
            self._ensure_blank_line()
        elif tag == "a" and self.href_stack:
            self.href_stack.pop()

    def handle_data(self, data: str) -> None:
        if not data:
            return
        text = html.unescape(data).replace("\xa0", " ")
        if not text.strip():
            if self.parts and not self.parts[-1].endswith((" ", "\n")):
                self.parts.append(" ")
            return
        text = re.sub(r"\s+", " ", text)
        self.parts.append(text)

    def get_markdown(self) -> str:
        text = "".join(self.parts)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _attachment_link(self, source: str) -> str | None:
        candidates = attachment_key_candidates(source)
        for candidate in candidates:
            link = self.attachment_links.get(candidate)
            if link:
                self.used_attachment_links.add(link)
                return link
        if is_inline_attachment_source(source):
            return self._next_unused_attachment_link()
        return None

    def _next_unused_attachment_link(self) -> str | None:
        for link in self.attachment_fallback_links:
            if link not in self.used_attachment_links:
                self.used_attachment_links.add(link)
                return link
        return None

    def _ensure_newline(self) -> None:
        if not self.parts or self.parts[-1].endswith("\n"):
            return
        self.parts.append("\n")

    def _ensure_blank_line(self) -> None:
        if not self.parts:
            return
        current = "".join(self.parts)
        if current.endswith("\n\n"):
            return
        if current.endswith("\n"):
            self.parts.append("\n")
        else:
            self.parts.append("\n\n")


def load_config(root: Path, config_arg: str | None) -> dict[str, Any]:
    config_path = root / (config_arg or CONFIG_PATH)
    if not config_path.exists():
        return dict(DEFAULT_CONFIG)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    ingest_config = data.get("brain_dump_ingest", {})
    return {**DEFAULT_CONFIG, **ingest_config}


def attachment_key_candidates(value: str) -> list[str]:
    clean = value.strip()
    without_cid = re.sub(r"^cid:", "", clean, flags=re.I)
    without_angles = without_cid.strip("<>")
    return list(dict.fromkeys([clean, without_cid, without_angles, f"cid:{without_angles}"]))


def is_inline_attachment_source(source: str) -> bool:
    return source.strip().lower().startswith("data:")


def html_to_markdown(
    note_html: str,
    attachment_links: dict[str, str] | None = None,
    attachment_fallback_links: list[str] | None = None,
) -> tuple[str, set[str]]:
    parser = AppleNotesHTMLToMarkdown(attachment_links, attachment_fallback_links)
    parser.feed(note_html)
    parser.close()
    markdown = parser.get_markdown()
    if markdown:
        return markdown, parser.used_attachment_links
    fallback = re.sub(r"<br\s*/?>", "\n", note_html, flags=re.I)
    fallback = re.sub(r"</(div|p|li|h[1-6])>", "\n", fallback, flags=re.I)
    fallback = re.sub(r"<[^>]+>", "", fallback)
    return html.unescape(fallback).strip(), parser.used_attachment_links


def is_effectively_empty(markdown: str) -> bool:
    compact = re.sub(r"\s+", "", markdown)
    return compact in {"", "#BrainDump", "BrainDump"}


def strip_generated_note_title(markdown: str, note_name: str) -> str:
    title_pattern = re.escape(note_name.strip())
    if not title_pattern:
        return markdown.strip()
    lines = markdown.strip().splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return ""

    first = lines[0].strip()
    if re.fullmatch(rf"#{{1,6}}\s+{title_pattern}", first, flags=re.I) or re.fullmatch(
        title_pattern,
        first,
        flags=re.I,
    ):
        lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)
    return "\n".join(lines).strip()


def fetch_brain_dump_note(note_name: str, clear: bool, cleared_note_body: str) -> str:
    script = r'''
on run argv
  set noteTitle to item 1 of argv
  set shouldClear to item 2 of argv
  set clearBody to item 3 of argv
  tell application "Notes"
    set matchedNotes to notes whose name is noteTitle
    if (count of matchedNotes) is 0 then
      error "Apple Note not found: " & noteTitle number 1001
    end if
    if (count of matchedNotes) is greater than 1 then
      error "Multiple Apple Notes named: " & noteTitle & ". Rename one so refresh can target it safely." number 1002
    end if
    set targetNote to item 1 of matchedNotes
    set noteBody to body of targetNote
    if shouldClear is "true" then
      set body of targetNote to clearBody
    end if
    return noteBody
  end tell
end run
'''
    result = subprocess.run(
        ["osascript", "-e", script, note_name, "true" if clear else "false", cleared_note_body],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise SystemExit(f"Apple Notes ingest failed: {detail}")
    return result.stdout


def clear_body_for_note(template: str, note_name: str) -> str:
    return template.format(note_name=html.escape(note_name))


def save_brain_dump_attachments(note_name: str, attachments_dir: Path, import_id: str) -> list[dict[str, str]]:
    attachments_dir.mkdir(parents=True, exist_ok=True)
    script = r'''
on sanitizeFileName(rawName)
  set safeName to rawName as text
  set badChars to {":", "/", return, linefeed, tab}
  repeat with badChar in badChars
    set AppleScript's text item delimiters to badChar
    set nameParts to text items of safeName
    set AppleScript's text item delimiters to "-"
    set safeName to nameParts as text
  end repeat
  set AppleScript's text item delimiters to ""
  if safeName is "" then set safeName to "attachment"
  return safeName
end sanitizeFileName

on run argv
  set noteTitle to item 1 of argv
  set outputDir to item 2 of argv
  set importPrefix to item 3 of argv
  set outputLines to {}
  tell application "Notes"
    set matchedNotes to notes whose name is noteTitle
    if (count of matchedNotes) is 0 then
      error "Apple Note not found: " & noteTitle number 1001
    end if
    if (count of matchedNotes) is greater than 1 then
      error "Multiple Apple Notes named: " & noteTitle & ". Rename one so refresh can target it safely." number 1002
    end if
    set targetNote to item 1 of matchedNotes
    set attachmentIndex to 0
    repeat with noteAttachment in attachments of targetNote
      set attachmentIndex to attachmentIndex + 1
      set attachmentName to name of noteAttachment
      if attachmentName is missing value or attachmentName is "" then set attachmentName to "attachment-" & attachmentIndex
      set safeName to my sanitizeFileName(attachmentName)
      set outputName to importPrefix & "-" & attachmentIndex & "-" & safeName
      set outputPath to outputDir & "/" & outputName
      save noteAttachment in (POSIX file outputPath)
      set attachmentCID to ""
      set attachmentURL to ""
      try
        set attachmentCID to content identifier of noteAttachment
      end try
      try
        set attachmentURL to URL of noteAttachment
      end try
      set end of outputLines to attachmentCID & tab & attachmentName & tab & outputName & tab & attachmentURL
    end repeat
  end tell
  set AppleScript's text item delimiters to linefeed
  set outputText to outputLines as text
  set AppleScript's text item delimiters to ""
  return outputText
end run
'''
    result = subprocess.run(
        ["osascript", "-e", script, note_name, str(attachments_dir), import_id],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise SystemExit(f"Apple Notes attachment ingest failed: {detail}")

    attachments: list[dict[str, str]] = []
    for raw_line in result.stdout.splitlines():
        if not raw_line.strip():
            continue
        cid, original_name, output_name, url = (raw_line.split("\t") + ["", "", "", ""])[:4]
        attachments.append(
            {
                "cid": cid.strip(),
                "original_name": original_name.strip() or output_name.strip(),
                "output_name": output_name.strip(),
                "url": url.strip(),
            }
        )
    return attachments


def build_attachment_links(root: Path, attachments_dir: Path, attachments: list[dict[str, str]]) -> dict[str, str]:
    links: dict[str, str] = {}
    for attachment in attachments:
        output_name = attachment["output_name"]
        vault_path = (attachments_dir / output_name).relative_to(root)
        label = f"![[{vault_path}]]"
        for key in [attachment.get("cid", ""), attachment.get("url", "")]:
            for candidate in attachment_key_candidates(key):
                if candidate:
                    links[candidate] = label
    return links


def build_attachment_link_sequence(root: Path, attachments_dir: Path, attachments: list[dict[str, str]]) -> list[str]:
    links: list[str] = []
    for attachment in attachments:
        output_name = attachment["output_name"]
        vault_path = (attachments_dir / output_name).relative_to(root)
        links.append(f"![[{vault_path}]]")
    return links


def attachment_section(root: Path, attachments_dir: Path, attachments: list[dict[str, str]], used_links: set[str]) -> str:
    lines: list[str] = []
    for attachment in attachments:
        vault_path = (attachments_dir / attachment["output_name"]).relative_to(root)
        link = f"![[{vault_path}]]"
        if link in used_links:
            continue
        name = attachment["original_name"] or attachment["output_name"]
        lines.append(f"- [[{vault_path}|{name}]]")
    if not lines:
        return ""
    return "\n\n" + "\n".join(lines)


def prepend_entry(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = f"{body.strip()}\n\n"
    if not path.exists():
        path.write_text(entry, encoding="utf-8")
        return
    existing = path.read_text(encoding="utf-8")
    path.write_text(f"{entry}{existing.lstrip()}", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest a single Apple Note into a vault file.")
    parser.add_argument("--root", default=None, help="Vault root. Defaults to auto-discovery.")
    parser.add_argument("--config", default=None, help="Vault-relative config path. Defaults to _master/system/config.json.")
    parser.add_argument("--note", default=None, help="Apple Note title. Defaults to config brain_dump_ingest.note_name.")
    parser.add_argument("--out", default=None, help="Vault-relative output path.")
    parser.add_argument("--attachments-dir", default=None, help="Vault-relative folder for copied attachments.")
    parser.add_argument("--no-attachments", action="store_true", help="Do not copy Apple Notes attachments.")
    parser.add_argument("--clear", action="store_true", help="Clear the Apple Note after a successful fetch.")
    parser.add_argument("--no-clear", action="store_true", help="Do not clear the Apple Note, overriding config.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be ingested without writing or clearing.")
    args = parser.parse_args(argv)

    root = resolve_vault_root(args.root, __file__)
    config = load_config(root, args.config)
    if not config.get("enabled", True):
        print("Apple Notes ingest disabled in config.")
        return 0

    note_name = args.note or str(config["note_name"])
    output_path = root / (args.out or str(config["output_path"]))
    attachments_dir = root / (args.attachments_dir or str(config["attachments_path"]))
    copy_attachments = bool(config.get("copy_attachments", True)) and not args.no_attachments
    clear = bool(config.get("clear_after_ingest", False))
    if args.clear:
        clear = True
    if args.no_clear or args.dry_run:
        clear = False

    cleared_note_body = clear_body_for_note(str(config["cleared_note_body"]), note_name)
    raw_body = fetch_brain_dump_note(note_name, clear=False, cleared_note_body=cleared_note_body)
    import_id = dt.datetime.now().strftime("%Y%m%dT%H%M%S")

    attachments: list[dict[str, str]] = []
    attachment_links: dict[str, str] = {}
    attachment_fallback_links: list[str] = []
    used_attachment_links: set[str] = set()
    if copy_attachments and not args.dry_run:
        attachments = save_brain_dump_attachments(note_name, attachments_dir, import_id)
        attachment_links = build_attachment_links(root, attachments_dir, attachments)
        attachment_fallback_links = build_attachment_link_sequence(root, attachments_dir, attachments)

    markdown, used_attachment_links = html_to_markdown(raw_body, attachment_links, attachment_fallback_links)
    markdown = strip_generated_note_title(markdown, note_name)
    if attachments:
        markdown = markdown + attachment_section(root, attachments_dir, attachments, used_attachment_links)

    if is_effectively_empty(markdown) and not attachments:
        print(f"Apple Note '{note_name}' is empty; nothing to ingest.")
        return 0

    if args.dry_run:
        print(f"Would ingest Apple Note '{note_name}' into {output_path.relative_to(root)}")
        if copy_attachments:
            print("Dry run did not copy attachments.")
        print(markdown)
        return 0

    prepend_entry(output_path, markdown)

    if clear:
        fetch_brain_dump_note(note_name, clear=True, cleared_note_body=cleared_note_body)
        print(f"Ingested and cleared Apple Note '{note_name}' into {output_path.relative_to(root)}")
    else:
        print(f"Ingested Apple Note '{note_name}' into {output_path.relative_to(root)} without clearing it.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
