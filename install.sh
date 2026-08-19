#!/bin/sh
# Install mm onto PATH as ~/bin/mm, pointed at this clone, and the mm(1) manual.
set -e
ROOT="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
mkdir -p "$HOME/bin" "$HOME/.local/share/man/man1"
cat > "$HOME/bin/mm" << EOF
#!/usr/bin/env python3
import sys
sys.path.insert(0, "$ROOT")
from mm.cli import main
if __name__ == "__main__":
    main()
EOF
chmod +x "$HOME/bin/mm"
cp "$ROOT/mm/data/mm.1" "$HOME/.local/share/man/man1/mm.1"
# drop stale whatis cache so `man mm` finds the new page
rm -f "$HOME/.local/share/man/man1/mm.1.gz" 2>/dev/null || true
echo "installed $HOME/bin/mm -> $ROOT"
echo "installed $HOME/.local/share/man/man1/mm.1"
echo "try:  man mm"
echo "next: mm init   (if you don't have ~/.mm/mm.toml yet)"
