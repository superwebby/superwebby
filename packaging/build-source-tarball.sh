#!/bin/bash
# Build a reproducible source tarball for the superwebby PKGBUILD.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
NAME="superwebby-${VERSION}"
OUT="${1:-$ROOT/packaging/superwebby-${VERSION}.tar.gz}"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

DEST="$STAGE/$NAME"
mkdir -p "$DEST"

copy_tree() {
  local src="$1" dest="$2"
  mkdir -p "$dest"
  tar -C "$src" --exclude '__pycache__' --exclude '*.pyc' --exclude '*.pyo' \
      --exclude '.venv' --exclude '.git' --exclude 'out' --exclude '*.tar.gz' \
      --exclude '*.spec' -cf - . | tar -C "$dest" -xf -
}
cp -a "$ROOT/README.md" "$ROOT/LICENSE" "$ROOT/VERSION" "$ROOT/pyproject.toml" "$ROOT/superwebby-run" "$DEST/"
copy_tree "$ROOT/superwebby" "$DEST/superwebby"
copy_tree "$ROOT/assets" "$DEST/assets"
mkdir -p "$DEST/packaging"
cp -a "$ROOT/packaging/superwebby-launcher" "$ROOT/packaging/build-source-tarball.sh" "$ROOT/packaging/build-bin.sh" "$DEST/packaging/"
chmod +x "$DEST/superwebby-run" "$DEST/packaging/"*

mkdir -p "$(dirname "$OUT")"
tar --sort=name --owner=0 --group=0 --numeric-owner \
  --mtime='2026-11-24T00:00:00' \
  --mode='u+rw,go+r-w,a+X' \
  -C "$STAGE" -czf "$OUT" "$NAME"

echo "Wrote $OUT"
sha256sum "$OUT"
