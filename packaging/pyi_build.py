#!/usr/bin/env python3
"""Cross-platform PyInstaller build for Windows and macOS (Linux uses build-bin.sh).

Windows: dist/superwebby/superwebby.exe (onedir, windowed, .ico icon)
macOS:   dist/Superwebby.app (onedir .app bundle, windowed, .icns icon, ad-hoc signed)
"""
from __future__ import annotations

import os
import subprocess  # nosec B404 - build script
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = (ROOT / "VERSION").read_text().strip()
SEP = os.pathsep


def main() -> int:
    work = ROOT / "packaging" / "out" / "pyi"
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onedir", "--windowed", "--noupx",
        "--paths", str(ROOT),
        "--add-data", f"{ROOT / 'superwebby' / 'data'}{SEP}superwebby/data",
        "--add-data", f"{ROOT / 'assets' / 'superwebby.png'}{SEP}assets",
        "--hidden-import", "PyQt6.sip",
        "--hidden-import", "PyQt6.QtCore",
        "--hidden-import", "PyQt6.QtGui",
        "--hidden-import", "PyQt6.QtWidgets",
        "--hidden-import", "PyQt6.QtNetwork",
        "--hidden-import", "PyQt6.QtWebEngineCore",
        "--hidden-import", "PyQt6.QtWebEngineWidgets",
        "--hidden-import", "PyQt6.QtWebChannel",
        "--workpath", str(work / "work"),
        "--specpath", str(work),
        "--distpath", str(ROOT / "dist"),
    ]
    if sys.platform.startswith("win"):
        args += ["--name", "superwebby", "--icon", str(ROOT / "assets" / "superwebby.ico")]
    elif sys.platform == "darwin":
        args += [
            "--name", "Superwebby",
            "--icon", str(ROOT / "assets" / "superwebby.icns"),
            "--osx-bundle-identifier", "io.github.superwebby.Superwebby",
        ]
    else:
        print("Use packaging/build-bin.sh on Linux", file=sys.stderr)
        return 2
    args.append(str(ROOT / "superwebby-run"))
    print(" ".join(args), flush=True)
    subprocess.run(args, check=True, cwd=ROOT)  # nosec B603

    if sys.platform == "darwin":
        app = ROOT / "dist" / "Superwebby.app"
        plist = app / "Contents" / "Info.plist"
        import plistlib

        with plist.open("rb") as fh:
            info = plistlib.load(fh)
        info.update({
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "CFBundleDisplayName": "Superwebby",
            "LSMinimumSystemVersion": "14.0",
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.productivity",
            "NSHumanReadableCopyright": "GPL-3.0-or-later. https://github.com/superwebby/superwebby",
            "CFBundleURLTypes": [{"CFBundleURLName": "Web site URL", "CFBundleURLSchemes": ["http", "https"]}],
        })
        with plist.open("wb") as fh:
            plistlib.dump(info, fh)
        # Info.plist changed, so re-sign the whole bundle ad hoc (no Apple Developer ID).
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)  # nosec B603 B607
        subprocess.run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)], check=True)  # nosec B603 B607
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
