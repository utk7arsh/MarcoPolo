"""Charts for POC 22 (find a registered item).

Figure 1: which model? accuracy on two tasks + deployment latency (registration encoded once, one full phone frame).
Figure 2: one-shot registration with OWLv2: how much the one photo matters (from registration_study.py).

Palette: reference categorical slots 1-2 (validated with the dataviz validator: CVD dE 24.7, contrast >= 3:1).
Text uses ink tokens; the latency panel is a single series in neutral ink (it is not a task).
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
R = json.loads((ROOT / "reports" / "poc22_registered_find.json").read_text())
FIG = ROOT / "reports" / "figures"
LAT = R["server_mode_latency"]["per_method_ms"]

SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1"
T1, T2 = "#2a78d6", "#eb6834"   # task 1 (blue), task 2 (orange)
TASKS = [("own_clutter", T1, "Task 1: find my item in my own clutter"),
         ("lookalikes", T2, "Task 2: find MY item among other people's look-alikes")]

MODELS = [  # one-shot registration: one photo (or just the name); None = gap between families
    ("owlv2_image", "OWLv2 - 1 photo"),
    ("owlv2_img1_name", "OWLv2 - 1 photo + name"),
    ("owlv2_text", "OWLv2 - name only"),
    None,
    ("yoloe26x_vp", "YOLOE-26x - 1 photo"),
    ("yoloe26x_text", "YOLOE-26x - name only"),
    None,
    ("yoloe26l_vp", "YOLOE-26l - 1 photo"),
    ("yoloe26l_text", "YOLOE-26l - name only"),
    None,
    ("yoloe26s_vp", "YOLOE-26s - 1 photo"),
    None,
    ("text_then_match1", "Name finds candidates, DINOv2 matches the photo"),
    ("propose_match1", "Box everything, DINOv2 matches the photo"),
]
S = json.loads((ROOT / "reports" / "poc22_registration_study.json").read_text())
PHOTO = [  # OWLv2, one photo: which photo?
    ("first named photo", "the first photo the name detector boxed"),
    ("single photo the name detector boxed", "any photo the name detector boxed"),
    ("single photo it could not box", "a photo it could not box (blurry, cut off, empty)"),
    ("name only", "no photo, just the name"),
]


def style():
    plt.rcParams.update({"font.family": "Helvetica Neue", "font.size": 10.5, "text.color": INK, "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": GRID})


def layout(rows, res=R):
    """y positions top-down, with a half-row gap between families."""
    y, ys, keys, labels = 0.0, [], [], []
    for r in rows:
        if r is None:
            y += 0.6
            continue
        if r[0] in res["own_clutter"] and r[0] in res["lookalikes"]:
            ys.append(y); keys.append(r[0]); labels.append(r[1]); y += 1
    return np.array(ys), keys, labels


def accuracy_panel(ax, ys, keys, labels, legend_y, res=R):
    h = 0.36
    for (task, color, name), off in zip(TASKS, (-h / 2 - 0.02, h / 2 + 0.02)):
        v = np.array([res[task][k]["hit_iou50_pct"] if isinstance(res[task][k], dict) else res[task][k] for k in keys])
        ax.barh(ys + off, v, height=h, color=color, label=name, zorder=3)
        for yi, vi in zip(ys + off, v):
            ax.text(vi + 1.2, yi, f"{vi:.0f}%", va="center", fontsize=9.5, color=INK2)
    ax.set_yticks(ys, labels, fontsize=10.5, color=INK)
    ax.set_ylim(ys.max() + 0.7, -0.7)
    ax.set_xlim(0, 108); ax.set_xlabel("Top box correct (IoU >= 0.5), %")
    ax.xaxis.grid(True, color=GRID, lw=0.8, zorder=0); ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.axvline(25, color=MUTED, lw=1, ls=(0, (3, 3)), zorder=2)
    ax.text(25.8, -0.62, "chance in task 2 (1 of 4 tiles)", fontsize=8.5, color=MUTED, va="bottom")
    ax.legend(loc="upper left", frameon=False, fontsize=9.5, ncol=2, bbox_to_anchor=(-0.02, legend_y))


def header(fig, title, sub):
    fig.suptitle(title, x=0.012, y=0.995, ha="left", fontsize=16, fontweight="bold", color=INK)
    fig.text(0.012, 0.935, sub, fontsize=9.5, color=INK2, va="top")


DATA_NOTE = ("ORBIT dataset: 18 real items filmed by blind and low-vision users (keys x4, remotes, wallets, sunglasses, phones, watches, "
             "headphones, cane, purse);\n156 cluttered test frames per task, human-drawn boxes. Frames are only 224 px, so every score is pessimistic. "
             "Registration = one photo of the item and its name, encoded once.")


def figure_models():
    ys, keys, labels = layout(MODELS)
    fig = plt.figure(figsize=(14, 0.42 * len(keys) + 3.2), facecolor=SURFACE)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.6, 0.9], wspace=0.06)
    ax = fig.add_subplot(gs[0]); ax.set_facecolor(SURFACE)
    accuracy_panel(ax, ys, keys, labels, legend_y=-0.095)
    ax.set_title("A  Accuracy", loc="left", fontsize=12, fontweight="bold", color=INK, pad=22)
    bx = fig.add_subplot(gs[1], sharey=ax); bx.set_facecolor(SURFACE)
    lat = np.array([LAT[k] for k in keys])
    bx.barh(ys, lat, height=0.5, color=INK2, zorder=3)
    for yi, v in zip(ys, lat):
        bx.text(v * 1.1, yi, f"{v:.0f} ms", va="center", fontsize=9.5, color=INK2)
    bx.set_xscale("log"); bx.set_xlim(8, 4000)
    bx.tick_params(axis="y", length=0, labelleft=False)
    for s in ("top", "right", "left"):
        bx.spines[s].set_visible(False)
    bx.xaxis.grid(True, which="major", color=GRID, lw=0.8, zorder=0); bx.set_axisbelow(True)
    for x, lab, ha, k in ((1000, "1 fps budget", "right", 0.95), (2000, "0.5 fps", "left", 1.05)):
        bx.axvline(x, color=MUTED, lw=1, ls=(0, (3, 3)), zorder=2)
        bx.text(x * k, -0.62, lab, fontsize=8.5, color=MUTED, va="bottom", ha=ha)
    bx.set_xlabel("Time per camera frame (ms, log scale)\none 1440x1920 phone frame, M3 Pro Mac (PyTorch/MPS, fp32);\na cloud GPU will be faster")
    bx.set_title("B  Latency once registered", loc="left", fontsize=12, fontweight="bold", color=INK, pad=22)
    fig.subplots_adjust(top=1 - 1.55 / fig.get_figheight(), bottom=1.5 / fig.get_figheight())
    header(fig, "Finding a registered item: which model?", DATA_NOTE)
    save(fig, "poc22_find_registered_items")


def figure_photo():
    ys, keys, labels = layout(PHOTO, S)
    fig = plt.figure(figsize=(11, 0.5 * len(keys) + 2.9), facecolor=SURFACE)
    ax = fig.add_subplot(111); ax.set_facecolor(SURFACE)
    accuracy_panel(ax, ys, keys, labels, legend_y=-0.16, res=S)
    n_ok, n_bad = S["own_clutter"]["single photo the name detector boxed (n photos)"], S["own_clutter"]["single photo it could not box (n photos)"]
    fig.subplots_adjust(left=0.36, top=1 - 1.05 / fig.get_figheight(), bottom=1.15 / fig.get_figheight())
    header(fig, "One-shot registration with OWLv2: the photo makes or breaks it",
           f"Same 18 items and 156 frames per task. Registration photos from the users' own videos: {n_ok} the name detector could box,\n"
           f"{n_bad} it could not. Rule for the app: if the name detector cannot box the item in the photo, ask for another photo.")
    save(fig, "poc22_one_shot_photo_quality")


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.png", dpi=170, bbox_inches="tight", facecolor=SURFACE)
    fig.savefig(FIG / f"{name}.svg", bbox_inches="tight", facecolor=SURFACE)
    print(FIG / f"{name}.png")


if __name__ == "__main__":
    style()
    figure_models()
    figure_photo()
