"""Scaled concept illustration of the "Marco Badge" chest piece (side view with camera FOV,
front view, exploded stack). Output: reports/figures/marco_badge_concept.png

Geometry is real: iPhone 15 Pro 146.6 x 70.6 x 8.25 mm, ARKit wide camera 62 deg vertical FOV in
portrait, 30 deg downward wedge, chest camera at 1.30 m, table 0.75 m, typical adult 1.75 m.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle, Wedge  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "reports" / "figures" / "marco_badge_concept.png"
INK = "#2b2f36"
SKIN = "#d9dde3"
BODY = "#c3c9d2"
STRAP = "#3d4450"
WEDGE = "#f29f38"
PHONE = "#1f2329"
GLASS = "#5b8def"
FOV = "#5b8def"
NOTE = "#5c6470"
TILT = np.radians(30)
PH, PW, PT = 0.1466, 0.0706, 0.00825


def person_side(ax):
    # legs, torso, neck, head (facing +x)
    ax.add_patch(Polygon([(-0.09, 0.0), (-0.02, 0.0), (0.0, 0.92), (-0.11, 0.92)], color=BODY, zorder=1))
    ax.add_patch(Polygon([(0.0, 0.0), (0.07, 0.0), (0.06, 0.92), (-0.02, 0.92)], color=BODY, zorder=1))
    torso = [(-0.12, 0.92), (0.09, 0.92), (0.11, 1.10), (0.13, 1.30), (0.12, 1.42), (0.06, 1.50), (-0.06, 1.50), (-0.13, 1.42), (-0.14, 1.20)]
    ax.add_patch(Polygon(torso, color=BODY, zorder=2))
    ax.add_patch(Rectangle((-0.035, 1.48), 0.06, 0.06, color=SKIN, zorder=2))
    ax.add_patch(Circle((0.0, 1.635), 0.105, color=SKIN, zorder=3))
    ax.add_patch(Polygon([(0.095, 1.64), (0.125, 1.61), (0.098, 1.60)], color=SKIN, zorder=3))  # nose
    # arm hanging
    ax.add_patch(Polygon([(-0.06, 1.44), (0.0, 1.44), (0.03, 1.05), (-0.01, 1.04)], color="#b3bac5", zorder=2))
    # AirPod
    ax.add_patch(FancyBboxPatch((-0.012, 1.615), 0.018, 0.028, boxstyle="round,pad=0.004", color="white", ec=INK, lw=0.6, zorder=6))
    # optional glasses (dashed)
    ax.plot([0.035, 0.105], [1.665, 1.665], color=GLASS, lw=1.6, ls=(0, (3, 2)), zorder=6)
    ax.add_patch(Circle((0.09, 1.66), 0.018, fill=False, ec=GLASS, lw=1.2, ls=(0, (2, 2)), zorder=6))
    # cross-body strap (side view: passes over shoulder, down the front to the badge)
    ax.plot([-0.02, 0.06, 0.125], [1.50, 1.45, 1.36], color=STRAP, lw=3.0, solid_capstyle="round", zorder=4)


def badge_side(ax):
    b = np.array([0.132, 1.235])               # bottom of phone, resting on the chest
    up = np.array([np.sin(TILT), np.cos(TILT)])  # phone's long axis, top leaning forward
    out = np.array([np.cos(TILT), -np.sin(TILT)])  # outward normal (camera side)
    top = b + PH * up
    # wedge between chest (vertical x=0.13) and the phone's screen side
    ax.add_patch(Polygon([b, (0.13, b[1]), (0.13, top[1] + 0.004), top], color=WEDGE, zorder=5))
    phone = [b, top, top + PT * out, b + PT * out]
    ax.add_patch(Polygon(phone, color=PHONE, zorder=6))
    # MagSafe battery on the outward back, below the camera module
    bat0 = b + 0.012 * up + PT * out
    ax.add_patch(Polygon([bat0, bat0 + 0.085 * up, bat0 + 0.085 * up + 0.011 * out, bat0 + 0.011 * out], color="#e9ecf0", ec=INK, lw=0.5, zorder=6))
    cam = top - 0.018 * up + (PT + 0.002) * out
    ax.add_patch(Circle(cam, 0.006, color="#0d0f12", zorder=7))
    return cam


def fov(ax, cam, reach=1.6):
    half = np.radians(31)  # portrait vertical FOV 62 deg
    axis = -TILT
    lo, hi = axis - half, axis + half
    pts = [cam]
    for a in np.linspace(hi, lo, 80):
        d = np.array([np.cos(a), np.sin(a)])
        t = reach
        if d[1] < 0:
            t = min(t, (0 - cam[1]) / d[1])
            t_tab = (0.75 - cam[1]) / d[1]
            q = cam + t_tab * d
            if 0.30 <= q[0] <= 1.25 and t_tab < t:
                t = t_tab
        pts.append(cam + t * d)
    ax.add_patch(Polygon(pts, color=FOV, alpha=0.12, zorder=0, lw=0))
    for a in (hi, lo):
        d = np.array([np.cos(a), np.sin(a)])
        ax.plot([cam[0], cam[0] + 0.45 * d[0]], [cam[1], cam[1] + 0.45 * d[1]], color=FOV, lw=0.9, alpha=0.8, zorder=1)
    d = np.array([np.cos(axis), np.sin(axis)])
    ax.plot([cam[0], cam[0] + 0.9 * d[0]], [cam[1], cam[1] + 0.9 * d[1]], color=FOV, lw=1.0, ls=(0, (4, 3)), zorder=1)


def table(ax):
    ax.add_patch(Rectangle((0.30, 0.72), 0.95, 0.03, color="#9aa3ad", zorder=1))
    for x in (0.33, 1.20):
        ax.add_patch(Rectangle((x, 0.0), 0.025, 0.72, color="#b7bec7", zorder=1))
    ax.add_patch(FancyBboxPatch((0.43, 0.752), 0.07, 0.012, boxstyle="round,pad=0.004", color="#e0a40b", zorder=3))  # keys
    ax.add_patch(Rectangle((0.80, 0.75), 0.07, 0.25, color="#4fa3a5", zorder=3))  # bottle
    ax.text(0.465, 0.79, "keys", ha="center", fontsize=7, color=NOTE)
    ax.text(0.835, 1.03, "bottle", ha="center", fontsize=7, color=NOTE)


def side_view(ax):
    ax.set_title("Side view (to scale)", fontsize=11, color=INK, loc="left")
    ax.axhline(0, color="#9aa3ad", lw=1)
    person_side(ax)
    cam = badge_side(ax)
    fov(ax, cam)
    table(ax)
    kw = dict(fontsize=8, color=INK, arrowprops=dict(arrowstyle="-", color=NOTE, lw=0.7))
    ax.annotate("Marco Badge on a 30° wedge\n(screen faces the chest, camera + LiDAR out)", xy=(0.17, 1.33), xytext=(0.42, 1.55), **kw)
    ax.annotate("camera view: 62° tall,\naimed 30° down", xy=(0.55, 1.05), xytext=(0.70, 1.28), **kw)
    ax.annotate("sees the table top from 0.3 m,\nso your hand + the item are in view", xy=(0.47, 0.76), xytext=(0.52, 0.42), **kw)
    ax.annotate("sees the floor from ~0.7 m\n(dropped things, bags in the way)", xy=(1.45, 0.0), xytext=(0.95, 0.30), **kw)
    ax.annotate("AirPods Pro (or Ray-Ban Meta,\ndashed: open-ear audio + eye-level camera)", xy=(0.0, 1.63), xytext=(-0.55, 1.86), **kw)
    ax.annotate("cross-body strap", xy=(0.06, 1.45), xytext=(-0.55, 1.40), **kw)
    ax.annotate("1.30 m", xy=(-0.30, 1.30), xytext=(-0.30, 1.30), fontsize=7, color=NOTE, va="center")
    ax.plot([-0.22, 0.12], [1.30, 1.30], color=NOTE, lw=0.5, ls=":")
    ax.set_xlim(-0.65, 1.75)
    ax.set_ylim(-0.05, 2.0)
    ax.set_aspect("equal")
    ax.axis("off")


def front_view(ax):
    ax.set_title("Front view", fontsize=11, color=INK, loc="left")
    ax.add_patch(Polygon([(-0.20, 0.92), (0.20, 0.92), (0.22, 1.40), (0.16, 1.48), (-0.16, 1.48), (-0.22, 1.40)], color=BODY, zorder=1))
    ax.add_patch(Rectangle((-0.035, 1.48), 0.07, 0.06, color=SKIN, zorder=1))
    ax.add_patch(Circle((0, 1.64), 0.10, color=SKIN, zorder=2))
    for sx in (-1, 1):
        ax.add_patch(Polygon([(sx * 0.20, 1.44), (sx * 0.25, 1.40), (sx * 0.27, 1.02), (sx * 0.22, 1.02)], color="#b3bac5", zorder=1))
        ax.add_patch(FancyBboxPatch((sx * 0.104 - 0.009, 1.615), 0.018, 0.03, boxstyle="round,pad=0.004", color="white", ec=INK, lw=0.6, zorder=3))
    # Apple Watch on left wrist
    ax.add_patch(FancyBboxPatch((-0.268, 1.035), 0.04, 0.045, boxstyle="round,pad=0.005", color=PHONE, zorder=3))
    ax.annotate("Apple Watch (optional):\nDouble Tap = 'Marco', haptic taps", xy=(-0.25, 1.06), xytext=(-0.62, 0.80), fontsize=8, color=INK,
                arrowprops=dict(arrowstyle="-", color=NOTE, lw=0.7))
    # strap: left shoulder to right hip
    ax.plot([-0.15, 0.20], [1.47, 0.95], color=STRAP, lw=6, solid_capstyle="round", zorder=3)
    # badge (phone back faces out; foreshortened by the 30 deg tilt)
    h = PH * np.cos(TILT)
    x0, y0 = -PW / 2, 1.235
    ax.add_patch(FancyBboxPatch((x0 - 0.006, y0 - 0.006), PW + 0.012, h + 0.012, boxstyle="round,pad=0.006", color=WEDGE, zorder=4))
    ax.add_patch(FancyBboxPatch((x0, y0), PW, h, boxstyle="round,pad=0.008", color=PHONE, zorder=5))
    # camera module top-left, with three lenses + LiDAR
    ax.add_patch(FancyBboxPatch((x0 + 0.004, y0 + h - 0.036), 0.032, 0.032, boxstyle="round,pad=0.004", color="#3a3f47", zorder=6))
    for cx, cy, r in ((0.012, -0.012, 0.0055), (0.012, -0.027, 0.0055), (0.027, -0.0195, 0.0055)):
        ax.add_patch(Circle((x0 + 0.004 + cx, y0 + h + cy), r, color="#0d0f12", zorder=7))
    ax.add_patch(Circle((x0 + 0.031, y0 + h - 0.008), 0.0025, color="#6b7280", zorder=7))
    # MagSafe battery below the camera module
    ax.add_patch(FancyBboxPatch((x0 + 0.007, y0 + 0.010), PW - 0.014, 0.068, boxstyle="round,pad=0.006", color="#e9ecf0", ec=INK, lw=0.5, zorder=6))
    ax.add_patch(Circle((x0 + PW / 2, y0 + 0.044), 0.018, fill=False, ec="#b8bec8", lw=1.0, zorder=7))
    # privacy LED glow along the edge
    ax.add_patch(FancyBboxPatch((x0 - 0.0105, y0 - 0.0105), PW + 0.021, h + 0.021, boxstyle="round,pad=0.006", fill=False, ec="#ff5a5f", lw=1.0, alpha=0.8, zorder=4))
    kw = dict(fontsize=8, color=INK, arrowprops=dict(arrowstyle="-", color=NOTE, lw=0.7))
    ax.annotate("Marco Badge at the sternum\n(see close-up below)", xy=(x0 + PW + 0.01, y0 + h / 2), xytext=(0.17, 1.42), **kw)
    ax.annotate("cross-body strap\n(or clip to a bag strap)", xy=(0.12, 1.07), xytext=(0.17, 1.00), **kw)
    ax.set_xlim(-0.65, 0.65)
    ax.set_ylim(0.75, 1.80)
    ax.set_aspect("equal")
    ax.axis("off")


def closeup(ax):
    """Badge, front, in millimetres."""
    ax.set_title("Badge close-up (front, mm)", fontsize=11, color=INK, loc="left")
    W, H = 70.6, 146.6 * np.cos(TILT)
    ax.add_patch(FancyBboxPatch((-W / 2 - 9, -9), W + 18, H + 18, boxstyle="round,pad=3", fill=False, ec="#ff5a5f", lw=2.0, alpha=0.85))
    ax.add_patch(FancyBboxPatch((-W / 2 - 5, -5), W + 10, H + 10, boxstyle="round,pad=3", color=WEDGE))
    ax.add_patch(FancyBboxPatch((-W / 2, 0), W, H, boxstyle="round,pad=6", color=PHONE))
    cx0, cy0 = -W / 2 + 4, H - 40
    ax.add_patch(FancyBboxPatch((cx0, cy0), 34, 34, boxstyle="round,pad=4", color="#3a3f47"))
    for x, y in ((9, 25), (9, 9), (25, 17)):
        ax.add_patch(Circle((cx0 + x, cy0 + y), 6.5, color="#0d0f12"))
        ax.add_patch(Circle((cx0 + x, cy0 + y), 2.5, color="#2c3440"))
    ax.add_patch(Circle((cx0 + 28, cy0 + 30), 2.6, color="#7a828f"))
    ax.text(cx0 + 33, cy0 + 37, "LiDAR", fontsize=6.5, color="#c7ccd4")
    ax.add_patch(FancyBboxPatch((-W / 2 + 7, 8), W - 14, 66, boxstyle="round,pad=4", color="#eef0f3", ec=INK, lw=0.6))
    ax.add_patch(Circle((0, 44), 22, fill=False, ec="#c3c9d2", lw=1.2))
    ax.text(0, 16, "MARCO", ha="center", fontsize=8, color=NOTE, weight="bold")
    ax.add_patch(Rectangle((W / 2 + 0.5, H - 58), 3.0, 9, color="#ff9f0a"))  # Action button
    kw = dict(fontsize=7.5, color=INK, arrowprops=dict(arrowstyle="-", color=NOTE, lw=0.7))
    ax.annotate("3 cameras + LiDAR\n(never covered)", xy=(cx0 + 20, cy0 + 30), xytext=(48, H + 10), **kw)
    ax.annotate("Action button:\npress = 'Marco'", xy=(W / 2 + 2, H - 53), xytext=(48, H - 52), **kw)
    ax.annotate("MagSafe battery", xy=(W / 2 - 8, 40), xytext=(48, 30), **kw)
    ax.annotate("30° wedge", xy=(-W / 2 - 4, 60), xytext=(-W / 2 - 20, 80), ha="right", **kw)
    ax.annotate("red glow =\ncamera on", xy=(-W / 2 - 9, 15), xytext=(-W / 2 - 20, 22), ha="right", **kw)
    ax.set_xlim(-W / 2 - 115, W / 2 + 95)
    ax.set_ylim(-20, H + 30)
    ax.set_aspect("equal")
    ax.axis("off")


def exploded(ax):
    """Side, in millimetres, with gaps between the parts."""
    ax.set_title("The stack (exploded side view, mm)", fontsize=11, color=INK, loc="left")
    parts = [("strap", STRAP, 4, 30, 58), ("quick-release\nmagnet clip", "#8a93a0", 8, 40, 53), ("30° wedge\n(3D-printed)", WEDGE, None, 146.6, 0),
             ("edge-clamp\ncradle", "#6b7280", 4, 150, -2), ("iPhone Pro\n(screen in)", PHONE, 8.25, 146.6, 0), ("MagSafe\nbattery", "#eef0f3", 11, 90, 12)]
    x = 0.0
    for name, col, th, h, y0 in parts:
        if th is None:
            w = h * np.tan(TILT) * 0.5
            ax.add_patch(Polygon([(x, 0), (x, h), (x + w, h)], color=col))
        else:
            w = th
            ax.add_patch(Rectangle((x, y0), w, h, color=col, ec=INK, lw=0.5))
        below = parts.index((name, col, th, h, y0)) % 2 == 0
        ax.text(x + w / 2, -10 if below else 178, name, ha="center", va="top" if below else "bottom", fontsize=7.2, color=INK)
        x += w + 34
    ax.text(-4, 160, "← chest", ha="left", fontsize=7.5, color=NOTE)
    ax.text(x - 30, 160, "outward →", ha="right", fontsize=7.5, color=NOTE)
    ax.text(0, -52, "≈300 g with battery; the top sticks out ≈7 cm (portrait).\n"
            "Landscape option sticks out only ≈3.5 cm but sees fewer put-downs (42% vs 49%).", fontsize=7.8, color=NOTE, va="top")
    ax.set_xlim(-10, x)
    ax.set_ylim(-80, 215)
    ax.set_aspect("equal")
    ax.axis("off")


if __name__ == "__main__":
    fig = plt.figure(figsize=(16, 10), facecolor="white")
    gs = fig.add_gridspec(2, 3, width_ratios=[1.6, 0.62, 0.62], height_ratios=[1.0, 0.82], wspace=0.04, hspace=0.06)
    side_view(fig.add_subplot(gs[:, 0]))
    front_view(fig.add_subplot(gs[0, 1:]))
    closeup(fig.add_subplot(gs[1, 1]))
    exploded(fig.add_subplot(gs[1, 2]))
    fig.suptitle("Marco Badge: chest-worn concept", x=0.06, ha="left", fontsize=16, color=INK, weight="bold")
    fig.text(0.06, 0.915, "The phone maps and remembers; AirPods or glasses are the ears; the Watch is optional. "
             "Geometry is to scale (iPhone 15 Pro, ARKit wide camera, 30° wedge).", fontsize=9.5, color=NOTE)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=170, bbox_inches="tight")
    fig.savefig(OUT.with_suffix(".svg"), bbox_inches="tight")  # vector
    fig.savefig(OUT.with_suffix(".pdf"), bbox_inches="tight")  # vector
    print(OUT, OUT.with_suffix(".svg"), OUT.with_suffix(".pdf"))
