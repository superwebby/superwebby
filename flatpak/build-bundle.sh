#!/bin/sh
# Build Superwebby as a user Flatpak and export a single-file bundle.
set -eu
cd "$(dirname "$0")"
MANIFEST=io.github.superwebby.Superwebby.yaml
APP_ID=io.github.superwebby.Superwebby
BUNDLE=superwebby-1.0.0.flatpak
WORK=builder-work
REPO=ostree-repo

flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo

flatpak-builder \
  --user \
  --force-clean \
  --ccache \
  --install-deps-from=flathub \
  --repo="$REPO" \
  "$WORK" \
  "$MANIFEST"

flatpak build-bundle "$REPO" "$BUNDLE" "$APP_ID"
ls -lh "$BUNDLE"
sha256sum "$BUNDLE"
