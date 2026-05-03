#!/usr/bin/env bash
# Snapshot portable Component 3 frontend sources into migration/component3-frontend/
# so you can `git rm -r frontend`, merge origin/main, then copy them back.
#
# Usage (from repo root):
#   chmod +x scripts/snapshot-component3-frontend.sh
#   ./scripts/snapshot-component3-frontend.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/frontend"
DST="$ROOT/migration/component3-frontend"

if [[ ! -d "$SRC" ]]; then
  echo "error: $SRC does not exist — nothing to snapshot." >&2
  exit 1
fi

echo "[snapshot] Writing portable sources to $DST"

rm -rf "$DST"
mkdir -p "$DST/src" "$DST/_merge-hints"

# --- Portable: feature modules, shared lib, components ---
for rel in features lib components; do
  if [[ -d "$SRC/src/$rel" ]]; then
    mkdir -p "$DST/src/$rel"
    cp -R "$SRC/src/$rel/." "$DST/src/$rel/"
    echo "  + src/$rel/"
  fi
done

if [[ -f "$SRC/src/vite-env.d.ts" ]]; then
  cp "$SRC/src/vite-env.d.ts" "$DST/src/vite-env.d.ts"
  echo "  + src/vite-env.d.ts"
fi

# --- Merge hints (reference only; do not blindly overwrite main) ---
for f in App.tsx main.tsx index.css; do
  if [[ -f "$SRC/src/$f" ]]; then
    cp "$SRC/src/$f" "$DST/_merge-hints/$f"
    echo "  + _merge-hints/$f"
  fi
done

for f in vite.config.ts components.json; do
  if [[ -f "$SRC/$f" ]]; then
    cp "$SRC/$f" "$DST/_merge-hints/$f"
    echo "  + _merge-hints/$f"
  fi
done

echo "[snapshot] Done."
echo ""
echo "Next:  git add migration/component3-frontend && git commit -m 'chore: snapshot component3 portable frontend sources'"
echo "Then:  git rm -r frontend && git commit -m 'chore: remove local frontend scaffold (restore from main)'"
echo "Then:  git fetch origin && git merge origin/main"
echo "Then:  copy snapshot back into frontend/src — see migration/component3-frontend/README.md"
