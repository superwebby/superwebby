#!/usr/bin/env python3
"""Headless smoke test for a built Superwebby binary: --version, --self-test and --audit (JSON reports).

Usage: ci-smoke.py <path-to-executable> <label>
Writes smoke-<label>.json and exits non-zero if the self-test fails or the audit is malformed.
"""
from __future__ import annotations

import json
import os
import subprocess  # nosec B404 - CI script, fixed argv
import sys
import tempfile
import time
from pathlib import Path


def run(exe: str, *args: str, timeout: int = 300) -> tuple[int, str, float]:
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    t0 = time.time()
    proc = subprocess.run([exe, *args], env=env, capture_output=True, text=True,  # nosec B603
                          timeout=timeout, errors="replace")
    return proc.returncode, (proc.stdout or "") + (proc.stderr or ""), time.time() - t0


def main() -> int:
    exe, label = sys.argv[1], sys.argv[2]
    tmp = Path(tempfile.mkdtemp(prefix="sw-smoke-"))
    summary: dict = {"label": label, "exe": exe}
    ok = True

    code, out, secs = run(exe, "--version", timeout=120)
    summary["version"] = {"exit": code, "seconds": round(secs, 1), "output": out.strip()[-200:]}
    print(f"--version exit={code} ({secs:.1f}s): {out.strip()[-200:]}")

    st_path = tmp / "selftest.json"
    code, out, secs = run(exe, "--self-test", "--report", str(st_path),
                          "--screenshot", str(tmp / f"selftest-{label}.png"))
    print(f"--self-test exit={code} ({secs:.1f}s)\n{out[-3000:]}")
    selftest = json.loads(st_path.read_text(encoding="utf-8")) if st_path.is_file() else None
    summary["selftest"] = {"exit": code, "seconds": round(secs, 1), "report": selftest}
    if code != 0 or not selftest or not selftest.get("ok"):
        ok = False

    au_path = tmp / "audit.json"
    code, out, secs = run(exe, "--audit", "--report", str(au_path))
    audit = json.loads(au_path.read_text(encoding="utf-8")) if au_path.is_file() else None
    summary["audit"] = {"exit": code, "seconds": round(secs, 1),
                        "counts": audit and audit.get("counts"),
                        "checks": audit and [(c["name"], c["status"], c.get("detail", "")) for c in audit["checks"]]}
    print(f"--audit exit={code} ({secs:.1f}s) counts={audit and audit.get('counts')}")
    if audit:
        for c in audit["checks"]:
            print(f"  {c['status']:5} {c['name']}: {c.get('detail', '')}")
    if code != 0 or not audit or len(audit.get("checks", [])) < 8:
        ok = False

    summary["ok"] = ok
    Path(f"smoke-{label}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    shot = tmp / f"selftest-{label}.png"
    if shot.is_file():
        Path(shot.name).write_bytes(shot.read_bytes())
    print("SMOKE", "PASS" if ok else "FAIL", label)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
