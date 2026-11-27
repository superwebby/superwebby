"""Internal superwebby:// pages and the custom scheme handler."""

from __future__ import annotations

from html import escape
from urllib.parse import urlparse

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QUrl
from PyQt6.QtWebEngineCore import QWebEngineUrlRequestJob, QWebEngineUrlSchemeHandler

from superwebby import __version__

CSS = """
:root {
  --bg: #0e1116;
  --surface: #161b22;
  --surface2: #1c2330;
  --border: #2d3646;
  --text: #e6edf3;
  --muted: #8b9bb0;
  --accent: #ff6b3d;
  --accent2: #7c9cff;
}
* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0;
  background: var(--bg); color: var(--text);
  font: 15px/1.5 system-ui, "Segoe UI", Ubuntu, sans-serif;
  min-height: 100%;
}
a { color: var(--accent2); text-decoration: none; }
a:hover { text-decoration: underline; }
.wrap { max-width: 820px; margin: 0 auto; padding: 72px 28px 48px; }
.mark {
  width: 56px; height: 56px; border-radius: 16px;
  background: linear-gradient(135deg, #1a2234, #0c1020);
  border: 1px solid var(--border);
  display: grid; place-items: center;
  color: var(--accent); font-weight: 700; font-size: 28px;
  margin-bottom: 18px;
}
h1 { font-size: 28px; font-weight: 650; letter-spacing: -0.03em; margin: 0 0 8px; }
.sub { color: var(--muted); margin: 0 0 28px; }
form.search { display: flex; gap: 8px; margin-bottom: 36px; }
input[type=search], input[type=text] {
  flex: 1; background: #0b0e13; color: var(--text);
  border: 1px solid var(--border); border-radius: 12px;
  padding: 12px 16px; font-size: 16px; outline: none;
}
input:focus { border-color: var(--accent); }
button, .chip {
  background: var(--surface2); color: var(--text);
  border: 1px solid var(--border); border-radius: 10px;
  padding: 10px 14px; cursor: pointer; font: inherit;
}
button:hover, .chip:hover { border-color: var(--accent); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; }
.tile {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; padding: 12px 14px; color: inherit; display: block;
}
.tile small { display: block; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hints { margin-top: 48px; color: var(--muted); font-size: 13px; }
kbd {
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 6px; padding: 1px 6px; font: 12px ui-monospace, monospace;
  color: var(--text);
}
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--border); vertical-align: top; }
th { color: var(--muted); font-weight: 500; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }
.title { font-weight: 600; }
.url { color: var(--muted); font-size: 13px; word-break: break-all; }
.meta { margin: 0 0 18px; color: var(--muted); }
"""


def _shell(title: str, body: str) -> bytes:
    html = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>{CSS}</style>
</head><body>
{body}
</body></html>
"""
    return html.encode("utf-8")


def newtab_html(frequent: list, recent: list) -> bytes:
    tiles = []
    seen = set()
    for item in list(frequent) + list(recent):
        url = item.url
        if url in seen:
            continue
        seen.add(url)
        title = escape(item.title or url)
        host = escape(urlparse(url).hostname or url)
        tiles.append(
            f'<a class="tile" href="{escape(url)}"><strong>{title}</strong><small>{host}</small></a>'
        )
        if len(tiles) >= 8:
            break
    grid = ""
    if tiles:
        grid = "<h2 style='font-size:13px;color:var(--muted);font-weight:600;letter-spacing:.06em;text-transform:uppercase'>Jump back in</h2>"
        grid += '<div class="grid">' + "".join(tiles) + "</div>"
    body = f"""
