# Contributing to mm

The bar is **minimal and correct**. mm is a box you put items into at
runtime. A feature earns its place by keeping that true, not by seeding
the day from a config file.

## The design rules

1. **Nothing appears unless the user typed `mm add`.** No preload, no
   rotation, no habits, no weekday tables, no auto-inject.
2. **Three containers only:** queue (FIFO), interrupt stack (LIFO),
   quick (batched). Do not add a fourth.
3. **Stdlib only.** No runtime dependencies. `python -S -c "import mm.cli"`
   must keep working; CI enforces it.
4. **One state file:** `~/.mm/state.json`. File lock, atomic save, undo
   snapshots. Do not add a second format “for compatibility.”
5. **Docs agree.** `README.md`, `mm/data/mm.1`, and the `--help` strings
   in `mm/cli.py` describe the same verbs.

## Working on it

```bash
git clone https://github.com/Toseef-Ahmad/mm.git
cd mm
python3 -m unittest discover -s tests -v   # must be green before and after
./install.sh                               # ~/bin/mm -> this clone, plus man mm
```

Tests use an isolated temp directory through `mm.use_home()`, so they never
touch your real `~/.mm`.

## Pull requests

- One behaviour change per PR, with a test in `tests/test_mm.py`.
- Tests cover queue / stack / quick only.
- Bug fixes: include the reproduction in the test.

## Cutting a release (maintainers)

1. Bump `__version__` in `mm/__init__.py`. That is the only place a version
   lives; the build reads it and release CI refuses a tag that disagrees.
2. Add the section to `CHANGELOG.md`.
3. Tag and push: `git tag -a vX.Y.Z -m "…" && git push origin vX.Y.Z`.
4. `gh release create vX.Y.Z --notes-file …`

Publishing to PyPI is off until it is configured. To turn it on: create a
PyPI [trusted publisher] for this repository with workflow `release.yml`
and environment `pypi`, then set the repository variable `PYPI_ENABLED=true`.

[trusted publisher]: https://docs.pypi.org/trusted-publishers/

## Reporting a bug

Include `mm --version`, your OS, and the command you ran. `mm export` and
the shape of `~/.mm/state.json` help more than a paraphrase. Redact task
names freely.
