"""Application entry point. Chromium flags are set before QApplication."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

from superwebby import __app_name__, __version__
from superwebby.paths import app_root, data_home, downloads_dir


CHROMIUM_FLAGS = [
    "--disable-breakpad",
    "--disable-crash-reporter",
    "--disable-component-update",
    "--disable-background-networking",
    "--disable-sync",
    "--disable-client-side-phishing-detection",
    "--disable-default-apps",
    "--disable-domain-reliability",
    "--disable-features=InterestCohortAPI,FederatedLearningOfCohorts,PrivacySandboxAdsAPIs,TranslateUI,MediaRouter,AutofillServerCommunication,OptimizationHints,NotificationTriggers",
    "--disable-hang-monitor",
    "--disable-speech-api",
    "--no-pings",
    "--no-first-run",
    "--no-default-browser-check",
    "--metrics-recording-only",  # combined with disable-metrics below; belt and suspenders
    "--disable-metrics",
    "--force-dark-mode",
    "--enable-features=WebContentsForceDark",
    "--test-third-party-cookie-phaseout",
    "--log-level=3",
]


def _prepare_environment(offscreen: bool = False) -> None:
    # Qt / Chromium telemetry and first-run surfaces stay off.
    os.environ.setdefault("QT_LOGGING_RULES", "qt.webenginecontext.info=false")
    os.environ.pop("QTWEBENGINE_REMOTE_DEBUGGING", None)
    flags = list(CHROMIUM_FLAGS)
    if offscreen or os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        flags.append("--disable-gpu")
    # Preserve any user-supplied flags, then ours.
    existing = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip()
    merged = (existing + " " + " ".join(flags)).strip()
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = merged
    # Do not phone home through Qt crash reports.
    os.environ.setdefault("QT_WEBENGINE_DISABLE_GPU_THREAD", "")


def _icon_path() -> Path:
    candidates: list[Path] = []
    # PyInstaller onedir
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidates.append(meipass / "assets" / "superwebby.png")
        candidates.append(Path(sys.executable).resolve().parent / "assets" / "superwebby.png")
    candidates.append(app_root().parent / "assets" / "superwebby.png")
    if not sys.platform.startswith("linux"):
        for path in candidates:
            if path.is_file():
                return path
        return candidates[0]
    flatpak_id = os.environ.get("FLATPAK_ID", "io.github.superwebby.Superwebby")
    icon_stems = (flatpak_id, "superwebby")
    prefixes = ["/app/share"]
    prefixes.extend(p for p in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":") if p)
    prefixes.append("/usr/share")
    seen_prefixes: set[str] = set()
    for prefix in prefixes:
        if prefix in seen_prefixes:
            continue
        seen_prefixes.add(prefix)
        base = Path(prefix)
        for stem in icon_stems:
            candidates.append(base / "icons" / "hicolor" / "256x256" / "apps" / f"{stem}.png")
            candidates.append(base / "icons" / "hicolor" / "scalable" / "apps" / f"{stem}.svg")
            candidates.append(base / "pixmaps" / f"{stem}.png")
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    for path in unique:
        if path.is_file():
            return path
    return unique[0]


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="superwebby",
        description="Superwebby — a painless, privacy-first desktop web browser.",
    )
    parser.add_argument("url", nargs="?", help="Optional URL or search to open at startup")
    parser.add_argument("--version", action="version", version=f"Superwebby {__version__}")
    parser.add_argument("--incognito", action="store_true", help="Private window, nothing written to disk")
    parser.add_argument("--self-test", action="store_true", help="Run a short headless/offscreen feature test and exit")
    parser.add_argument("--screenshot", metavar="PATH", help="After load, write a window screenshot to PATH")
    parser.add_argument("--offscreen", action="store_true", help="Use the offscreen Qt platform")
    parser.add_argument("--no-restore", action="store_true", help="Do not restore the previous session")
    parser.add_argument("--high-speed", action="store_true", help="Start in High Speed mode (core blocklist, no janitor, prefetch on)")
    parser.add_argument("--add-favorite", metavar="SITE", action="append", help="Save a favorite site (pinned + per-site fixes) and exit")
    parser.add_argument("--audit", action="store_true", help="Print the security audit as JSON and exit")
    parser.add_argument("--report", metavar="PATH",
                        help="Also write --self-test / --audit results as JSON to PATH (Windows GUI builds have no console)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse(list(sys.argv[1:] if argv is None else argv))
    from superwebby.settings import Settings

    if args.add_favorite:
        settings = Settings.load()
        for site in args.add_favorite:
            fav = settings.add_favorite(site)
            print(f"favorite saved: {fav.host}" if fav else f"not a site: {site}")
        settings.save()
        return 0
    if args.self_test:
        tmp = tempfile.mkdtemp(prefix="superwebby-selftest-")
        os.environ["XDG_DATA_HOME"] = tmp
        os.environ["XDG_CACHE_HOME"] = tmp
        os.environ["XDG_CONFIG_HOME"] = tmp
    if sys.platform.startswith("linux"):
        has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    else:
        has_display = False
    # Linux: keep the real display when one exists so --self-test can screenshot.
    # Windows/macOS: --self-test and --audit always run offscreen (headless CI, no window flash).
    offscreen = bool(args.offscreen or ((args.self_test or args.audit) and not has_display))
    _prepare_environment(offscreen=offscreen)

    from superwebby.web import register_scheme

    register_scheme()

    from PyQt6.QtCore import QCoreApplication, Qt, QTimer
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication

    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    QCoreApplication.setApplicationName(__app_name__)
    QCoreApplication.setOrganizationName("Superwebby")
    QCoreApplication.setOrganizationDomain("superwebby.local")
    QCoreApplication.setApplicationVersion(__version__)

    app = QApplication(sys.argv[:1])
    if sys.platform.startswith("linux"):
        app.setDesktopFileName(os.environ.get("FLATPAK_ID") or "superwebby")
    app.setApplicationDisplayName(__app_name__)
    app.setQuitOnLastWindowClosed(True)

    from superwebby.theme import apply as apply_theme

    apply_theme(app, force_dark=True)

    icon = QIcon(str(_icon_path())) if _icon_path().is_file() else QIcon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    from superwebby.blocker import Blocker
    from superwebby.history import HistoryStore
    from superwebby.window import BrowserWindow, interpret_input

    settings = Settings.load()
    if args.high_speed:
        settings.high_speed = True
    blocker = Blocker(high_speed=settings.high_speed)
    blocker.relaxed_for = lambda host: settings.tweaks_for(host)["relaxed"]
    from superwebby.web import create_profile

    profile = create_profile(blocker, incognito=args.incognito, settings=settings)
    store_path = data_home() / "history.sqlite"
    history = HistoryStore(store_path, enabled=not args.incognito)

    window = BrowserWindow(profile, blocker, history, icon, incognito=args.incognito, settings=settings)
    if args.audit:
        import json

        from superwebby.audit import run_audit

        report = run_audit(window)
        text = json.dumps(report, indent=2, default=str)
        _write_report(args.report, text)
        print(text)
        return 0
    window.show()

    startup = None
    if args.url:
        startup = interpret_input(args.url)
    if args.self_test:
        return _run_self_test(app, window, blocker, screenshot=args.screenshot, report=args.report)
    if startup:
        window.restore_or_start(startup_url=startup)
    elif args.no_restore or args.incognito:
        window.open_tab()
    else:
        window.restore_or_start()

    if args.screenshot:
        path = Path(args.screenshot)

        def _shot() -> None:
            pixmap = window.grab()
            path.parent.mkdir(parents=True, exist_ok=True)
            pixmap.save(str(path), "PNG")

        QTimer.singleShot(1800, _shot)

    return app.exec()


def _write_report(path: str | None, text: str) -> None:
    if not path:
        return
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def _run_self_test(app, window, blocker, screenshot: str | None, report: str | None = None) -> int:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from PyQt6.QtCore import QTimer, QUrl
    from pathlib import Path

    results: dict[str, object] = {"ok": False, "errors": []}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args, **kwargs):  # noqa: ANN001
            return

        def do_GET(self):  # noqa: N802
            if self.path.startswith("/ads/pixel"):
                self.send_response(200)
                self.send_header("Content-Type", "image/gif")
                self.end_headers()
                self.wfile.write(b"GIF89a")
                return
            if self.path == "/ok.txt":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"ok")
                return
            body = b"""<!doctype html><html><head><title>Superwebby Test Page</title>
