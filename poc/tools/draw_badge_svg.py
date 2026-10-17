"""Hand-built vector (SVG) hero illustration of the Marco Badge.

Left: a person wearing the badge, AirPods in, the camera's view cone falling on a table, and
the "Polo" coming back from the keys. Right: the badge itself in a 3/4 view, built from the
real geometry (iPhone 15 Pro 70.6 x 146.6 x 8.25 mm on a 30 deg wedge) and projected
orthographically, so proportions are true.
Output: reports/figures/marco_badge_hero.svg
"""
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parents[1] / "reports" / "figures" / "marco_badge_hero.svg"
W, H = 1600, 1000
INK, SUB = "#1d2129", "#6b7380"
ORANGE, ORANGE_D, ORANGE_L = "#f29f38", "#d9832a", "#f7bd6f"
PHONE_TOP, PHONE_SIDE, PHONE_EDGE = "#2a2f37", "#16191e", "#3b414b"
BLUE = "#4f86f7"


def pts(arr):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in arr)


def poly(arr, fill, stroke="none", sw=0, op=1.0, extra=""):
    return f'<polygon points="{pts(arr)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{op}" stroke-linejoin="round" {extra}/>'


# ---------- 3/4 view of the badge (orthographic projection of the real geometry) ----------
TILT = np.radians(30)
PH, PW, PT = 146.6, 70.6, 8.25


def make_projector(yaw_deg=-38, pitch_deg=18, scale=2.25, origin=(1110, 740)):
    a, b = np.radians(yaw_deg), np.radians(pitch_deg)
    Ry = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    Rx = np.array([[1, 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]])
    R = Rx @ Ry

    def P(p):
        q = R @ np.asarray(p, float)
        return (origin[0] + scale * q[0], origin[1] - scale * q[1]), q[2]
    return P


def badge_parts(P):
    """Return list of (depth, svg) for the faces, drawn back to front."""
    d = np.array([0, np.cos(TILT), np.sin(TILT)])     # along the phone, bottom -> top (leans outward)
    n = np.array([0, -np.sin(TILT), np.cos(TILT)])    # outward normal of the phone's back
    xs = (-PW / 2, PW / 2)
    faces = []

    def face(corners, fill, stroke="none", sw=0, op=1.0):
        prj = [P(c) for c in corners]
        faces.append((len(faces), poly([q[0] for q in prj], fill, stroke, sw, op)))

    # wedge: triangular prism (chest plane z=0, tilted face under the phone), a bit wider than the phone
    wx = (-PW / 2 - 5, PW / 2 + 5)
    top_y = PH * np.cos(TILT)
    A, B, C = np.array([0, 0, 0]), np.array([0, top_y, 0]), np.array([0, top_y, PH * np.sin(TILT)])
    for x0 in wx:  # side triangles
        face([A + [x0, 0, 0], B + [x0, 0, 0], C + [x0, 0, 0]], ORANGE_D)
    face([B + [wx[0], 0, 0], B + [wx[1], 0, 0], C + [wx[1], 0, 0], C + [wx[0], 0, 0]], ORANGE_L)  # top
    # phone body
    corners = lambda s: [np.array([x, 0, 0]) + t * d + s * n for x, t in ((xs[0], 0), (xs[1], 0), (xs[1], PH), (xs[0], PH))]
    back0, back1 = corners(0.0), corners(PT)
    # orange wedge face visible as a rim around the phone (the tilted face, slightly larger)
    rim = [np.array([x, 0, 0]) + t * d - 0.3 * n for x, t in ((wx[0], -4), (wx[1], -4), (wx[1], PH + 4), (wx[0], PH + 4))]
    face(rim, ORANGE)
    for i in (0, 1, 2, 3):  # phone sides
        j = (i + 1) % 4
        face([back0[i], back0[j], back1[j], back1[i]], PHONE_SIDE)
    face(back1, PHONE_TOP, PHONE_EDGE, 1.2)  # outward back
    # camera module, lenses, LiDAR on the outward back near the top-left (seen from the front)
    o = lambda x, t, s=PT + 0.6: np.array([x, 0, 0]) + t * d + s * n
    cam = [o(-PW / 2 + 4, PH - 40), o(-PW / 2 + 38, PH - 40), o(-PW / 2 + 38, PH - 5), o(-PW / 2 + 4, PH - 5)]
    face(cam, "#3a4049", "#4a515c", 1.0)
    # MagSafe battery (raised block)
    bx, bt = (-PW / 2 + 7, PW / 2 - 7), (10, 100)
    b0 = [o(bx[0], bt[0]), o(bx[1], bt[0]), o(bx[1], bt[1]), o(bx[0], bt[1])]
    b1 = [o(x, t, PT + 11) for x, t in ((bx[0], bt[0]), (bx[1], bt[0]), (bx[1], bt[1]), (bx[0], bt[1]))]
    for i in range(4):
        j = (i + 1) % 4
        face([b0[i], b0[j], b1[j], b1[i]], "#cfd4dc")
    face(b1, "#f1f3f6", "#c3c9d2", 1.0)
    return faces, o, b1


