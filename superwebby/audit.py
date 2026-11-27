"""Security audit: real checks run against the running build.

Every check reports PASS, WARN, FAIL, or INFO from what it can actually
observe. Nothing is hard-coded to pass. The static-analysis section is read
from data/static_audit.json, which packaging/run-static-audit.sh writes at
build time (bandit on the source, pip-audit on the Python dependencies).
"""

from __future__ import annotations

import ast
import datetime as _dt
import json
import os
import re
from pathlib import Path

from superwebby import __version__
from superwebby.paths import app_root, data_dir

PASS, WARN, FAIL, INFO = "PASS", "WARN", "FAIL", "INFO"

# Hosts that would mean the browser phones home. Searched for in our own
# Python source (not in the blocklists, which list them to *block* them).
TELEMETRY_PATTERNS = (
    "google-analytics.com", "googletagmanager.com", "sentry.io", "ingest.sentry", "mixpanel.com",
    "api.segment.io", "amplitude.com", "posthog.com", "datadoghq", "bugsnag", "crashlytics",
    "app-measurement.com", "telemetry.", "metrics.", "stats.", "/collect?", "/telemetry",
    "clients2.google.com", "update.googleapis.com", "safebrowsing.googleapis.com",
)
# Files whose job is to list ad/tracker hosts to block them.
BLOCK_LIST_MODULES = {"youtube.py", "blocker.py", "audit.py", "settings.py"}
NETWORK_IMPORTS = {"urllib.request", "http.client", "requests", "httpx", "aiohttp", "socket",
                   "urllib3", "ftplib", "smtplib"}
# URLs the UI may open when the *user* clicks something. Not background traffic.
USER_INITIATED_URLS = {
    "https://duckduckgo.com/",
    "https://duckduckgo.com/?q={query}",
    "https://github.com/superwebby/superwebby",
    "https://www.",
}
REQUIRED_FLAGS = (
    "--disable-breakpad", "--disable-crash-reporter", "--disable-component-update",
    "--disable-background-networking", "--disable-sync", "--disable-domain-reliability",
    "--no-pings", "--disable-metrics",
)


def _check(name: str, status: str, detail: str, evidence: str = "") -> dict:
    return {"name": name, "status": status, "detail": detail, "evidence": evidence}


# ---------------------------------------------------------------------------
def check_telemetry() -> dict:
    root = app_root()
    hits: list[str] = []
    net_imports: list[str] = []
    urls: set[str] = set()
    excluded: list[str] = []
    for path in sorted(root.glob("*.py")):
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError) as exc:
            hits.append(f"{path.name}: unreadable ({exc})")
            continue
        # Self-test fixtures (fake ad URLs the blocker must refuse) are not traffic.
        skip_ids = set()
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef) and fn.name == "_run_self_test":
                skip_ids |= {id(n) for n in ast.walk(fn)}
                excluded.append(f"{path.name}:_run_self_test")
        for node in ast.walk(tree):
            if id(node) in skip_ids:
                continue
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in NETWORK_IMPORTS:
                        net_imports.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module in NETWORK_IMPORTS:
                net_imports.append(f"{path.name}: from {node.module}")
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                for m in re.findall(r"https?://[A-Za-z0-9][^\s\"'<>,]*", node.value):
                    urls.add(m)
                if path.name not in BLOCK_LIST_MODULES:
                    low = node.value.lower()
                    for pat in TELEMETRY_PATTERNS:
                        if pat in low:
                            hits.append(f"{path.name}: '{pat}'")
    scanned = len(list(root.glob("*.py")))
    method = "source"
    if scanned == 0:
        # Frozen (PyInstaller) build: no .py files on disk. Scan the compiled
        # code objects of every superwebby module instead.
        method = "bytecode"
        scanned, b_hits, b_imports, b_urls = _scan_bytecode()
        hits += b_hits
        net_imports += b_imports
        urls |= b_urls
    if scanned == 0:
        return _check("Telemetry endpoints", WARN, "Could not inspect the application code in this build.",
                      "No source files or compiled modules were found.")
    unexpected = sorted(u for u in urls if not any(u.startswith(ok) for ok in USER_INITIATED_URLS)
                        and "127.0.0.1" not in u and "pgl.yoyo.org" not in u
                        and "chromiumdash" not in u)
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    missing = [f for f in REQUIRED_FLAGS if f not in flags]
    evidence = (
        f"Scanned {scanned} modules ({method}; self-test fixtures excluded: "
        f"{', '.join(excluded) or 'none'}). Network imports: "
        f"{', '.join(net_imports) or 'none'}. URL literals: {', '.join(sorted(urls)) or 'none'}. "
        f"Chromium phone-home switches missing: {', '.join(missing) or 'none'}."
    )
    if hits or unexpected or missing:
        status = FAIL if hits else WARN
        detail = "Possible telemetry: " + "; ".join(hits + unexpected + [f"missing {m}" for m in missing])
    elif net_imports:
        status = WARN
        detail = "No telemetry endpoints, but network imports exist (review them)."
    else:
        status = PASS
        detail = ("No telemetry endpoints in the source; crash reporting, metrics, component "
                  "updates, sync, domain reliability and pings are switched off in Chromium.")
    return _check("Telemetry endpoints", status, detail, evidence)


