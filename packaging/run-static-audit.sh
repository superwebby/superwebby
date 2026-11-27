#!/bin/bash
# Run the build-time static audit and write superwebby/data/static_audit.json.
# Tools: bandit (Python security lint on our source) and pip-audit (known CVEs
# in the Python packages the binary is built from). Results are written as-is.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"
OUT="$ROOT/superwebby/data/static_audit.json"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
"$PY" -m bandit -r "$ROOT/superwebby" -f json -o "$TMP/bandit.json" -q >/dev/null 2>"$TMP/bandit.err"
echo "bandit exit $?"
"$PY" -m pip freeze --exclude-editable 2>/dev/null | grep -iE '^(pyqt6|pyqt6-qt6|pyqt6-webengine|pyqt6-webengine-qt6|pyqt6-sip|pyinstaller|pyinstaller-hooks-contrib|altgraph|packaging|setuptools)==' > "$TMP/req.txt"
"$PY" -m pip_audit -r "$TMP/req.txt" --no-deps --disable-pip -f json -o "$TMP/pipaudit.json" >/dev/null 2>"$TMP/pipaudit.err"
echo "pip-audit exit $?"
"$PY" - "$TMP" "$OUT" "$ROOT" << 'PYEOF'
import datetime, json, sys, os
tmp, out, root = sys.argv[1:4]
tools = []
try:
    b = json.load(open(os.path.join(tmp, "bandit.json")))
    res = b.get("results", [])
    sev = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    findings = []
    for r in res:
        sev[r["issue_severity"]] = sev.get(r["issue_severity"], 0) + 1
        findings.append(f'{r["issue_severity"]}/{r["issue_confidence"]} {r["test_id"]} '
                        f'{os.path.relpath(r["filename"], root)}:{r["line_number"]} {r["issue_text"]}')
    loc = b.get("metrics", {}).get("_totals", {}).get("loc", 0)
    status = "FAIL" if sev.get("HIGH") else ("WARN" if res else "PASS")
    tools.append({"name": "bandit (Python security lint)", "status": status,
                  "summary": f"{len(res)} finding(s) in {loc} lines: {sev['HIGH']} high, {sev['MEDIUM']} medium, {sev['LOW']} low.",
                  "findings": findings})
except Exception as e:
    tools.append({"name": "bandit", "status": "WARN", "summary": f"bandit did not run: {e}; "
                  + open(os.path.join(tmp, "bandit.err")).read()[-300:], "findings": []})
try:
    p = json.load(open(os.path.join(tmp, "pipaudit.json")))
    deps = p.get("dependencies", [])
    vulns = [(d["name"], d.get("version"), v["id"], ",".join(v.get("fix_versions") or []) or "no fix")
             for d in deps for v in d.get("vulns", [])]
    skipped = [d["name"] for d in deps if d.get("skip_reason")]
    findings = [f"{n} {ver}: {vid} (fixed in {fx})" for n, ver, vid, fx in vulns]
    findings += [f"skipped {s}" for s in skipped]
    status = "FAIL" if vulns else ("WARN" if skipped else "PASS")
    tools.append({"name": "pip-audit (known CVEs in Python deps)", "status": status,
                  "summary": f"{len(deps)} package(s) checked ({', '.join(d['name'] + ' ' + str(d.get('version')) for d in deps)}); {len(vulns)} known vulnerability(ies).",
                  "findings": findings})
except Exception as e:
    tools.append({"name": "pip-audit", "status": "WARN", "summary": f"pip-audit did not run: {e}; "
                  + open(os.path.join(tmp, "pipaudit.err")).read()[-300:], "findings": []})
order = {"PASS": 0, "INFO": 0, "WARN": 1, "FAIL": 2}
worst = max((t["status"] for t in tools), key=lambda s: order.get(s, 1))
summary = "; ".join(f'{t["name"].split(" ")[0]}: {t["status"]}' for t in tools)
note = ("pip-audit covers the PyPI wheels used for the AUR -bin binary; the Flatpak uses PyQt/Qt from "
        "com.riverbankcomputing.PyQt.BaseApp, whose engine version is shown in the runtime check.")
json.dump({"status": worst, "summary": summary + ". " + note,
           "generated": "Generated " + datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
           "tools": tools}, open(out, "w"), indent=2)
print(json.dumps(json.load(open(out)), indent=2))
PYEOF
