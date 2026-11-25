#!/bin/bash
# Build a stripped PyInstaller onedir tree and wrap it in a reproducible tarball.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
OUTDIR="${1:-$ROOT/packaging/out}"
NAME="superwebby-${VERSION}-x86_64"
DEST="$OUTDIR/$NAME"
TARBALL="${2:-$ROOT/packaging/${NAME}.tar.gz}"

python3 -m pip install --user --break-system-packages 'pyinstaller>=6,<7' >/tmp/pyinstaller-install.log

WORKDIR="$OUTDIR/pyi-build"
rm -rf "$WORKDIR" "$DEST"
mkdir -p "$WORKDIR" "$DEST"

# PyInstaller must run from the project root so imports resolve.
cd "$ROOT"
python3 -m PyInstaller \
  --noconfirm --clean --onedir --strip --name superwebby \
  --noupx \
  --paths "$ROOT" \
  --add-data "$ROOT/superwebby/data:superwebby/data" \
  --add-data "$ROOT/assets/superwebby.png:assets" \
  --add-data "$ROOT/assets/superwebby.desktop:assets" \
  --hidden-import PyQt6.sip \
  --hidden-import PyQt6.QtCore \
  --hidden-import PyQt6.QtGui \
  --hidden-import PyQt6.QtWidgets \
  --hidden-import PyQt6.QtWebEngineCore \
  --hidden-import PyQt6.QtWebEngineWidgets \
  --hidden-import PyQt6.QtWebChannel \
  --collect-all PyQt6 \
  --workpath "$WORKDIR/work" \
  --specpath "$WORKDIR" \
  --distpath "$WORKDIR/dist" \
  "$ROOT/superwebby-run"

# PyInstaller 6 uses dist/superwebby/ with the binary and _internal/.
cp -a "$WORKDIR/dist/superwebby" "$DEST/superwebby-app"
# Convenience wrapper name
cat > "$DEST/README.txt" << TXT
Superwebby ${VERSION} prebuilt x86_64 tree (PyInstaller onedir, stripped).

Run ./superwebby-app/superwebby
This archive is produced by packaging/build-bin.sh from the public source.
TXT

tar --sort=name --owner=0 --group=0 --numeric-owner \
  --mtime='2026-11-24T00:00:00' \
  --mode='u+rw,go+r-w,a+X' \
  -C "$OUTDIR" -czf "$TARBALL" "$NAME"

echo "Wrote $TARBALL"
sha256sum "$TARBALL"
du -sh "$DEST" "$TARBALL"