def badge_svg():
    P = make_projector()
    faces, o, b1 = badge_parts(P)
    out = ['<g id="badge">', '<ellipse cx="1150" cy="815" rx="170" ry="22" fill="#000" opacity="0.07"/>']
    out += [f[1] for f in faces]
    # lenses (circles projected approximately as ellipses: draw small circles at projected centres)
    for x, t, r in ((-PW / 2 + 13, PH - 13, 6.5), (-PW / 2 + 13, PH - 30, 6.5), (-PW / 2 + 28, PH - 21.5, 6.5)):
        (cx, cy), _ = P(o(x, t, PT + 1.2))
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r * 2.0:.1f}" fill="#0c0e11" stroke="#555d69" stroke-width="1.5"/>')
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r * 0.8:.1f}" fill="#25303d"/>')
    (lx, ly), _ = P(o(-PW / 2 + 33, PH - 9, PT + 1.2))
    out.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="5" fill="#8c95a3"/>')
    # MagSafe ring + wordmark on the battery
    (mx, my), _ = P(o(0, 55, PT + 11.2))
    out.append(f'<ellipse cx="{mx:.1f}" cy="{my:.1f}" rx="44" ry="40" fill="none" stroke="#c3c9d2" stroke-width="2.5" transform="rotate(-8 {mx:.1f} {my:.1f})"/>')
    (tx, ty), _ = P(o(0, 22, PT + 11.2))
    out.append(f'<text x="{tx:.1f}" y="{ty:.1f}" font-family="-apple-system, Helvetica Neue, Arial" font-size="17" font-weight="700" fill="{SUB}" text-anchor="middle" transform="rotate(-9 {tx:.1f} {ty:.1f})" letter-spacing="3">MARCO</text>')
    # Action button (orange) on the phone's left edge as seen from the front
    a0, _ = P(o(-PW / 2 - 0.5, PH - 52, PT * 0.5))
    a1, _ = P(o(-PW / 2 - 0.5, PH - 40, PT * 0.5))
    out.append(f'<line x1="{a0[0]:.1f}" y1="{a0[1]:.1f}" x2="{a1[0]:.1f}" y2="{a1[1]:.1f}" stroke="#ff9f0a" stroke-width="6" stroke-linecap="round"/>')
    out.append("</g>")
    # callouts
    def callout(x0, y0, x1, y1, text, anchor="start"):
        return (f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" stroke="#9aa3ae" stroke-width="1.2"/>'
                f'<circle cx="{x0}" cy="{y0}" r="3.2" fill="#9aa3ae"/>'
                f'<text x="{x1 + (8 if anchor == "start" else -8)}" y="{y1 + 5}" font-family="-apple-system, Helvetica Neue, Arial" font-size="17" fill="{INK}" text-anchor="{anchor}">{text}</text>')
    (c1x, c1y), _ = P(o(-PW / 2 + 22, PH - 22, PT + 1))
    (c2x, c2y), _ = P(o(PW / 2 - 7, 70, PT + 11))
    (c3x, c3y), _ = P(np.array([PW / 2 + 5, PH * np.cos(TILT) * 0.45, 8]))
    (c4x, c4y), _ = P(o(-PW / 2 - 0.5, PH - 46, PT * 0.5))
    out.append(callout(c1x, c1y, 1300, 360, "Cameras + LiDAR, never covered"))
    out.append(callout(c2x, c2y, 1300, 560, "MagSafe battery (outward back)"))
    out.append(callout(c3x, c3y, 1300, 690, "30° wedge aims the camera down"))
    out.append(callout(c4x, c4y, 900, 430, "Action button: press to ask", anchor="end"))
    return "\n".join(out)


