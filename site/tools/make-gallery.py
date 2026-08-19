#!/usr/bin/env python3
"""Render the Product Hunt launch images.

    python3 site/tools/make-gallery.py

Writes 1270x760 gallery slides and a 240x240 thumbnail into site/launch/. The
slides are drawn by tools/gallery.html from the captured demo data, so a launch
image cannot show output the CLI does not actually produce.

Needs Chrome or Chromium on PATH (or in the usual macOS location). Output is
committed, so this only has to run when the demo or the copy changes.
"""
from __future__ import annotations

import http.server
import os
import shutil
import subprocess
import sys

import threading
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
OUT = SITE / "launch" / "gallery"
PORT = 4399

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
]

SLIDES = [
    "01-one-task", "02-gates", "03-interrupts", "04-obsidian", "05-open-source",
]


def find_chrome() -> str:
    for c in CHROME_CANDIDATES:
        if os.path.isfile(c) or shutil.which(c):
            return c
    sys.exit("Chrome or Chromium not found — install one, or add it to PATH.")


def serve(root: Path) -> http.server.ThreadingHTTPServer:
    """gallery.html loads ../demo-data.js, so it needs an origin, not file://."""
    handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(  # noqa: E731
        *a, directory=str(root), **kw)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def shoot(chrome: str, url: str, dest: Path, size: str) -> None:
    # Deliberately minimal flags. --virtual-time-budget makes Chrome wait on the
    # webfont and never draw if it stalls; a throwaway --user-data-dir sends
    # first-run profile setup into a hang. Neither is needed for a static page.
    subprocess.run(
        [chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
         f"--window-size={size}", f"--screenshot={dest}", url],
        check=True, timeout=120,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    chrome = find_chrome()
    OUT.mkdir(parents=True, exist_ok=True)
    httpd = serve(SITE)
    try:
        for i, name in enumerate(SLIDES):
            dest = OUT / f"{name}.png"
            shoot(chrome, f"http://127.0.0.1:{PORT}/tools/gallery.html#{i}",
                  dest, "1270,760")
            print(f"  {dest.relative_to(SITE.parent)}  "
                  f"{dest.stat().st_size // 1024} KB", file=sys.stderr)

        thumb = OUT.parent / "thumbnail-240.png"
        shoot(chrome, f"http://127.0.0.1:{PORT}/tools/thumbnail.html", thumb, "240,240")
        print(f"  {thumb.relative_to(SITE.parent)}  "
              f"{thumb.stat().st_size // 1024} KB", file=sys.stderr)
    finally:
        httpd.shutdown()
    print("\nUpload the five slides in order; thumbnail goes in its own field.",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