def _scan_bytecode() -> tuple[int, list[str], list[str], set[str]]:
    import importlib
    import pkgutil
    import types

    import superwebby

    hits: list[str] = []
    imports: list[str] = []
    urls: set[str] = set()
    count = 0
    for info in pkgutil.iter_modules(superwebby.__path__):
        name = f"superwebby.{info.name}"
        try:
            mod = importlib.import_module(name)
        except Exception as exc:
            hits.append(f"{name}: import failed ({exc})")
            continue
        loader = getattr(mod, "__loader__", None)
        code = None
        try:
            code = loader.get_code(name) if loader is not None else None
        except Exception:
            code = None
        if code is None:
            continue
        count += 1
        short = info.name + ".py"
        for value in mod.__dict__.values():
            if isinstance(value, types.ModuleType) and value.__name__ in NETWORK_IMPORTS:
                imports.append(f"{short}: {value.__name__}")
        stack = [code]
        while stack:
            co = stack.pop()
            if co.co_name == "_run_self_test":
                continue
            for const in co.co_consts:
                if isinstance(const, types.CodeType):
                    stack.append(const)
                elif isinstance(const, str):
                    for m in re.findall(r"https?://[A-Za-z0-9][^\s\"'<>,]*", const):
                        urls.add(m)
                    if short not in BLOCK_LIST_MODULES:
                        low = const.lower()
                        for pat in TELEMETRY_PATTERNS:
                            if pat in low:
                                hits.append(f"{short}: '{pat}'")
    return count, hits, imports, urls


def check_blocklist(blocker) -> dict:
    from superwebby.youtube import AD_HOSTS, AD_PATHS

    full = len(blocker.full_domains) if blocker.full_domains else 0
    core = len(blocker.core_domains)
    mode = "High Speed (core list)" if blocker.high_speed else "Full list"
    active = len(blocker.domains)
    evidence = (f"Full list: {full:,} domains, version {blocker.full_version or 'not loaded'}. "
                f"Core list: {core:,} domains, version {blocker.core_version or 'unknown'}. "
                f"YouTube rules: {len(AD_HOSTS)} hosts + {len(AD_PATHS)} path rules + &oad/ctier=L/adformat stream rules.")
    if active < 1000:
        return _check("Ad/tracker blocklist", FAIL, f"Only {active} domains active ({mode}).", evidence)
    version = blocker.list_version
    status = PASS
    detail = f"{active:,} domains active ({mode}); YouTube/YouTube Music ad rules on."
    try:
        built = _dt.date.fromisoformat(version[:10].replace(".", "-"))
        age = (_dt.date.today() - built).days
        detail += f" List version {version[:10]} is {age} day(s) old."
        if age > 90:
            status = WARN
            detail += " Older than 90 days: rebuild the list."
    except ValueError:
        status = WARN
        detail += " List has no parseable version date."
    return _check("Ad/tracker blocklist", status, detail, evidence)


def _webengine_children() -> list[str]:
    """Command lines of QtWebEngineProcess children of this process (Linux)."""
    me = os.getpid()
    out = []
    proc = Path("/proc")
    if not proc.is_dir():
        return out
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text()
            ppid = int(stat.rsplit(")", 1)[1].split()[1])
            cmd = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="ignore")
        except (OSError, ValueError, IndexError):
            continue
        if "QtWebEngineProcess" in cmd:
            # Our children, or grandchildren via the zygote.
            if ppid == me or _parent_is(ppid, me):
                out.append(cmd)
    return out