# ---------------------------------- scene with the person ----------------------------------
def person_svg():
    s = []
    px_m = 383.0                      # pixels per metre (1.75 m person from y=290 to y=960)
    chest_bottom = np.array([441.0, 556.0])
    up = np.array([np.sin(TILT), -np.cos(TILT)])        # phone long axis (screen y is down)
    out_n = np.array([np.cos(TILT), np.sin(TILT)])      # outward normal, 30 deg below horizontal
    L = 0.1466 * px_m
    top = chest_bottom + L * up
    cam = top - 0.018 * px_m * up + 4 * out_n
    # view cone: fan from the camera, +1 deg .. -61 deg, clipped by the table top (y=800) and floor
    fan = [cam]
    for a in np.linspace(np.radians(1), np.radians(-61), 60):
        d = np.array([np.cos(a), -np.sin(a)])
        t = 420.0
        if d[1] > 0:
            t_tab = (800 - cam[1]) / d[1]
            if 400 <= cam[0] + t_tab * d[0] <= 730:
                t = min(t, t_tab)
            t = min(t, (960 - cam[1]) / d[1])
        fan.append(cam + t * d)
    s.append(poly(fan, "url(#cone)"))
    # table + items
    s.append('<rect x="400" y="800" width="330" height="16" rx="5" fill="#c6ccd5"/>')
    s.append('<rect x="425" y="816" width="12" height="144" fill="#d5dae1"/><rect x="695" y="816" width="12" height="144" fill="#d5dae1"/>')
    s.append('<rect x="610" y="712" width="34" height="88" rx="9" fill="#4fa3a5"/><rect x="616" y="702" width="22" height="14" rx="4" fill="#3d8688"/>')
    s.append('<circle cx="500" cy="790" r="10" fill="none" stroke="#e0a40b" stroke-width="4"/>'
             '<path d="M 508 793 l 34 4 l 0 6 l -6 0 l 0 4 l -5 0 l 0 -4 l -24 -3 Z" fill="#e0a40b"/>'
             '<path d="M 494 798 l -8 22 l 5 2 l 2 -5 l 4 1 l 2 -4 l -3 -1 l 4 -12 Z" fill="#c98f07"/>')
    # "Polo" from the keys, travelling toward the ear (up and to the left)
    ear = np.array([306.0, 372.0])
    k0 = np.array([500.0, 785.0])
    ang = np.degrees(np.arctan2(-(ear[1] - k0[1]), ear[0] - k0[0]))   # direction to the ear (math angle)
    for k, r in enumerate((32, 56, 80, 104)):
        a0, a1 = np.radians(ang - 16), np.radians(ang + 16)
        p0 = k0 + r * np.array([np.cos(a0), -np.sin(a0)])
        p1 = k0 + r * np.array([np.cos(a1), -np.sin(a1)])
        s.append(f'<path d="M {p0[0]:.1f} {p0[1]:.1f} A {r} {r} 0 0 0 {p1[0]:.1f} {p1[1]:.1f}" fill="none" stroke="{BLUE}" '
                 f'stroke-width="{6 - k}" stroke-linecap="round" opacity="{0.95 - 0.2 * k:.2f}"/>')
    s.append(f'<text x="540" y="690" font-family="-apple-system, Helvetica Neue, Arial" font-size="30" font-weight="700" fill="{BLUE}" font-style="italic">"Polo!"</text>')
    # body (profile, facing right)
    s.append('<path d="M 230 960 L 236 600 Q 238 500 300 470 L 345 455 Q 400 462 425 495 Q 445 525 442 600 '
             'L 448 700 Q 450 760 440 800 L 446 960 Z" fill="#c9cfd8"/>')
    s.append('<path d="M 306 470 L 304 425 L 342 425 L 345 462 Z" fill="#e3c9b4"/>')          # neck
    s.append('<ellipse cx="326" cy="360" rx="58" ry="70" fill="#e8d1bf"/>')                   # head
    s.append('<path d="M 268 352 Q 262 288 324 286 Q 384 286 384 336 Q 352 316 318 324 Q 296 330 290 362 Z" fill="#3a3330"/>')  # hair
    s.append('<path d="M 381 352 q 15 9 6 22 q -6 2 -9 -2" fill="#e8d1bf"/>')                 # nose
    s.append('<ellipse cx="364" cy="350" rx="4" ry="5" fill="#3a3330"/>')                     # eye
    s.append('<ellipse cx="303" cy="370" rx="11" ry="16" fill="#dcbfa8"/>')                   # ear
    s.append('<rect x="297" y="362" width="13" height="20" rx="6.5" fill="#ffffff" stroke="#aeb6c1" stroke-width="1.5"/>'
             '<rect x="300" y="379" width="5" height="17" rx="2.5" fill="#ffffff" stroke="#aeb6c1" stroke-width="1"/>')  # AirPod
    # arm hanging, hand, Watch
    s.append('<path d="M 300 500 Q 285 620 300 760 L 330 760 Q 322 640 338 520 Z" fill="#b9c0cb"/>')
    s.append('<ellipse cx="315" cy="772" rx="16" ry="19" fill="#e3c9b4"/>')
    s.append('<rect x="301" y="728" width="28" height="32" rx="9" fill="#1e2228"/>')
    # strap over the shoulder, down to the badge
    s.append(f'<path d="M 318 462 Q 380 466 415 500 L {chest_bottom[0] - 4:.0f} {chest_bottom[1] - 34:.0f}" fill="none" stroke="#3d4450" stroke-width="11" stroke-linecap="round"/>')
    # badge: wedge (between chest and phone) + phone leaning out at the top
    s.append(poly([chest_bottom, (chest_bottom[0], top[1]), top], ORANGE))
    ph = [chest_bottom, top, top + 7 * out_n, chest_bottom + 7 * out_n]
    s.append(poly(ph, PHONE_TOP))
    s.append(f'<circle cx="{cam[0]:.1f}" cy="{cam[1]:.1f}" r="4.5" fill="#0c0e11"/>')
    return "\n".join(s)