<div class="wrap">
  <div class="mark">S</div>
  <h1>Superwebby</h1>
  <p class="sub">A painless browser. No nags, no telemetry, no wizard. Type and go.</p>
  <form class="search" action="https://duckduckgo.com/" method="get">
    <input type="search" name="q" placeholder="Search DuckDuckGo or paste an address" autofocus>
    <button type="submit">Search</button>
  </form>
  {grid}
  <p class="hints">
    <kbd>Ctrl</kbd>+<kbd>L</kbd> address
    &nbsp;<kbd>Ctrl</kbd>+<kbd>K</kbd> command palette
    &nbsp;<kbd>Ctrl</kbd>+<kbd>J</kbd> downloads
    &nbsp;<kbd>Ctrl</kbd>+<kbd>H</kbd> history
    &nbsp;<kbd>Ctrl</kbd>+<kbd>T</kbd> new tab
  </p>
</div>
"""
    return _shell("New Tab", body)


def history_html(visits: list) -> bytes:
    rows = []
    for item in visits:
        title = escape(item.title or item.url)
        url = escape(item.url)
        rows.append(
            f'<tr><td><div class="title"><a href="{url}">{title}</a></div>'
            f'<div class="url">{url}</div></td><td>{item.count}</td></tr>'
        )
    table = (
        "<table><thead><tr><th>Page</th><th>Visits</th></tr></thead><tbody>"
        + ("".join(rows) or "<tr><td colspan='2'>No history yet.</td></tr>")
        + "</tbody></table>"
    )
    body = f"""
<div class="wrap">
  <h1>History</h1>
  <p class="meta">Local only. Nothing is synced or reported. Press <kbd>Ctrl</kbd>+<kbd>H</kbd> to toggle the panel.</p>
  {table}
</div>
"""
    return _shell("History", body)


def downloads_html(items: list[dict]) -> bytes:
    rows = []
    for item in items:
        name = escape(str(item.get("name") or ""))
        url = escape(str(item.get("url") or ""))
        state = escape(str(item.get("state") or ""))
        path = escape(str(item.get("path") or ""))
        rows.append(
            f"<tr><td><div class='title'>{name}</div><div class='url'>{url}</div></td>"
            f"<td>{state}</td><td class='url'>{path}</td></tr>"
        )
    table = (
        "<table><thead><tr><th>File</th><th>Status</th><th>Path</th></tr></thead><tbody>"
        + ("".join(rows) or "<tr><td colspan='3'>No downloads yet. They land quietly in ~/Downloads.</td></tr>")
        + "</tbody></table>"
    )
    body = f"""
<div class="wrap">
  <h1>Downloads</h1>
  <p class="meta">Saved automatically to your Downloads folder. <kbd>Ctrl</kbd>+<kbd>J</kbd> toggles the panel.</p>
  {table}
</div>
"""
    return _shell("Downloads", body)


def about_html(block_count: int, domain_count: int) -> bytes:
    body = f"""
<div class="wrap">
  <div class="mark">S</div>
  <h1>Superwebby {escape(__version__)}</h1>
  <p class="sub">A from-scratch desktop browser. Not a reskin of Chromium UI, Brave, Firefox, Ladybird, qutebrowser, or surf — though it uses Qt WebEngine so pages actually render.</p>
  <p class="meta">
    Built-in ad and tracker blocking ({domain_count:,} domains), no telemetry,
    no sign-in nags, no first-run wizard, automatic downloads, auto dark mode,
    a command palette, and a real <kbd>Ctrl</kbd>+<kbd>J</kbd> downloads panel.
  </p>
  <p class="meta">Blocked this session: <strong>{block_count}</strong>. License: GPL-3.0-or-later.</p>
  <p class="meta">Source, releases and issues: <a href="https://github.com/superwebby/superwebby">github.com/superwebby/superwebby</a></p>
