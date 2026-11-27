# Superwebby security audit

Superwebby ships its own audit. Open `superwebby://audit` (or the **Audit**
toolbar button, *Menu → Security Audit*, or run `superwebby --audit` for JSON).
Every check runs **live against the build you are running**. No result is
hard-coded to pass, and warnings and failures are shown as they are.

## What is checked

| Check | How | PASS means |
| --- | --- | --- |
| Telemetry endpoints | Parses Superwebby's own code (the source, or the compiled bytecode in the PyInstaller binary) for network imports, URL literals, and known telemetry hosts; confirms Chromium's phone-home switches are set (`--disable-breakpad`, `--disable-crash-reporter`, `--disable-component-update`, `--disable-background-networking`, `--disable-sync`, `--disable-domain-reliability`, `--no-pings`, `--disable-metrics`) | No telemetry hosts or network libraries in the code; every switch present |
| Ad/tracker blocklist | Counts the domains actually loaded and reads the list version | ≥1,000 domains active, list ≤90 days old |
| Chromium renderer sandbox | Reads `QTWEBENGINE_DISABLE_SANDBOX` and the Chromium flags, then inspects the live `QtWebEngineProcess` command lines (`/proc` on Linux, `ps` on macOS, `Win32_Process` on Windows) | Renderers running and none started with `--no-sandbox` (WARN if none were running to confirm it) |
| HTTPS upgrade | Feeds a bare hostname through the address bar logic and checks the interceptor for an HTTPS-upgrade rule | Typed addresses *and* http:// links are upgraded |
| Third-party cookies | Checks that the cookie-store filter is installed on the live profile | Third-party cookies refused |
| WebRTC IP leak | Reads `WebRTCPublicInterfacesOnly` from the live profile | Local/LAN IPs hidden from WebRTC |
| Fingerprinting | Reads the live profile settings and Chromium flags | Always WARN today: see below |
| Engine version / CVE age | Reads `qWebEngineChromiumVersion()` and `qWebEngineChromiumSecurityPatchVersion()` and dates them against Chrome's public milestone schedule (bundled offline from chromiumdash) | Security patches match the current Chrome stable; WARN if behind, FAIL if more than 3 milestones or 60 days behind |
| Static analysis | Build-time `bandit` on the source and `pip-audit` on the Python packages the binary is built from (`packaging/run-static-audit.sh`) | No findings |

## Results for 1.1.0 (run 2026-11-27)

Runtime results differ by build because the Flatpak and the binary ship
different Qt WebEngine versions.

| Check | AUR `superwebby-bin` (PyInstaller, Qt 6.12.0) | Flatpak (PyQt BaseApp 6.11, Qt 6.11.2) |
| --- | --- | --- |
| Telemetry endpoints | **PASS** (14 compiled modules scanned) | **PASS** (16 modules scanned) |
| Ad/tracker blocklist | **PASS**: 124,449 domains, list 2026.11.24; core list 3,570 (2026.11.27) | **PASS**: same lists |
| Chromium renderer sandbox | **PASS**: renderers running, none with `--no-sandbox` | **PASS** with a D-Bus session bus (every desktop has one): renderers sandboxed through Flatpak sub-sandboxes. Without a session bus Qt WebEngine cannot start in Flatpak at all, so our headless CI box runs it with `QTWEBENGINE_DISABLE_SANDBOX=1`, and the audit then shows **FAIL** |
| HTTPS upgrade | **WARN**: typed addresses go to https://, but http:// links on pages are not upgraded (no HTTPS-only mode yet) | **WARN**: same |
| Third-party cookies | **PASS** | **PASS** |
| WebRTC IP leak | **PASS** | **PASS** |
| Fingerprinting | **WARN**: plugins, hyperlink-auditing pings, screen capture, Privacy Sandbox ad APIs off; permission prompts auto-denied. No canvas/WebGL/audio randomization, no font or screen spoofing; the User-Agent says Superwebby | **WARN**: same |
| Engine / CVE age | **WARN**: Chromium 140 base with security patches through **157** (Chrome 157 stable 2026-11-03); 1 milestone behind Chrome 158; fixes from 158 have been public for up to 10 days | **FAIL**: Chromium 140 base with patches only through **151** (Chrome 151 stable 2026-07-28); 7 milestones behind; fixes from Chrome 152+ have been public for up to 94 days. This is the newest PyQt BaseApp on Flathub (6.11); Superwebby moves to the next one when it ships |
| **Totals** | **5 PASS · 3 WARN · 0 FAIL** | **5 PASS · 2 WARN · 1 FAIL** |

The AUR from-source package (`superwebby`) uses Arch's own `qt6-webengine`, so
its engine result depends on the Arch version installed; run the audit to see it.

### Static analysis (build time)

- **bandit 1.9.4 on 3,601 lines of Superwebby source: 14 findings, all LOW**,
  0 medium, 0 high. 12 × B110 (`try/except/pass`, deliberate: the WebEngine
  I/O thread must never crash on a bad request) and 2 × B105 false positives
  (a hex colour string, `'#3dd68c'`, flagged as a "hardcoded password"). One
  MEDIUM B108 finding from the first run (a hard-coded `/tmp` path for the
  self-test screenshot) was fixed by switching to `tempfile.gettempdir()`.
- **pip-audit: 0 known vulnerabilities** in the 9 PyPI packages the binary is
  built from (PyQt6 6.12.1, PyQt6-Qt6 6.12.1, PyQt6-WebEngine 6.140.1,
  PyQt6-WebEngine-Qt6 6.140.0, PyInstaller 6.22.3, pyinstaller-hooks-contrib
  2026.10, altgraph 0.17.5, packaging 26.4, setuptools 84.2.1). pip-audit
  cannot see Chromium CVEs inside Qt WebEngine; the engine check above covers those.

### Idle network test

The binary was started on its new-tab page with a fresh profile and left idle
for 30 seconds while every TCP/UDP socket owned by Superwebby and its
`QtWebEngineProcess` children was sampled once per second (`ss -tunp`).
**Sockets seen: 0.** Sampling once a second could miss a connection that
opens and closes within the same second; this is a sanity check, not a packet
capture.

## Known gaps (planned)

- No HTTPS-only mode for links yet.
- No fingerprint randomization (canvas/WebGL/audio), unlike Brave.
- The Flatpak's engine lags Chrome stable until a newer PyQt BaseApp ships.
- The full blocklist is a compiled snapshot (2026.11.24) and does not update
  itself; rebuilding the list is part of each release.

Report security problems at <https://github.com/superwebby/superwebby/issues>.
