#!/usr/bin/env python3
"""Bake favorite sites into a personalized Superwebby build.

    packaging/bake-favorites.py music.youtube.com docs.google.com
    packaging/bake-favorites.py --clear

Writes superwebby/data/favorites.json. A fresh profile (no
~/.config/superwebby/settings.json yet) starts with these favorites pinned,
with any built-in site fixes already applied. Users can change them later in
superwebby://settings; nothing asks them on startup.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from superwebby.settings import Settings  # noqa: E402

out = ROOT / "superwebby" / "data" / "favorites.json"
args = sys.argv[1:]
if args == ["--clear"]:
    out.unlink(missing_ok=True)
    print("removed", out)
    raise SystemExit(0)
if not args:
    print(__doc__)
    raise SystemExit(2)
settings = Settings()
for site in args:
    if settings.add_favorite(site) is None:
        print("not a site:", site, file=sys.stderr)
        raise SystemExit(1)
payload = {"favorites": [vars(f) for f in settings.favorites], "high_speed": False}
out.write_text(json.dumps(payload, indent=2) + "\n")
print("wrote", out, "->", ", ".join(f.host for f in settings.favorites))
