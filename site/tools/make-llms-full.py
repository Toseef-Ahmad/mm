#!/usr/bin/env python3
"""Render docs.html to site/llms-full.txt as plain text.

    python3 site/tools/make-llms-full.py

AI assistants and search crawlers get a clean, complete copy of the manual
without having to strip markup themselves. It is generated rather than written
so it cannot drift from the page — there is only ever one copy of the docs.
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
SRC = SITE / "docs.html"
OUT = SITE / "llms-full.txt"

SKIP = {"script", "style", "nav", "aside", "header", "footer"}
BLOCK = {"h1", "h2", "h3", "h4", "p", "li", "pre", "tr", "div"}


class DocsToText(HTMLParser):
    """Walks only the <main> content and emits readable plain text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth_skip = 0
        self.in_main = False
        self.main_depth = 0
        self.tag_stack: list[str] = []
        self.buf: list[str] = []
        self.line: list[str] = []
        self.in_pre = False
        self.cells: list[str] = []
        self.in_cell = False

    # -- helpers ---------------------------------------------------------
    def flush(self, prefix: str = "", underline: str = "") -> None:
        text = "".join(self.line)
        if not self.in_pre:
            text = re.sub(r"\s+", " ", text).strip()
        self.line = []
        if not text:
            return
        self.buf.append(prefix + text)
        if underline:
            self.buf.append(underline * min(len(text), 72))
        self.buf.append("")

    # -- parser hooks ----------------------------------------------------
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "main":
            self.in_main = True
        if not self.in_main:
            return
        if tag in SKIP:
            self.depth_skip += 1
            return
        if self.depth_skip:
            return
        if tag in BLOCK and self.line:
            self.flush()
        if tag == "pre":
            self.in_pre = True
        if tag in ("td", "th"):
            self.in_cell = True
        self.tag_stack.append(tag)

    def handle_endtag(self, tag):
        if tag == "main":
            self.in_main = False
        if not self.in_main:
            return
        if tag in SKIP:
            self.depth_skip = max(0, self.depth_skip - 1)
            return
        if self.depth_skip:
            return

        if tag in ("td", "th"):
            cell = re.sub(r"\s+", " ", "".join(self.line)).strip()
            self.line = []
            self.in_cell = False
            if cell:
                self.cells.append(cell)
        elif tag == "tr":
            if self.cells:
                self.buf.append("  " + "  |  ".join(self.cells))
            self.cells = []
        elif tag == "pre":
            code = "".join(self.line).strip("\n")
            self.line = []
            self.in_pre = False
            for ln in code.splitlines():
                self.buf.append("    " + ln.rstrip())
            self.buf.append("")
        elif tag in ("h1", "h2"):
            self.flush(underline="=")
        elif tag == "h3":
            self.flush(underline="-")
        elif tag == "li":
            self.flush(prefix="  - ")
        elif tag in BLOCK:
            self.flush()

        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()

    def handle_data(self, data):
        if not self.in_main or self.depth_skip:
            return
        self.line.append(data if self.in_pre else data)

    def text(self) -> str:
        self.flush()
        out = "\n".join(self.buf)
        return re.sub(r"\n{3,}", "\n\n", out).strip() + "\n"


HEADER = """# mm — full documentation (plain text)

Source: https://mm.tafil.app/docs
Repository: https://github.com/Toseef-Ahmad/mm
Licence: MIT

mm is a free, open-source command-line to-do list and habit tracker. It shows
exactly one task at a time, and while a "gate" is open it refuses to offer any
easier work. Written in Python 3.11+ with zero runtime dependencies. Optional
two-way sync with Obsidian daily-note checkbox properties.

This file is generated from the documentation page so the two cannot disagree.
A shorter overview is at https://mm.tafil.app/llms.txt

---

"""


def main() -> int:
    if not SRC.exists():
        print(f"missing {SRC}", file=sys.stderr)
        return 1
    parser = DocsToText()
    parser.feed(SRC.read_text(encoding="utf-8"))
    OUT.write_text(HEADER + parser.text(), encoding="utf-8")
    words = len(OUT.read_text(encoding="utf-8").split())
    print(f"wrote {OUT.relative_to(SITE.parent)} — {words} words", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