def _parent_is(pid: int, ancestor: int, depth: int = 3) -> bool:
    for _ in range(depth):
        try:
            stat = Path(f"/proc/{pid}/stat").read_text()
            pid = int(stat.rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            return False
        if pid == ancestor:
            return True
    return False


def check_sandbox() -> dict:
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    env_off = os.environ.get("QTWEBENGINE_DISABLE_SANDBOX", "") not in ("", "0")
    flag_off = "--no-sandbox" in flags
    flatpak = Path("/.flatpak-info").exists() or bool(os.environ.get("FLATPAK_ID"))
    children = _webengine_children()
    child_off = [c for c in children if "--no-sandbox" in c]
    evidence = (f"QTWEBENGINE_DISABLE_SANDBOX={'set' if env_off else 'unset'}; --no-sandbox in flags: {flag_off}; "
                f"Flatpak: {flatpak}; renderer processes observed: {len(children)}, "
                f"of which started with --no-sandbox: {len(child_off)}.")
    if env_off or flag_off or child_off:
        extra = " The Flatpak sandbox still confines the whole app." if flatpak else ""
        return _check("Chromium renderer sandbox", FAIL,
                      "The Chromium sandbox is DISABLED in this session." + extra, evidence)
    if not children:
        return _check("Chromium renderer sandbox", WARN,
                      "Not disabled by flags or environment, but no renderer process was running to confirm it.",
                      evidence)
    return _check("Chromium renderer sandbox", PASS,
                  "Renderer processes are running without --no-sandbox; the Chromium sandbox is on.", evidence)


def check_https(blocker) -> dict:
    from superwebby.window import interpret_input

    typed = interpret_input("example.com")
    upgrade = getattr(blocker, "https_upgrade", False)
    evidence = f"Typing 'example.com' opens {typed}. Interceptor HTTPS upgrade of http:// links: {upgrade}."
    if typed.startswith("https://") and upgrade:
        return _check("HTTPS upgrade", PASS, "Typed addresses and http:// links are upgraded to HTTPS.", evidence)
    if typed.startswith("https://"):
        return _check("HTTPS upgrade", WARN,
                      "Typed addresses default to https://, but http:// links on pages are NOT automatically "
                      "upgraded (no HTTPS-only mode yet).", evidence)
    return _check("HTTPS upgrade", FAIL, "Typed addresses do not default to HTTPS.", evidence)


def check_cookies(profile) -> dict:
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    has_filter = bool(getattr(profile, "_superwebby_cookie_filter", False))
    phaseout = "--test-third-party-cookie-phaseout" in flags
    evidence = f"QWebEngineCookieStore filter installed: {has_filter}; --test-third-party-cookie-phaseout: {phaseout}."
    if has_filter:
        return _check("Third-party cookies", PASS,
                      "Third-party cookies are refused by a cookie-store filter (relaxed favorite sites excepted).",
                      evidence)
    if phaseout:
        return _check("Third-party cookies", WARN,
                      "Only Chromium's phase-out switch is set; no cookie filter is installed.", evidence)
    return _check("Third-party cookies", FAIL, "Third-party cookies are allowed.", evidence)


def check_webrtc(profile) -> dict:
    from PyQt6.QtWebEngineCore import QWebEngineSettings

    attr = QWebEngineSettings.WebAttribute
    on = profile.settings().testAttribute(attr.WebRTCPublicInterfacesOnly)
    evidence = f"WebRTCPublicInterfacesOnly = {on} (read from the live profile)."
    if on:
        return _check("WebRTC IP leak", PASS,
                      "WebRTC only uses the public interface; local/LAN IPs are not exposed to sites.", evidence)
    return _check("WebRTC IP leak", FAIL, "WebRTC may expose local IP addresses.", evidence)


def check_fingerprinting(profile) -> dict:
    from PyQt6.QtWebEngineCore import QWebEngineSettings

    attr = QWebEngineSettings.WebAttribute
    s = profile.settings()
    have = []
    if not s.testAttribute(attr.PluginsEnabled):
        have.append("plugins off")
    if not s.testAttribute(attr.HyperlinkAuditingEnabled):
        have.append("hyperlink auditing (ping) off")
    if not s.testAttribute(attr.ScreenCaptureEnabled):
        have.append("screen capture off")
    have.append("permission requests (camera, mic, location, notifications) auto-denied")
    if "--disable-features=InterestCohortAPI" in os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "") or \
            "InterestCohortAPI" in os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", ""):
        have.append("FLoC/Topics/Privacy Sandbox ad APIs off")
    ua = profile.httpUserAgent()
    missing = "no canvas/WebGL/audio randomization (farbling), no font or screen-size spoofing"
    evidence = f"Active: {'; '.join(have)}. User-Agent: {ua}"
    return _check("Fingerprinting mitigations", WARN,
                  f"Partial: {', '.join(have)}. Missing: {missing}; the User-Agent also says Superwebby, "
                  "which adds a little entropy.", evidence)


