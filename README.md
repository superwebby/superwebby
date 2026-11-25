# Superwebby

A painless, privacy-first desktop web browser. It is a new browser — not a
repackaged Ladybird, qutebrowser, or surf build — with a real **Ctrl+J
downloads panel** the way Brave used to work, then pushed further so everyday
browsing stays out of your way.

Superwebby uses **Python 3 + PyQt6 / Qt WebEngine** so it actually builds and
renders modern pages, then wraps its own chrome, shortcuts, blocking, and
internal pages around that engine.

The application ID used for Flatpak is `io.github.superwebby.Superwebby`. That
GitHub-style namespace is a placeholder and is easy to rename later in the
manifest, desktop file, metainfo, and icon filenames together.

## Why it exists

Brave used to open downloads with Ctrl+J. When that went away, a small, useful
habit went with it. Superwebby puts the downloads panel back, then removes the
rest of the usual browser friction:

- No telemetry, crash-phone-home, or metrics
- No sign-in nags, no default-browser nag, no first-run wizard
- Built-in ad and tracker blocking from the first request
- Quiet automatic downloads into `~/Downloads`
- Auto dark mode for both chrome and page content
- Cookie-banner auto-dismiss (prefers “Reject all” / “Necessary only”)
- A command palette that searches tabs, history, and commands
- Session restore without asking

## Features

- Tabbed browsing with favicons, drag-reorder, and a closed-tab stack
- Omnibox: URLs, search (DuckDuckGo), and history completion
- Request-interception blocker with a bundled domain list (~124k hosts) plus
  conservative path rules for `/pagead/`, `/ads/pixel`, and similar
- Shield badge shows how many requests were blocked on the current page
- Downloads shelf (Ctrl+J) and a `superwebby://downloads` page
- History panel (Ctrl+H) and a `superwebby://history` page
- Command palette (Ctrl+K)
- Auto dark mode (`ForceDarkMode` + Chromium force-dark)
- Cookie-banner janitor for common CMPs (OneTrust, Cookiebot, Quantcast,
  Didomi, Funding Choices, CookieYes, Osano, and others)
- Permission popups are denied quietly (clipboard paste is still allowed)
- Third-party cookies are phased out via Chromium flags
- Private windows (`--incognito`) write nothing to the profile
- Internal pages: `superwebby://newtab`, `history`, `downloads`, `about`, `shield`

Blocking uses a compiled, offline list derived from Peter Lowe’s ad server
list, StevenBlack/hosts (MIT), and EasyList / EasyPrivacy ad- and tracking-
server domains (CC BY-SA 3.0). See `superwebby/data/NOTICE`. The list is
shipped in the source tree so startup never needs a network fetch.

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| Ctrl+T | New tab |
| Ctrl+W | Close tab |
| Ctrl+Shift+T | Reopen last closed tab |
| Ctrl+Tab / Ctrl+PageDown | Next tab |
| Ctrl+Shift+Tab / Ctrl+PageUp | Previous tab |
| Ctrl+1 … Ctrl+8, Ctrl+9 | Jump to tab / last tab |
| Ctrl+L, Alt+D, F6 | Focus address bar |
| Ctrl+Enter (in address bar) | Wrap a bare word as `www.*.com` |
| Ctrl+K | Command palette |
| Ctrl+J | Toggle downloads panel |
| Ctrl+H | Toggle history panel |
| Ctrl+R / F5 | Reload (or stop while loading) |
| Ctrl+Shift+R / Shift+F5 | Hard reload |
| Ctrl+F, F3, Ctrl+G | Find in page / find next |
| Ctrl+Shift+G | Find previous |
| Ctrl+= / Ctrl+- / Ctrl+0 | Zoom in, out, reset |
| Alt+Left / Alt+Right | Back / forward |
| Alt+Home | New tab page |
| Ctrl+N | New window |
| F11 | Fullscreen |
| Escape | Close palette, find bar, or panel; stop load |
| Ctrl+Q / Ctrl+Shift+W | Quit window |

## Install from a Flatpak bundle

Once the bundle is published as a GitHub Release asset named
`superwebby-1.0.0.flatpak`, install it with:

```bash
flatpak install --user https://github.com/superwebby/Superwebby/releases/download/v1.0.0/superwebby-1.0.0.flatpak
flatpak run io.github.superwebby.Superwebby
```

From a local copy of the same bundle:

```bash
flatpak install --user ./superwebby-1.0.0.flatpak
flatpak run io.github.superwebby.Superwebby
```

The first install also pulls the KDE Platform 6.11 runtime from Flathub. Add
the remote first if you do not already have it:

```bash
flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
```

Build the bundle from this tree (needs `flatpak` and `flatpak-builder`):

```bash
cd flatpak
./build-bundle.sh
```

The Flatpak uses `org.kde.Platform` 6.11 and
`com.riverbankcomputing.PyQt.BaseApp` 6.11, which already includes PyQt6 and
Qt WebEngine.

## Install from an AUR-style PKGBUILD (Arch Linux)

This repo ships two PKGBUILDs:

- `aur/superwebby` — builds from the reproducible source tarball
- `aur/superwebby-bin` — installs a prebuilt, stripped PyInstaller onedir tree

They expect release assets at:

- `https://github.com/superwebby/Superwebby/releases/download/v1.0.0/superwebby-1.0.0.tar.gz`
- `https://github.com/superwebby/Superwebby/releases/download/v1.0.0/superwebby-1.0.0-x86_64.tar.gz`

Until those URLs exist, build the tarballs locally and place them next to the
PKGBUILD (or adjust `source=` to a `file://` path):

```bash
./packaging/build-source-tarball.sh
./packaging/build-bin.sh   # optional, for superwebby-bin
cp packaging/superwebby-1.0.0.tar.gz aur/superwebby/
cd aur/superwebby
# If you are installing from a local tarball, temporarily set
# source=("${pkgname}-${pkgver}.tar.gz") in the PKGBUILD, then:
makepkg -si
```

You need `base-devel` (`sudo pacman -S --needed base-devel`). `makepkg -si`
pulls in the Qt and PyQt dependencies for the source package. Launch with
`superwebby`.

## Running from this tree

```bash
python3 superwebby-run
python3 superwebby-run https://example.com
python3 superwebby-run --incognito
python3 superwebby-run --self-test --screenshot /tmp/superwebby.png
```

Dependencies: Python 3.11+, PyQt6, PyQt6 WebEngine (Arch: `python-pyqt6`
`python-pyqt6-webengine` `qt6-webengine`).

Profile data lives in `~/.local/share/superwebby/`. Cache is in
`~/.cache/superwebby/`. Under Flatpak, those paths are remapped into the
app's sandbox data directory. Nothing is sent anywhere.

## License

GPL-3.0-or-later. Superwebby uses PyQt6, which is available under the GPL.

## Rendering notes

Qt WebEngine needs a working GL/DRI path to paint web pages. On a normal Arch
desktop that just works. Some virtual framebuffers (Xvfb without DRI3, or
environments with no `/dev/dri`) can leave the web view blank even though the
page loaded, blocking ran, and the rest of the chrome is fine. Superwebby's
own pages (`superwebby://newtab`, history, downloads, about, shield) are native
widgets, so they still appear in that situation. `superwebby --self-test`
checks blocking, the Ctrl+J panel, history, the palette, and writes a
screenshot without requiring a GPU.
