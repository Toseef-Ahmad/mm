# site/ — the landing page for mm

Live at **[mm.tafil.app](https://mm.tafil.app/)**. Static HTML, hand-written CSS,
one small vanilla-JS file. No framework, no build step, no npm install needed to
work on it.

That is a deliberate match to what it advertises: a page selling a
zero-dependency tool should not ship a CSS runtime and a bundler.

## Layout

```
site/
  index.html        the page
  styles.css        all styling; palette taken from the CLI itself
  terminal.js       the demo player + copy-to-clipboard
  demo-data.js      GENERATED — real captured CLI output
  og.png            GENERATED — link preview image
  favicon.svg
  robots.txt  sitemap.xml  llms.txt
  vercel.json       headers + static config
  tools/
    capture.py      regenerates demo-data.js from the real CLI
    demo.mm.toml    the schedule the demo is recorded against
    og.svg          source for og.png
    make-og.mjs     og.svg -> og.png
```

## The demo is real output

Every terminal frame on the page is genuine `mm` output. `tools/capture.py`
builds a throwaway `MM_HOME` from `tools/demo.mm.toml`, runs the CLI inside a
pseudo-terminal so it emits its true ANSI colours, converts those colours to
`<i class="a|g|w|b|d">` spans, and writes `demo-data.js`.

```bash
python3 tools/capture.py     # from site/, or: python3 site/tools/capture.py
```

It never touches your real `~/.mm`, and the Obsidian scenario builds a throwaway
vault with a real daily note, so that sync demo is a genuine round trip rather
than a story about one.

**Re-run it whenever CLI output changes.** A demo that has drifted from the tool
is worse than no demo, and this is the only guard against that.

The colour classes map to `mm/util.py`: `a` = ANSI 36 (the cyan pointer),
`g` = 32 (done), `w` = 33 (interrupts), `b` = bold, `d` = dim.

## Local preview

```bash
cd site && python3 -m http.server 4321
# http://localhost:4321
```

Absolute paths (`/styles.css`) are used throughout, so it must be served from
the `site/` root rather than opened as a `file://` URL.

## The link preview image

`og.png` is committed because crawlers will not accept SVG for `og:image`. Only
regenerate it when `tools/og.svg` changes:

```bash
npm install          # just @resvg/resvg-js, dev-only
npm run og
```

`tools/og.svg` is deliberately pure ASCII with XML numeric entities for anything
else, so no editor can corrupt its encoding.

## Deploy

Same pattern as the other `*.tafil.app` sites: a Vercel project with no build
step, deployed from this directory.

```bash
cd site
vercel --prod --yes
```

The project is linked through `site/.vercel/`, which is not committed. To relink
on a fresh machine:

```bash
vercel link          # choose the mm-landing project
vercel domains ls    # mm.tafil.app should point at it
```

## Editing conventions

- Keep it honest. If the page claims a behaviour, the demo or the docs must show
  it. The FAQ says gates can be overridden because they can.
- No new runtime dependencies. Fonts come from Google Fonts; everything else is
  local.
- Accessibility is not optional: the demo respects `prefers-reduced-motion` by
  rendering frames instantly, the scenario tabs are a real ARIA tablist with
  arrow-key support, and every control has a label.
- Content-Security-Policy in `vercel.json` allows only self plus Google Fonts. If
  you add a third-party script you have to widen it deliberately.
