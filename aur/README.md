# Superwebby AUR packages

This archive is AUR-style packaging for Superwebby 1.0.0.

## Packages

- `superwebby/` — build from the reproducible source tarball.
  Depends on `python`, `python-pyqt6`, `python-pyqt6-webengine`, `qt6-webengine`.
- `superwebby-bin/` — install a prebuilt, stripped PyInstaller onedir tree
  into `/opt/superwebby` with a `/usr/bin/superwebby` symlink.

Both directories already contain their source tarballs, so you can run
`makepkg -si` offline on an Arch system.

```bash
cd superwebby && makepkg -si
# or
cd superwebby-bin && makepkg -si
```

The source is reproducible (`packaging/build-source-tarball.sh` uses
sorted names, numeric owners, and a fixed mtime). Rebuild the binary
tarball with `packaging/build-bin.sh` from the source tree.

This environment is Debian, not Arch, so PKGBUILDs were syntax-checked
with `bash -n` and their sha256sums were verified against the files.
Use `namcap` and `makepkg` on Arch for the official package check.