</div>
"""
    return _shell("About Superwebby", body)


def blocked_html(stats, page_url: str, total: int) -> bytes:
    rows = []
    hosts = sorted(stats.hosts.items(), key=lambda kv: (-kv[1], kv[0])) if stats else []
    for host, count in hosts:
        rows.append(f"<tr><td>{escape(host)}</td><td>{count}</td></tr>")
    table = (
        "<table><thead><tr><th>Host</th><th>Blocked</th></tr></thead><tbody>"
        + ("".join(rows) or "<tr><td colspan='2'>Nothing blocked on this page.</td></tr>")
        + "</tbody></table>"
    )
    body = f"""
<div class="wrap">
  <h1>Shield</h1>
  <p class="meta">{stats.count if stats else 0} request(s) blocked on this page. {total} this session.</p>
  <p class="url">{escape(page_url or "")}</p>
  {table}
</div>
"""
    return _shell("Shield", body)


def audit_html(report: dict) -> bytes:
    colors = {"PASS": "#3dd68c", "WARN": "#f2c94c", "FAIL": "#ff5c5c", "INFO": "#7c9cff"}
    rows = []
    for c in report["checks"]:
        rows.append(
            f"<tr><td style='color:{colors.get(c['status'], '#fff')};font-weight:700'>{escape(c['status'])}</td>"
            f"<td><div class='title'>{escape(c['name'])}</div>{escape(c['detail'])}"
            f"<div class='url'>{escape(c.get('evidence', ''))}</div></td></tr>"
        )
    static = report.get("static", {})
    for t in static.get("tools", []):
        rows.append(
            f"<tr><td style='color:{colors.get(t.get('status'), '#fff')};font-weight:700'>{escape(t.get('status', ''))}</td>"
            f"<td><div class='title'>{escape(t.get('name', ''))} (static)</div>{escape(t.get('summary', ''))}</td></tr>"
        )
    body = f"""
<div class="wrap">
  <h1>Security audit</h1>
  <p class="meta">Superwebby {escape(report['version'])} · {escape(report['mode'])} mode · {escape(report['ran_at'])}</p>
  <table><thead><tr><th>Result</th><th>Check</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
</div>
"""
    return _shell("Security audit", body)


class SuperwebbySchemeHandler(QWebEngineUrlSchemeHandler):
    def __init__(self, app_window, parent=None) -> None:
        super().__init__(parent)
        self.window = app_window

    def requestStarted(self, job: QWebEngineUrlRequestJob) -> None:  # noqa: N802
        url: QUrl = job.requestUrl()
        name = (url.host() or url.path().lstrip("/")).lower()
        if name.endswith("/"):
            name = name[:-1]
        try:
            payload = self._render(name)
        except Exception as exc:  # last-resort error page
            payload = _shell("Error", f"<div class='wrap'><h1>Page error</h1><p>{escape(str(exc))}</p></div>")
        data = QByteArray(payload)
        buffer = QBuffer(job)
        buffer.setData(data)
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        job.reply(b"text/html; charset=utf-8", buffer)

    def _render(self, name: str) -> bytes:
        win = self.window
        if name in {"", "newtab", "home", "start"}:
            frequent = win.history.frequent() if win else []
            recent = win.history.recent(12) if win else []
            return newtab_html(frequent, recent)
        if name == "history":
            return history_html(win.history.recent(200) if win else [])
        if name == "downloads":
            items = win.downloads.as_dicts() if win else []
            return downloads_html(items)
        if name == "about":
            domains = len(win.blocker.domains) if win else 0
            total = win.blocker.total_blocked if win else 0
            return about_html(total, domains)
        if name in {"blocked", "shield"}:
            url = win.current_url() if win else ""
            stats = win.blocker.stats_for(url) if win else None
            total = win.blocker.total_blocked if win else 0
            return blocked_html(stats, url, total)
        if name in {"audit", "security"} and win is not None:
            from superwebby.audit import run_audit

            return audit_html(run_audit(win))
        return _shell(
            "Unknown",
            "<div class='wrap'><h1>Unknown page</h1><p class='meta'>Try superwebby://newtab, history, downloads, about, audit, settings, or shield.</p></div>",
        )
