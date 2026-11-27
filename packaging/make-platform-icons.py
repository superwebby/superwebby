#!/usr/bin/env python3
"""Generate assets/superwebby.ico (Windows) and assets/superwebby.icns (macOS) from the PNG logo set."""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
src = Image.open(ASSETS / "superwebby-512.png").convert("RGBA")
if src.size != (1024, 1024):
    big = src.resize((1024, 1024), Image.LANCZOS)
else:
    big = src

src.save(ASSETS / "superwebby.ico", format="ICO",
         sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
big.save(ASSETS / "superwebby.icns", format="ICNS")
print("wrote", ASSETS / "superwebby.ico", "and", ASSETS / "superwebby.icns")
