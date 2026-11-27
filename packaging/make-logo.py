#!/usr/bin/env python3
"""Generate the Superwebby logo SVG: a peace sign formed by people holding
hands, whose centre stroke is a rifle with a flower blooming from the muzzle.
A peace / anti-violence image ("flower power"), not weapon glorification."""
import colorsys
import math
import sys

S = 512
CX, CY = 256, 256
R = 178            # radius of the circle where the people stand (feet)
FIG = 1.0          # figure scale


def person(x, y, angle_deg, color, scale=1.0):
    """A little person standing at (x, y), head pointing along angle (0 = up)."""
    s = scale
    return (
        f'<g transform="translate({x:.1f},{y:.1f}) rotate({angle_deg:.1f}) scale({s:.3f})">'
        f'<circle cx="0" cy="-37" r="7.5" fill="{color}"/>'
        f'<path d="M-6,-27 Q0,-30 6,-27 L5,-12 L-5,-12 Z" fill="{color}"/>'
        f'<path d="M-3.5,-13 L-5,0 M3.5,-13 L5,0" stroke="{color}" stroke-width="4.2" stroke-linecap="round" fill="none"/>'
        f'<path d="M-5,-25 L-14,-21 M5,-25 L14,-21" stroke="{color}" stroke-width="3.6" stroke-linecap="round" fill="none"/>'
        f'</g>'
    )


def hue(i, n, sat=0.62, light=0.66):
    r, g, b = colorsys.hls_to_rgb((i / n) % 1.0, light, sat)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


parts = []
parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" width="{S}" height="{S}">
<title>Superwebby: a flower in the barrel, a peace sign made of people</title>
<defs>
  <radialGradient id="bg" cx="50%" cy="42%" r="70%">
    <stop offset="0" stop-color="#1d2a4a"/><stop offset="1" stop-color="#0b1020"/>
  </radialGradient>
  <linearGradient id="steel" x1="0" x2="1">
    <stop offset="0" stop-color="#5d6b80"/><stop offset="0.5" stop-color="#9aa8bb"/><stop offset="1" stop-color="#4f5b6d"/>
  </linearGradient>
  <linearGradient id="wood" x1="0" x2="1">
    <stop offset="0" stop-color="#6b4a32"/><stop offset="0.5" stop-color="#9a6e4b"/><stop offset="1" stop-color="#5a3d29"/>
  </linearGradient>
  <radialGradient id="petal" cx="50%" cy="80%" r="80%">
    <stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#ff8fc7"/>
  </radialGradient>
</defs>
<rect x="8" y="8" width="496" height="496" rx="112" fill="url(#bg)"/>
''')

# --- the ring of people, holding hands (arms = a ring at shoulder height)
arm_r = R + 21
parts.append(f'<circle cx="{CX}" cy="{CY}" r="{arm_r}" fill="none" stroke="#ffd36e" stroke-width="3.2" opacity="0.9"/>')
N = 30
for i in range(N):
    a = 2 * math.pi * i / N
    x = CX + R * math.sin(a)
    y = CY - R * math.cos(a)
    parts.append(person(x, y, math.degrees(a), hue(i, N), FIG))

# --- the two legs of the peace sign, each a line of people holding hands
def line_of_people(x0, y0, x1, y1, n, offset_hue):
    out = []
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    # normal pointing "up" relative to the line
    nx, ny = uy, -ux
    if ny > 0:
        nx, ny = -nx, -ny
    ang = math.degrees(math.atan2(nx, -ny))
    sx0, sy0 = x0 + nx * 21, y0 + ny * 21
    sx1, sy1 = x1 + nx * 21, y1 + ny * 21
    out.append(f'<line x1="{sx0:.1f}" y1="{sy0:.1f}" x2="{sx1:.1f}" y2="{sy1:.1f}" stroke="#ffd36e" stroke-width="3.2" opacity="0.9"/>')
    for k in range(n):
        t = (k + 0.5) / n
        out.append(person(x0 + dx * t, y0 + dy * t, ang, hue(k + offset_hue, n * 3), FIG))
    return out

leg = R + 4
lx = CX - leg * math.sin(math.radians(45))
ly = CY + leg * math.cos(math.radians(45))
rx = CX + leg * math.sin(math.radians(45))
parts += line_of_people(CX - 14, CY + 14, lx, ly, 5, 3)
parts += line_of_people(CX + 14, CY + 14, rx, ly, 5, 9)

# --- the centre stroke: a rifle pointing up, butt down, flower in the muzzle
rifle = f'''
<g opacity="0.97">
  <!-- barrel -->
  <rect x="250" y="112" width="12" height="150" rx="3" fill="url(#steel)"/>
  <rect x="247" y="110" width="18" height="10" rx="2" fill="#7d8aa0"/>
  <!-- handguard -->
  <rect x="244" y="190" width="24" height="70" rx="6" fill="url(#wood)"/>
  <!-- receiver -->
  <rect x="243" y="256" width="26" height="54" rx="5" fill="url(#steel)"/>
  <!-- trigger guard (empty, no hand on it) -->
  <path d="M269,300 q18,4 14,26 q-4,10 -14,6" fill="none" stroke="#7d8aa0" stroke-width="4"/>
  <!-- stock -->
  <path d="M243,306 L269,306 L276,404 Q256,416 236,404 Z" fill="url(#wood)"/>
  <rect x="234" y="402" width="44" height="10" rx="4" fill="#3d2a1d"/>
</g>
<!-- flower growing out of the muzzle -->
<g>
  <path d="M256,116 C254,98 262,86 256,66" stroke="#46c26a" stroke-width="5" fill="none" stroke-linecap="round"/>
  <path d="M257,96 C270,92 278,96 284,104 C272,108 263,104 257,96 Z" fill="#46c26a"/>
  <path d="M255,102 C242,98 234,102 229,110 C241,113 250,110 255,102 Z" fill="#3aa95a"/>
  <g transform="translate(256,58)">
'''
for k in range(8):
    rifle += f'<ellipse cx="0" cy="-15" rx="7.5" ry="15" fill="url(#petal)" transform="rotate({k * 45})"/>'
rifle += '''
    <circle r="9" fill="#ffcf3d"/><circle r="4" fill="#f59f00"/>
  </g>
</g>
'''
parts.append(rifle)
parts.append('</svg>\n')

out = sys.argv[1] if len(sys.argv) > 1 else "superwebby.svg"
with open(out, "w") as fh:
    fh.write("\n".join(parts))
print("wrote", out)
