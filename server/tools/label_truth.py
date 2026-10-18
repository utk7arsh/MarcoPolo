"""Ground truth for a real recording: click the middle of each item once, in a frame where it is 1-2 m away with
nothing in front of it (not your hand), and LiDAR depth turns the click into a world position (truth.json). eval_detection.py then projects that
point into every frame (with an occlusion check) to know where each item should be seen. Items must stay put while
recording. The stored position is the footprint (where the item stands), like the server's placements: the clicked
point lowered by half the item's size.

  python tools/label_truth.py data/sessions/<id>                  # a window: n / p = next / previous frame,
                                                                  # click the middle of an item, type its name; q ends
  python tools/label_truth.py data/sessions/<id> --click keys=12:960,700 --size keys=0.08
                                                                  # scripted: frame_id:u,v in sensor pixels
"""
import argparse
import io
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from marco import codec, geometry as G  # noqa: E402
from marco.session import Session  # noqa: E402

DEFAULT_SIZE = {"keys": 0.08, "wallet": 0.10, "mug": 0.10, "bottle": 0.22, "jar": 0.10, "remote": 0.18}


def frame_of(ses, meta):
    _, d, c = ses.frame_bytes(meta)
    return G.Frame(G.mat4(meta["camera_transform"]), G.mat3(meta["intrinsics"]), tuple(meta["image_resolution"]),
                   codec.decode_depth(d), codec.decode_conf(c))


def position_from_click(fr, u, v, r=2):
    """World point under sensor pixel (u, v): the nearest depth cluster around it (the item is the closest surface
    there; a plain median mixes in the table or wall behind a small item), unprojected. None without depth."""
    iu, iv = int(u * fr.sx), int(v * fr.sy)
    win = fr.depth[max(iv - r, 0): iv + r + 1, max(iu - r, 0): iu + r + 1]
    cw = fr.conf[max(iv - r, 0): iv + r + 1, max(iu - r, 0): iu + r + 1]
    z = win[(cw >= 1) & np.isfinite(win)]
    if z.size == 0:
        return None
    near = z[z <= np.percentile(z, 25) + 0.03]
    return fr.unproject(u, v, float(np.median(near)))


def add_item(session_dir, name, position, size, source):
    p = Path(session_dir) / "truth.json"
    truth = json.loads(p.read_text()) if p.exists() else dict(items={}, touches=[])
    truth.setdefault("items", {})[name] = dict(position=[round(float(x), 4) for x in position], size=float(size), labelled_from=source)
    truth.setdefault("note", "position = where the item meets its surface, from one click + LiDAR (tools/label_truth.py)")
    p.write_text(json.dumps(truth, indent=1))
    return truth


def label_click(ses, name, frame_id, u, v, size=None):
    meta = next((m for m in ses.frames if m["frame_id"] == frame_id), None)
    if meta is None:
        raise SystemExit(f"no frame {frame_id}")
    pos = position_from_click(frame_of(ses, meta), u, v)
    if pos is None:
        raise SystemExit(f"no LiDAR depth at frame {frame_id} ({u:.0f}, {v:.0f}): click a nearby spot")
    size = size or DEFAULT_SIZE.get(name, 0.10)
    foot = pos - np.array([0.0, size / 2, 0.0])
    return add_item(ses.dir, name, foot, size, dict(frame_id=frame_id, u=round(u, 1), v=round(v, 1)))


def interactive(ses, sizes):
    import matplotlib.pyplot as plt
    from PIL import Image
    state = dict(i=0)
    fig, ax = plt.subplots(figsize=(8, 10))

    def show():
        meta = ses.frames[state["i"]]
        jpeg, _, _ = ses.frame_bytes(meta)
        im = Image.open(io.BytesIO(jpeg)).convert("RGB")
        k = G.upright_turns(G.mat4(meta["camera_transform"]))
        state.update(meta=meta, k=k, jw=im.width, jh=im.height, scale=float(meta.get("jpeg_scale", 0.5)))
        up = im.transpose([None, Image.Transpose.ROTATE_270, Image.Transpose.ROTATE_180, Image.Transpose.ROTATE_90][k]) if k else im
        ax.clear()
        ax.imshow(up)
        ax.set_title(f"frame {meta['frame_id']} ({state['i'] + 1}/{len(ses.frames)}): click the middle of an item; n/p, q")
        fig.canvas.draw_idle()

    def on_key(ev):
        if ev.key in ("n", "right"):
            state["i"] = min(state["i"] + 1, len(ses.frames) - 1)
        elif ev.key in ("p", "left"):
            state["i"] = max(state["i"] - 1, 0)
        elif ev.key == "q":
            plt.close(fig)
            return
        show()

    def on_click(ev):
        if ev.inaxes is not ax or ev.xdata is None:
            return
        x, y = G.unrotate_point(ev.xdata, ev.ydata, state["k"], state["jw"], state["jh"])
        u, v = x / state["scale"], y / state["scale"]
        name = input(f"item at frame {state['meta']['frame_id']} ({u:.0f}, {v:.0f}) - name (empty to skip): ").strip()
        if not name:
            return
        try:
            truth = label_click(ses, name, state["meta"]["frame_id"], u, v, sizes.get(name))
            print(f"  {name}: {truth['items'][name]['position']}")
            ax.plot(ev.xdata, ev.ydata, "g+", ms=18, mew=3)
            ax.annotate(name, (ev.xdata, ev.ydata), color="lime", fontsize=12, xytext=(8, -8), textcoords="offset points")
            fig.canvas.draw_idle()
        except SystemExit as e:
            print(f"  {e}")

    fig.canvas.mpl_connect("key_press_event", on_key)
    fig.canvas.mpl_connect("button_press_event", on_click)
    show()
    plt.show()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--click", nargs="*", default=[], help="name=frame_id:u,v (sensor pixels)")
    ap.add_argument("--size", nargs="*", default=[], help="name=metres (item height/width, for visibility)")
    a = ap.parse_args()
    ses = Session(a.session)
    sizes = {k: float(v) for k, v in (s.split("=", 1) for s in a.size)}
    if not a.click:
        interactive(ses, sizes)
    for c in a.click:
        name, rest = c.split("=", 1)
        fid, uv = rest.split(":")
        u, v = map(float, uv.split(","))
        t = label_click(ses, name, int(fid), u, v, sizes.get(name))
        print(f"{name}: {t['items'][name]['position']}")
