#!/bin/sh
# Install mm onto PATH, pointed at this clone.
# macOS and Linux: ~/bin/mm and the mm(1) manual.
# Windows Git Bash: hands off to install.ps1, which installs %USERPROFILE%\bin\mm.cmd.
set -e
ROOT="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"

uname_s=$(uname -s 2>/dev/null || echo unknown)
case "$uname_s" in
  MINGW*|MSYS*|CYGWIN*)
    if ! command -v powershell.exe >/dev/null 2>&1; then
      echo "powershell.exe was not found. From Command Prompt or PowerShell, run: install.cmd" >&2
      exit 1
    fi
    win_ps1="$ROOT/install.ps1"
    if command -v cygpath >/dev/null 2>&1; then
      win_ps1=$(cygpath -w "$ROOT/install.ps1")
    fi
    exec powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$win_ps1"
    ;;
esac

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 was not found. Install Python 3.11+ and re-run ./install.sh" >&2
  exit 1
fi
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "Python 3.11+ is required. This machine has: $(python3 --version 2>&1)" >&2
  exit 1
fi

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
rm -f "$HOME/.local/share/man/man1/mm.1.gz" 2>/dev/null || true
echo "installed $HOME/bin/mm -> $ROOT"
echo "installed $HOME/.local/share/man/man1/mm.1"
echo "try:  man mm"
echo "next: mm add \"…\""
