"""Read-only investigation of live sessions on the server: what Marco took for each item, how dark and sharp the frames
were, how ARKit tracked, and what happened at every touch. It changes nothing: it only reads the data folder and the
log, and writes to --out. Needs numpy and Pillow (no models, no GPU), so it can run next to the live service.

  journalctl -u marco -o cat --since "2026-10-18 10:50" --until "2026-10-18 13:30" > /tmp/marco-live.log
  python tools/investigate_live.py --data /var/lib/marco/data --since "2026-10-18 10:50" --until "2026-10-18 13:30" \
      --log /tmp/marco-live.log --out /tmp/marco-investigation

--since and --until are in the server's local time, the same as journalctl's.

Writes to --out:
  report.md            the findings in words and numbers; read this first
  report.json          the same, for scripts
  sheets/<item>.jpg    every spot each item was placed at, with up to 4 frames, the spot circled in red (what Marco
                       took for the item) and other items placed in that frame circled in other colours
  registry/            each registered item's photo and the crop the detector compares against
"""
import argparse
import collections
import datetime as dt
import io
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from marco import codec, geometry as G  # noqa: E402
from marco.world.memory import World  # noqa: E402

TRANSPOSE = [None, Image.Transpose.ROTATE_270, Image.Transpose.ROTATE_180, Image.Transpose.ROTATE_90]   # brain.py's
LINE = re.compile(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),(\d{3}) marco INFO frame (\S+): (.*)$")
PLACED = re.compile(r"placed at \[([-\d.e]+), ([-\d.e]+), ([-\d.e]+)\], ([\d.]+) m away")
GATES = (("photo+name", "photo+name score"), ("DINOv2", "DINOv2 crop similarity"), ("margin", "margin over the other items"),
         ("colour", "looks different from its photo"))
SPOT_M = 0.30                 # placements this close (3D) are the same spot
HOLD_M = 0.05                 # touch.py HOLD_M: the hand this close to the guided item is "on it"
CELL = 300                    # thumbnail size in the sheets
COLOURS = ["#ff2d2d", "#2d9bff", "#30d158", "#ffd60a", "#bf5af2", "#ff9f0a", "#64d2ff", "#ffffff"]


def local_ts(s):
    """'2026-10-18 10:50' (or with T) in this machine's local time -> epoch seconds."""
    return dt.datetime.fromisoformat(s.replace("T", " ")).timestamp()


def clock(t):
    return dt.datetime.fromtimestamp(t).strftime("%H:%M:%S")


def read_jsonl(path, since, until):
    out = []
    if not path.exists():
        return out
    with open(path, errors="replace") as f:
        for line in f:
            try:
                m = json.loads(line)
            except ValueError:
                continue
            w = m.get("received_wall")
            if isinstance(w, (int, float)) and since <= w <= until:
                out.append(m)
    return out


# ------------------------------------------------------------------ inputs
def load_sessions(data, since, until):
    """Sessions with frames in the window: {sid: dict(dir, frames, phone)}; plus every server->phone message."""
    sessions, out_msgs = {}, []
    for d in sorted((data / "sessions").glob("*")):
        if not d.is_dir():
            continue
        out_msgs += read_jsonl(d / "out.jsonl", since, until)
        frames = read_jsonl(d / "frames.jsonl", since, until)
        if frames:
            phone = []
            for m in read_jsonl(d / "phone.jsonl", since, until):
                if m.get("type") == "hand":                  # keep what's needed: these are ~5 KB each
                    conf = {j.get("name"): float(j.get("conf", 0)) for j in m.get("joints", [])}
                    m = dict(type="hand", received_wall=m["received_wall"], tip=conf.get("indexTip", 0.0),
                             best=max(conf.values(), default=0.0))
                phone.append(m)
            sessions[d.name] = dict(dir=d, frames=sorted(frames, key=lambda m: m["received_wall"]), phone=phone)
    out_msgs.sort(key=lambda m: m["received_wall"])
    return sessions, out_msgs


def parse_log(path):
    rows = []
    for line in open(path, errors="replace"):
        m = LINE.search(line)
        if not m:
            continue
        t = local_ts(m.group(1)) + int(m.group(2)) / 1000
        res = []
        for part in m.group(4).split("; "):
            name, _, what = part.partition(": ")
            p = PLACED.match(what)
            if p:
                res.append(dict(name=name, kind="placed", pos=[float(v) for v in p.groups()[:3]], dist=float(p.group(4))))
            elif what.startswith("present, not placed"):
                res.append(dict(name=name, kind="unplaced", why=what.split(": ", 1)[-1]))
            else:
                res.append(dict(name=name, kind="absent", why=what.split(": ", 1)[-1]))
        rows.append(dict(t=t, frame_id=m.group(3), res=res))
    return rows