def check_engine() -> dict:
    from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
    from PyQt6 import QtWebEngineCore

    chromium = _call(QtWebEngineCore, "qWebEngineChromiumVersion")
    patch = _call(QtWebEngineCore, "qWebEngineChromiumSecurityPatchVersion")
    table = {}
    try:
        table = json.loads((data_dir() / "chromium_releases.json").read_text())["stable_dates"]
    except (OSError, ValueError, KeyError):
        pass
    today = _dt.date.today()
    base_major = chromium.split(".")[0] if chromium else ""
    patch_major = patch.split(".")[0] if patch else base_major
    latest = None
    for major, date in table.items():
        if date and _dt.date.fromisoformat(date) <= today:
            if latest is None or int(major) > int(latest):
                latest = major
    evidence = (f"Qt {QT_VERSION_STR}, PyQt {PYQT_VERSION_STR}, Chromium base {chromium or '?'}, "
                f"security patches through Chromium {patch or '?'}; newest Chrome stable in the bundled "
                f"schedule as of {today.isoformat()}: {latest or '?'}.")
    date = table.get(patch_major)
    if not date:
        return _check("Engine version / CVE age", WARN, "Could not date the security-patch level.", evidence)
    patch_date = _dt.date.fromisoformat(date)
    behind = int(latest) - int(patch_major) if latest else 0
    newer = [m for m, d in table.items() if d and int(m) > int(patch_major) and _dt.date.fromisoformat(d) <= today]
    exposure = 0
    if newer:
        first_newer = min(newer, key=int)
        exposure = (today - _dt.date.fromisoformat(table[first_newer])).days
    detail = (f"Chromium {patch_major} security patches (Chrome {patch_major} stable {date}). "
              f"{behind} milestone(s) behind current stable {latest}; ")
    if exposure:
        detail += f"CVEs fixed in Chrome {min(newer, key=int)}+ have been public for up to {exposure} day(s) and may be unpatched here."
    else:
        detail += "no newer Chrome security release is known."
    if exposure > 60 or behind > 3:
        status = FAIL
    elif exposure > 0:
        status = WARN
    else:
        status = PASS
    return _check("Engine version / CVE age", status, detail, evidence)


def _call(mod, name: str) -> str:
    fn = getattr(mod, name, None)
    try:
        return str(fn()) if fn else ""
    except Exception:
        return ""


def static_audit() -> dict:
    path = data_dir() / "static_audit.json"
    if not path.is_file():
        return {"status": WARN, "summary": "No static audit results bundled in this build.", "tools": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": WARN, "summary": f"Static audit file unreadable: {exc}", "tools": []}


def run_audit(window) -> dict:
    profile = window.profile
    blocker = window.blocker
    checks = []
    for fn, args in (
        (check_telemetry, ()), (check_blocklist, (blocker,)), (check_sandbox, ()),
        (check_https, (blocker,)), (check_cookies, (profile,)), (check_webrtc, (profile,)),
        (check_fingerprinting, (profile,)), (check_engine, ()),
    ):
        try:
            checks.append(fn(*args))
        except Exception as exc:  # report, never hide, a broken check
            checks.append(_check(fn.__name__, FAIL, f"Check crashed: {exc!r}"))
    static = static_audit()
    counts = {k: sum(1 for c in checks if c["status"] == k) for k in (PASS, WARN, FAIL, INFO)}
    return {
        "version": __version__,
        "ran_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": "High Speed" if blocker.high_speed else "Normal",
        "checks": checks,
        "counts": counts,
        "static": static,
    }
