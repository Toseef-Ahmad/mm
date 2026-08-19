# Contributing to mm

The bar is **minimal and correct**. mm is a tool someone runs twenty times a day,
so a feature earns its place by removing a decision, not by adding an option.

## The design rules

1. **A new command needs a reason the habit model cannot cover.** Most ideas are
   already expressible as `type` + `repeat` + `position` + `gate` on a habit. If
   yours is, add config, not code.
2. **Stdlib only.** No runtime dependencies, ever. `python -S -c "import mm.cli"`
   must keep working, and CI enforces it.
3. **The tool never lies about state.** If mm cannot reach an item, the line says
   why (see `gate-locked`). Silent success is worse than a visible refusal.
4. **You own your files, mm owns its own.** mm may rewrite `~/.mm/state.json`,
   `habits.json`, `books.json`, `obsidian.json`. It must not clobber your
   `mm.toml`, your Obsidian notes, or anything you hand-edited, without reading
   the current contents first.
5. **TOML is the config format.** JSON still loads for compatibility; it is not
   where new work goes.

## Working on it

```bash
git clone https://github.com/Toseef-Ahmad/mm.git
cd mm
python3 -m unittest discover -s tests -v   # must be green before and after
./install.sh                               # ~/bin/mm -> this clone, plus man mm
```

Tests use an isolated temp directory through `mm.use_home()`, so they never touch
your real `~/.mm`. If you find a test that does, that is a bug worth reporting on
its own.

## Pull requests

- One behaviour change per PR, with a test in `tests/test_mm.py` that fails
  before your change and passes after.
- Describe the decision the change removes, or the wrong state it prevents.
- Bug fixes: please include the reproduction in the test. The interesting bugs in
  this codebase have been about two sources of truth disagreeing (see the
  Obsidian shadow in `mm/obsidian.py`), and those only stay fixed when a test
  pins the exact sequence.
- Docs live in three places that must agree: `README.md`, `mm/data/mm.1`, and the
  `--help` strings in `mm/cli.py`.
- If you change what the CLI prints, re-record the landing page demo with
  `python3 site/tools/capture.py` and commit the result. The page shows real
  captured output, so stale frames are a lie about the tool.
- If you change behaviour, `site/docs.html` is the fourth place that must agree,
  then run `python3 site/tools/make-llms-full.py` — CI fails on a stale
  `llms-full.txt`. `site/llms.txt` is hand-written and carries the positioning;
  update it when what the tool *is* changes, not on every behaviour tweak.

## Cutting a release (maintainers)

1. Bump `__version__` in `mm/__init__.py`. That is the only place a version
   lives; the build reads it and release CI refuses a tag that disagrees.
2. Re-record the landing page demo — `python3 site/tools/capture.py` — and commit
   it. The recording carries the version the site displays, so CI fails the
   bump until it is refreshed. Refresh the generated docs and, if the copy or
   demo moved, the launch images:

   ```bash
   python3 site/tools/make-llms-full.py
   python3 site/tools/make-gallery.py   # only before a launch
   cd site && vercel --prod --yes
   ```
3. Add the section to `CHANGELOG.md`.
4. Tag and push: `git tag -a vX.Y.Z -m "…" && git push origin vX.Y.Z`.
5. `gh release create vX.Y.Z --notes-file …`

Publishing to PyPI is off until it is configured, so a tag never leaves a failed
run behind. To turn it on: create a PyPI [trusted publisher] for this repository
with workflow `release.yml` and environment `pypi`, then set the repository
variable `PYPI_ENABLED=true`.

[trusted publisher]: https://docs.pypi.org/trusted-publishers/

## Reporting a bug

Include `mm --version`, your OS, and the command you ran. If it involves habits
or Obsidian, `mm export` and the relevant part of `~/.mm/habits.json` make the
difference between a guess and a fix. Redact freely — the schema matters more
than your task names.