def join_log(rows, sessions):
    """Match each log line to its frame: same frame_id, logged 0-6 s after the frame arrived. The best whole-hour
    clock offset is found first, in case the log and the data disagree about the time zone (normally 0)."""
    by_id = collections.defaultdict(list)
    for sid, s in sessions.items():
        for meta in s["frames"]:
            by_id[str(meta["frame_id"])].append((meta["received_wall"], sid, meta))

    def matches(off):
        out = []
        for r in rows:
            c = [x for x in by_id.get(r["frame_id"], []) if 0 <= r["t"] - off - x[0] <= 6]
            if c:
                out.append((r, min(c, key=lambda x: r["t"] - off - x[0])))
        return out
    best = max(range(-14, 15), key=lambda h: len(matches(h * 3600)))
    return matches(best * 3600), best


# ------------------------------------------------------------------ measurements
def frame_quality(jpeg, conf):
    g = np.asarray(Image.open(io.BytesIO(jpeg)).convert("L").reduce(2), np.float32)
    lap = 4 * g[1:-1, 1:-1] - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    c = codec.decode_conf(conf)
    return dict(luma=round(float(g.mean()), 1), sharpness=round(float(lap.var()), 1), lidar_high=round(float((c == 2).mean()), 3))


def photo_quality(im):
    g = np.asarray(im.convert("L").resize((max(1, im.width * 480 // max(im.size)), max(1, im.height * 480 // max(im.size)))), np.float32)
    lap = 4 * g[1:-1, 1:-1] - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return dict(luma=round(float(g.mean()), 1), sharpness=round(float(lap.var()), 1), size=list(im.size))


def pct(xs, q):
    return round(float(np.percentile(xs, q)), 3) if len(xs) else None


def spots(placements):
    """Greedy 3D clustering, per AR map (positions from different maps can't be compared)."""
    out = []
    for p in sorted(placements, key=lambda p: p["t"]):
        near = [s for s in out if s["map_id"] == p["map_id"] and np.linalg.norm(np.subtract(s["centre"], p["pos"])) <= SPOT_M]
        if near:
            s = min(near, key=lambda s: np.linalg.norm(np.subtract(s["centre"], p["pos"])))
            s["members"].append(p)
            s["centre"] = list(np.mean([m["pos"] for m in s["members"]], axis=0))
        else:
            out.append(dict(map_id=p["map_id"], centre=list(p["pos"]), members=[p]))
    return sorted(out, key=lambda s: -len(s["members"]))


def dot_moves(placements):
    """The dashboard dot, replayed through the real world model: every time it jumped, and how far."""
    w, ids, moves = World(), {}, []
    for p in sorted(placements, key=lambda p: p["t"]):
        key = (p["name"], p["map_id"])
        if key not in ids:
            ids[key] = w.add_item(p["name"]).item_id
        for e in w.sighting(ids[key], p["pos"], p["t"]):
            if e["kind"] in ("moved", "put_down"):
                moves.append(dict(name=p["name"], t=clock(p["t"]), metres=round(float(np.linalg.norm(np.subtract(e["position"], e["from_position"]))), 2)))
    return moves


def guidance_runs(phone, out_msgs, names):
    """Each time the phone guided to an item: how close the hand got, whether and when the touch came, and the item's
    state changes on the server meanwhile (a 'missing' item can't be touched)."""
    gs = [m for m in phone if m.get("type") == "guidance" and m.get("item_id")]
    hands = [m for m in phone if m.get("type") == "hand"]
    runs, cur = [], None
    for m in gs:
        t = m["received_wall"]
        if cur and (m["item_id"] != cur["item_id"] or t - cur["t1"] > 5):
            runs.append(cur)
            cur = None
        if cur is None:
            cur = dict(item_id=m["item_id"], t0=t, t1=t, phases=[])
        cur["t1"] = t
        ph = m.get("phase")
        if ph and (not cur["phases"] or cur["phases"][-1] != ph):
            cur["phases"].append(ph)
        if ph in ("off", "touched"):
            runs.append(cur)
            cur = None
    if cur:
        runs.append(cur)
    out = []
    for r in runs:
        a, b = r["t0"] - 1, r["t1"] + 3
        iid = r["item_id"]
        prox = [(m["received_wall"], m["distance_m"]) for m in out_msgs
                if m.get("type") == "hand_proximity" and m.get("item_id") == iid and a <= m["received_wall"] <= b]
        touches = [m for m in out_msgs if m.get("type") == "touch" and a <= m["received_wall"] <= b]
        events = [f"{clock(m['received_wall'])} {m.get('kind')}" for m in out_msgs
                  if m.get("type") == "event" and m.get("item_id") == iid and r["t0"] - 30 <= m["received_wall"] <= b]
        on = [t for t, d in prox if d <= HOLD_M]
        held = sum(min(t2 - t1, 0.2) for (t1, d1), (t2, _) in zip(prox, prox[1:]) if d1 <= HOLD_M)
        hs = [h for h in hands if a <= h["received_wall"] <= b]
        gaps = sum(1 for h1, h2 in zip(hs, hs[1:]) if h2["received_wall"] - h1["received_wall"] > 0.25)
        first_touch = touches[0] if touches else None
        out.append(dict(
            item=names.get(iid, iid), start=clock(r["t0"]), seconds=round(r["t1"] - r["t0"], 1), phases=r["phases"],
            closest_hand_m=round(min((d for _, d in prox), default=float("nan")), 3) if prox else None,
            seconds_hand_within_5cm=round(held, 2), first_within_5cm=clock(on[0]) if on else None,
            touch=None if first_touch is None else dict(
                at=clock(first_touch["received_wall"]), on_target=first_touch.get("item_id") == iid,
                item=first_touch.get("name") or names.get(first_touch.get("item_id"), first_touch.get("item_id")),
                seconds_after_first_within_5cm=round(first_touch["received_wall"] - on[0], 2) if on else None),
            item_events=events,
            hand_messages=len(hs), hand_gaps_over_250ms=gaps,
            fingertip_hidden_pct=round(100 * float(np.mean([h["tip"] < 0.5 for h in hs])), 1) if hs else None,
            no_usable_joint_pct=round(100 * float(np.mean([h["best"] < 0.3 for h in hs])), 1) if hs else None))
    return out


# ------------------------------------------------------------------ pictures
def thumb(sdir, meta, marks):
    """The frame as Marco saw it (upright), with each (pos, colour, text) circled where it was placed."""
    base = sdir / "frames" / f"{int(meta['frame_id']):06d}"
    im = Image.open(base.with_suffix(".jpg")).convert("RGB")
    T, K = G.mat4(meta["camera_transform"]), G.mat3(meta["intrinsics"])
    W, H = meta["image_resolution"]
    s = float(meta.get("jpeg_scale", im.width / W))
    fr = G.Frame(T, K, (W, H), codec.decode_depth(base.with_suffix(".depth").read_bytes()),
                 codec.decode_conf(base.with_suffix(".conf").read_bytes()))
    k = G.upright_turns(T)
    pts = []
    for pos, colour, text in marks:
        uv, z = fr.project(np.asarray(pos, float)[None])
        if float(z[0]) <= 0.05:
            continue
        x, y = G.rotate_point(float(uv[0][0]) * s, float(uv[0][1]) * s, k, im.width, im.height)
        pts.append((x, y, max(0.10 * K[0, 0] * s / float(z[0]), 6), colour, text))
    up = im.transpose(TRANSPOSE[k]) if k else im
    f = CELL / max(up.size)
    up = up.resize((max(1, int(up.width * f)), max(1, int(up.height * f))))
    d = ImageDraw.Draw(up)
    for x, y, r, colour, text in pts:
        x, y, r = x * f, y * f, max(r * f, 7)
        d.ellipse([x - r, y - r, x + r, y + r], outline=colour, width=3)
        d.text((x + r + 2, y - 6), text, fill=colour)
    return up


def sheet(name, item_spots, sessions, frame_marks, path, per_spot=4, max_spots=10):
    rows = item_spots[:max_spots]
    label_w = 230
    img = Image.new("RGB", (label_w + per_spot * (CELL + 6), max(1, len(rows)) * (CELL + 6)), "#111")
    d = ImageDraw.Draw(img)
    for i, s in enumerate(rows):
        y = i * (CELL + 6)
        mem = s["members"]
        ds = [m["dist"] for m in mem]
        d.text((6, y + 6), f"{name}: spot {i + 1}\n{len(mem)} placements\n{clock(mem[0]['t'])}-{clock(mem[-1]['t'])}\n"
                           f"{min(ds):.1f}-{max(ds):.1f} m from the phone\nheight {s['centre'][1]:+.2f} m\n"
                           f"session {mem[0]['sid'][:14]}", fill="#eee")
        pick = [mem[int(j)] for j in np.unique(np.linspace(0, len(mem) - 1, min(per_spot, len(mem))).round())]
        for j, m in enumerate(pick):
            marks = [(m["pos"], COLOURS[0], f"{name} {clock(m['t'])}")]
            marks += [(o["pos"], COLOURS[1 + q % (len(COLOURS) - 1)], o["name"])
                      for q, o in enumerate(frame_marks.get((m["sid"], m["frame_id"]), [])) if o["name"] != name]
            try:
                img.paste(thumb(sessions[m["sid"]]["dir"], m["meta"], marks), (label_w + j * (CELL + 6), y))
            except (OSError, KeyError, ValueError) as e:
                d.text((label_w + j * (CELL + 6) + 6, y + 6), f"frame unreadable: {e}", fill="#f66")
    img.save(path, quality=82)


# ------------------------------------------------------------------ main
def investigate(data, since, until, log, out):
    out.mkdir(parents=True, exist_ok=True)
    (out / "sheets").mkdir(exist_ok=True)
    (out / "registry").mkdir(exist_ok=True)
    rep = dict(window=[clock(since), clock(until)], data=str(data))
    sessions, out_msgs = load_sessions(data, since, until)

    # Registration: the photos and the crops the detector uses, with their light and sharpness.
    names, reg = {}, []
    idx = data / "registry" / "items.json"
    for r in (json.loads(idx.read_text()) if idx.exists() else []):
        names[r["item_id"]] = r.get("name")
        row = dict(item_id=r["item_id"], name=r.get("name"), source=r.get("source"), photo_kind=r.get("photo_kind"),
                   created=r.get("created_wall"))
        for kind, p in (("photo", data / "registry" / "photos" / f"{r['item_id']}.jpg"),
                        ("template", data / "registry" / "templates" / f"{r['item_id']}.png")):
            if p.exists():
                im = Image.open(p).convert("RGB")
                row[kind] = photo_quality(im)
                im.thumbnail((640, 640))
                im.save(out / "registry" / f"{re.sub(r'[^A-Za-z0-9]+', '_', str(r.get('name')))}_{r['item_id']}_{kind}.jpg", quality=88)
        reg.append(row)
    for m in out_msgs:
        if m.get("item_id") and m.get("name"):
            names.setdefault(m["item_id"], m["name"])
    rep["registry"] = reg

    # Sessions: light, sharpness, LiDAR and ARKit tracking.
    rep["sessions"] = []
    for sid, s in sessions.items():
        q = []
        for meta in s["frames"]:
            base = s["dir"] / "frames" / f"{int(meta['frame_id']):06d}"
            try:
                q.append(frame_quality(base.with_suffix(".jpg").read_bytes(), base.with_suffix(".conf").read_bytes()))
            except OSError:
                pass
        track = collections.Counter(str(m.get("tracking", "?")) for m in s["frames"])
        rep["sessions"].append(dict(
            session=sid, start=clock(s["frames"][0]["received_wall"]), end=clock(s["frames"][-1]["received_wall"]),
            frames=len(s["frames"]), maps=len({m.get("map_id") for m in s["frames"]}), tracking=dict(track),
            luma_median=pct([x["luma"] for x in q], 50), luma_p10=pct([x["luma"] for x in q], 10),
            sharpness_median=pct([x["sharpness"] for x in q], 50), sharpness_p10=pct([x["sharpness"] for x in q], 10),
            lidar_high_conf_median=pct([x["lidar_high"] for x in q], 50),
            finds=[m.get("name") for m in s["phone"] if m.get("type") == "query" and m.get("kind") == "find"]))

    # What Marco took for each item: the log's per-frame results joined to the frames.
    rep["detection"], placements, frame_marks = {}, [], collections.defaultdict(list)
    if log:
        joined, offset_h = join_log(parse_log(log), sessions)
        rep["log"] = dict(lines_matched_to_frames=len(joined), clock_offset_hours=offset_h)
        per = collections.defaultdict(lambda: dict(frames=0, placed=0, unplaced=collections.Counter(), failed=collections.Counter()))
        for r, (_, sid, meta) in joined:
            for x in r["res"]:
                st = per[x["name"]]
                st["frames"] += 1
                if x["kind"] == "placed":
                    st["placed"] += 1
                    p = dict(name=x["name"], pos=x["pos"], dist=x["dist"], t=meta["received_wall"], sid=sid,
                             frame_id=meta["frame_id"], meta=meta, map_id=meta.get("map_id"))
                    placements.append(p)
                    frame_marks[(sid, meta["frame_id"])].append(p)
                elif x["kind"] == "unplaced":
                    st["unplaced"][re.sub(r"[\d.]+ m away", "N m away", x["why"])] += 1
                else:
                    for short, text in GATES:
                        if text in x["why"]:
                            st["failed"][short] += 1
        moves = dot_moves(placements)
        for name, st in per.items():
            mine = [p for p in placements if p["name"] == name]
            sp = spots(mine)
            safe = re.sub(r"[^A-Za-z0-9]+", "_", name)
            if sp:
                sheet(name, sp, sessions, frame_marks, out / "sheets" / f"{safe}.jpg")
            rep["detection"][name] = dict(
                frames_checked=st["frames"], placed=st["placed"], placed_pct=round(100 * st["placed"] / max(st["frames"], 1), 1),
                present_but_not_placed=dict(st["unplaced"]), gate_failures=dict(st["failed"]), spots=len(sp),
                top_spots=[dict(placements=len(s["members"]), centre=[round(v, 2) for v in s["centre"]],
                                first=clock(s["members"][0]["t"]), last=clock(s["members"][-1]["t"])) for s in sp[:10]],
                dot_moves=[m for m in moves if m["name"] == name], sheet=f"sheets/{safe}.jpg" if sp else None)

    # Touches.
    rep["guidance"] = []
    for sid, s in sessions.items():
        rep["guidance"] += [dict(session=sid, **g) for g in guidance_runs(s["phone"], out_msgs, names)]

    (out / "report.json").write_text(json.dumps(rep, indent=1, default=str))
    (out / "report.md").write_text(markdown(rep))
    return rep


def markdown(rep):
    L = [f"# Marco live investigation, {rep['window'][0]}-{rep['window'][1]} (server local time)", ""]
    L += ["## Sessions: light, sharpness, LiDAR, tracking",
          "luma: 0 black to 255 white (indoor night is often under 60); sharpness: higher is sharper; LiDAR: share of "
          "high-confidence depth.", ""]
    for s in rep["sessions"]:
        L.append(f"- {s['session']}: {s['start']}-{s['end']}, {s['frames']} frames, {s['maps']} AR map(s); luma median "
                 f"{s['luma_median']} (p10 {s['luma_p10']}); sharpness median {s['sharpness_median']} (p10 "
                 f"{s['sharpness_p10']}); LiDAR {s['lidar_high_conf_median']}; tracking {s['tracking']}; finds {s['finds']}")
    L += ["", "## Registered items (photos and crops in registry/)", ""]
    for r in rep["registry"]:
        L.append(f"- {r['name']} ({r['source']}, {r.get('photo_kind')}): photo {r.get('photo')}, crop {r.get('template')}")
    if rep.get("log"):
        L += ["", f"## What Marco took for each item ({rep['log']['lines_matched_to_frames']} log lines matched to frames)",
              "Open the sheet: each row is one spot the item was placed at; the red circle is where it was placed (the base "
              "of whatever was taken for the item, about 10 cm across).", ""]
        for name, d in rep["detection"].items():
            L.append(f"- **{name}**: placed in {d['placed']} of {d['frames_checked']} frames ({d['placed_pct']} %), at "
                     f"{d['spots']} spots; the dashboard dot moved {len(d['dot_moves'])} times; present but not placed "
                     f"{d['present_but_not_placed']}; refused by {d['gate_failures']}; sheet {d['sheet']}")
    L += ["", "## Every guidance run and its touch",
          "A touch needs the hand within 5 cm of the item (held) or the fingertip on it. A 'missing' item can't be "
          "touched.", ""]
    for g in rep["guidance"]:
        L.append(f"- {g['start']} {g['item']} ({g['seconds']} s, {' > '.join(g['phases'])}): closest hand {g['closest_hand_m']} m, "
                 f"{g['seconds_hand_within_5cm']} s within 5 cm; touch {g['touch']}; item events {g['item_events']}; "
                 f"hand messages {g['hand_messages']} ({g['hand_gaps_over_250ms']} gaps, fingertip hidden "
                 f"{g['fingertip_hidden_pct']} %, no usable joint {g['no_usable_joint_pct']} %)")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", default="/var/lib/marco/data")
    ap.add_argument("--since", required=True, help="server local time, e.g. '2026-10-18 10:50'")
    ap.add_argument("--until", required=True)
    ap.add_argument("--log", help="journalctl -u marco -o cat output for the same window")
    ap.add_argument("--out", default="/tmp/marco-investigation")
    a = ap.parse_args(argv)
    rep = investigate(Path(a.data), local_ts(a.since), local_ts(a.until), Path(a.log) if a.log else None, Path(a.out))
    print(f"{len(rep['sessions'])} sessions, {sum(d['placed'] for d in rep['detection'].values())} placements, "
          f"{len(rep['guidance'])} guidance runs -> {a.out}/report.md")


if __name__ == "__main__":
    main()