<style>body{font-family:system-ui;background:#0e1116;color:#e6edf3;padding:40px}
h1{color:#ff6b3d} .ok{color:#3dd68c}</style></head>
<body>
<h1>Superwebby self-test</h1>
<p class="ok">This page should render. The tracker image and doubleclick request must be blocked.</p>
<img src="/ads/pixel.gif" alt="" width="1" height="1" id="adpixel">
<img src="https://doubleclick.net/pixel.gif" alt="" width="1" height="1" id="tracker">
<img src="/ok.txt" alt="" width="1" height="1">
<p>Ctrl+J opens the downloads panel the way Brave did before they removed it.</p>
</body></html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/"

    window.restore_or_start(startup_url=url)

    def finish() -> None:
        errors = []
        # Domain + path blocking
        if not blocker.host_is_blocked("doubleclick.net"):
            errors.append("doubleclick.net missing from blocklist")
        if not blocker.host_is_blocked("ad.doubleclick.net"):
            errors.append("subdomain matching failed for ad.doubleclick.net")
        if not blocker.would_block("https://doubleclick.net/pixel.gif"):
            errors.append("would_block failed for doubleclick.net")
        if not blocker.would_block("http://127.0.0.1/ads/pixel.gif", main_frame=False):
            errors.append("path rule failed for /ads/pixel")
        if blocker.would_block(url, main_frame=True):
            errors.append("main frame of the test page was incorrectly blocked")
        # Downloads panel (Ctrl+J)
        if window.downloads.isVisible():
            errors.append("downloads panel should start hidden")
        window.toggle_downloads()
        if not window.downloads.isVisible():
            errors.append("Ctrl+J/toggle did not show the downloads panel")
        # History panel
        window.toggle_history()
        if not window.history_panel.isVisible():
            errors.append("history panel did not open")
        if window.downloads.isVisible():
            errors.append("downloads panel should hide when history opens")
        window.toggle_history()
        window.toggle_downloads()
        if not window.downloads.isVisible():
            errors.append("downloads panel did not reopen")
        # Palette
        window.open_palette()
        if not window.palette.isVisible():
            errors.append("command palette did not open")
        window.palette.hide_palette()
        # 1.1: YouTube / YouTube Music ad rules (always on, also in High Speed)
        yt_cases = [
            "https://music.youtube.com/api/stats/ads?ver=2",
            "https://www.youtube.com/pagead/viewthroughconversion/1",
            "https://www.youtube.com/ptracking?pltype=adhost",
            "https://music.youtube.com/youtubei/v1/player/ad_break?key=x",
            "https://rr1---sn-x.googlevideo.com/videoplayback?id=1&oad=1",
            "https://rr1---sn-x.googlevideo.com/videoplayback?id=1&ctier=L",
            "https://googleads.g.doubleclick.net/pagead/id",
        ]
        for mode in (False, True):
            blocker.set_high_speed(mode)
            for case in yt_cases:
                if not blocker.would_block(case):
                    errors.append(f"YouTube ad rule missed (high_speed={mode}): {case}")
            if blocker.would_block("https://rr1---sn-x.googlevideo.com/videoplayback?id=1&itag=251"):
                errors.append("normal googlevideo stream wrongly blocked")
            if blocker.would_block("https://music.youtube.com/youtubei/v1/player?key=x"):
                errors.append("YouTube player API wrongly blocked")
        if len(blocker.core_domains) >= len(blocker.full_domains):
            errors.append("core list should be smaller than the full list")
        blocker.set_high_speed(False)
        # 1.1: menu has Dirty Browser and High Speed
        labels = [a.text() for a in window.main_menu.actions()]
        if "Dirty Browser" not in labels:
            errors.append("Dirty Browser menu item missing")
        if "High Speed" not in labels:
            errors.append("High Speed menu item missing")
        dirty = window.open_dirty_browser()
        if not dirty.incognito or not dirty.profile.isOffTheRecord():
            errors.append("Dirty Browser did not open an off-the-record window")
        dirty.close()
        window.set_high_speed(True)
        if not blocker.high_speed or not window.speed_action.isChecked():
            errors.append("High Speed toggle did not apply")
        names = [sc.name() for sc in window.profile.scripts().toList()]
        if "superwebby-cookie-janitor" in names:
            errors.append("janitor should be off in High Speed mode")
        if "superwebby-youtube-adblock" not in names:
            errors.append("YouTube userscript missing in High Speed mode")
        window.set_high_speed(False)
        names = [sc.name() for sc in window.profile.scripts().toList()]
        if "superwebby-cookie-janitor" not in names or "superwebby-youtube-adblock" not in names:
            errors.append("scripts not restored after leaving High Speed mode")
        # 1.1: favorites + audit
        fav = window.settings.add_favorite("https://www.Docs.Google.com/document")
        if fav is None or fav.host != "docs.google.com" or not fav.no_dark:
            errors.append("favorite site normalization / built-in fix failed")
        window.settings.remove_favorite("docs.google.com")
        from superwebby.audit import run_audit

        report = run_audit(window)
        results["audit"] = report["counts"]
        if len(report["checks"]) < 8:
            errors.append("audit returned too few checks")
        window.navigate("superwebby://audit")
        window.navigate("superwebby://settings")
        # Omnibox + shortcuts wiring
        if window.omnibox is None:
            errors.append("omnibox missing")
        # Native new-tab page is GPU-independent; show it with the downloads shelf for the shot.
        window.navigate("superwebby://newtab")
        if not window.downloads.isVisible():
            window.toggle_downloads()
        window.setWindowTitle("Superwebby")
        shot = screenshot or str(Path(tempfile.gettempdir()) / "superwebby-selftest.png")
        try:
            pix = window.grab()
            Path(shot).parent.mkdir(parents=True, exist_ok=True)
            if not pix.save(shot, "PNG"):
                errors.append("failed to write screenshot")
            else:
                results["screenshot"] = shot
        except Exception as exc:  # pragma: no cover
            errors.append(f"screenshot: {exc}")
        results["errors"] = errors
        results["ok"] = not errors
        results["blocked_total"] = blocker.total_blocked
        results["domains"] = len(blocker.domains)
        app.quit()

    # Give the page a moment to load and the interceptor to run.
    QTimer.singleShot(2500, finish)
    code = app.exec()
    try:
        server.shutdown()
    except Exception:
        pass
    errors = results.get("errors") or []
    import json
    import platform

    results["platform"] = f"{platform.system()} {platform.release()} {platform.machine()}"
    results["version"] = __version__
    _write_report(report, json.dumps(results, indent=2, default=str))
    if results.get("ok"):
        print(
            f"SUPERWEBBY SELF-TEST OK  domains={results.get('domains')} "
            f"blocked_session={results.get('blocked_total')}  audit={results.get('audit')}  "
            f"screenshot={results.get('screenshot')}"
        )
        return 0
    print("SUPERWEBBY SELF-TEST FAILED")
    for item in errors:
        print(" -", item)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
