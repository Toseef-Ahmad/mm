## What this changes

<!-- The decision it removes, or the wrong state it prevents. -->

## Checklist

- [ ] `python3 -m unittest discover -s tests -v` is green
- [ ] A test fails before this change and passes after
- [ ] Still stdlib only (`python3 -S -c "import mm.cli"` works)
- [ ] Docs updated where they overlap: `README.md`, `mm/data/mm.1`, `--help` text
- [ ] `CHANGELOG.md` entry under the unreleased heading
