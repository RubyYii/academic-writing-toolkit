#!/usr/bin/env bash
# scripts/setup-export-backend.sh — give /export a conversion backend.
#
# The converter needs pypandoc (the binding, not the `pandoc` binary) OR
# python-docx AND markdown. A bare `pip install` is refused as
# externally-managed by any PEP 668 interpreter, which is the default on
# Homebrew Python and on current Debian and Ubuntu, so this creates a project
# virtual environment — the location doctor, `awt verify` and the export tool
# all look in. Idempotent: an interpreter that can already convert is left alone.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONVERTER="$ROOT/.claude/skills/export/scripts/convert_to_docx.py"
REQUIREMENTS="$ROOT/.claude/skills/export/scripts/requirements.txt"

for candidate in "${AWT_PYTHON:-}" "$ROOT/.venv/bin/python" "$ROOT/.venv/Scripts/python.exe" python3; do
    [ -n "$candidate" ] || continue
    if command -v "$candidate" >/dev/null 2>&1 || [ -x "$candidate" ]; then
        if "$candidate" "$CONVERTER" --check >/dev/null 2>&1; then
            ok "export backend already available ($candidate)"
            exit 0
        fi
    fi
done

command -v python3 >/dev/null 2>&1 || die "python3 not found; install it, then re-run make setup"
printf "  creating %s and installing the export backend...\n" "$ROOT/.venv"
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" install --quiet --upgrade pip
"$ROOT/.venv/bin/pip" install --quiet -r "$REQUIREMENTS"
"$ROOT/.venv/bin/python" "$CONVERTER" --check >/dev/null \
    || die "installed the requirements but the converter still reports no backend"
ok "export backend installed into .venv"