def svg():
    head = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f6f7f9"/><stop offset="1" stop-color="#e9ecf0"/></linearGradient>
  <linearGradient id="cone" x1="0" y1="0" x2="0.6" y2="1"><stop offset="0" stop-color="{BLUE}" stop-opacity="0.30"/><stop offset="1" stop-color="{BLUE}" stop-opacity="0.04"/></linearGradient>
</defs>
<rect width="{W}" height="{H}" fill="url(#bg)"/>
<text x="80" y="110" font-family="-apple-system, Helvetica Neue, Arial" font-size="58" font-weight="800" fill="{INK}">Marco Badge</text>
<text x="82" y="160" font-family="-apple-system, Helvetica Neue, Arial" font-size="26" fill="{SUB}">A memory you wear. It sees where things go, so when you ask, they answer.</text>
<line x1="80" y1="960" x2="760" y2="960" stroke="#c8ced6" stroke-width="2"/>
'''
    foot = (f'<text x="860" y="905" font-family="-apple-system, Helvetica Neue, Arial" font-size="15" fill="{SUB}">'
            "iPhone Pro on a 30° wedge · edge-clamp cradle · magnetic strap clip · ≈300 g · to scale</text></svg>")
    return head + person_svg() + "\n" + badge_svg() + "\n" + foot


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg())
    print(OUT)
