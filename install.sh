#!/bin/sh
# Install mm onto PATH as ~/bin/mm, pointed at this clone.
set -e
ROOT="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
mkdir -p "$HOME/bin"
cat > "$HOME/bin/mm" << EOF
#!/usr/bin/env python3
import sys
sys.path.insert(0, "$ROOT")
from mm.cli import main
if __name__ == "__main__":
    main()
EOF
chmod +x "$HOME/bin/mm"
echo "installed $HOME/bin/mm -> $ROOT"
echo "next: mm init   (if you don't have ~/.mm/mm.toml yet)"
