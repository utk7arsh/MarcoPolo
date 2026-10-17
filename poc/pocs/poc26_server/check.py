"""POC 26: exercise the server prototype (app.py) in-process: no socket is opened (FastAPI TestClient).

1. Auth fails closed: with no verifier wired and no test bypass, every route answers 403.
2. Registration with the retake loop: for each ORBIT item, try its registration photos in order until the
   server says "ok" (what the app does when it asks for another photo). How many tries, and how good is
   the photo that got accepted (per-photo accuracy from registration_study.py)?
3. Presence thresholds: send every ORBIT test frame to /frames with all 18 items registered; fit thresholds
   for "this item is in the frame" at about 1 % false positives on other people's frames; report what that
   catches, and how often the box is also right.
4. EXIF: a sideways JPEG with an orientation tag must give the same boxes as the upright image.
5. Latency of /frames per 960 px phone-size frame, with 1 and 18 items registered.
6. Latest frame wins: frames arriving faster than the model runs; older ones must be skipped.
"""
import importlib.util
import io
import json
import os
import sys
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("poc22_bench", ROOT / "pocs" / "poc22_registered_find" / "bench.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
sys.path.insert(0, str(HERE))
import app as A  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def jpeg(im, exif=None):
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85, **({"exif": exif} if exif else {}))
    return buf.getvalue()


def main():
    rep = {}
    os.environ.pop("AUTH_TEST_BYPASS", None)
    client = TestClient(A.app)
    r1 = client.get("/items")
    r2 = client.post("/frames", data={"device_id": "x", "frame_id": "1"}, files={"frame": ("f.jpg", b"123", "image/jpeg")})
    rep["1_auth_fail_closed"] = {"GET /items": r1.status_code, "POST /frames": r2.status_code}
    print("1 auth:", rep["1_auth_fail_closed"], flush=True)
    os.environ["AUTH_TEST_BYPASS"] = "1"

    # ---------------- 2. registration with retake loop
    its = B.items()
    study = json.loads((ROOT / "reports" / "poc22_registration_study.json").read_text())["per_item"]["own_clutter"]
    tries, accepted_acc, ids = [], [], {}
    for it in its:
        name = B.NAMES.get(it["obj"], it["obj"].replace("-", " "))
        for k, rf in enumerate(sorted(it["reg"])):          # photos in the order the user took them
            data = (it["regdir"] / rf).read_bytes()
            r = client.post("/items", data={"name": name}, files={"photo": (rf, data, "image/jpeg")}).json()
            if r["quality"] == "ok":
                ids[it["name"]] = r["item_id"]
                tries.append(k + 1)
                slot = it["reg_order"].index(rf) + 1
                accepted_acc.append(study[f"photo {slot}"][it["name"]])
                break
        else:
            tries.append(None)
    got = [t for t in tries if t]
    rep["2_registration_retake_loop"] = dict(items=len(its), registered=len(got), first_photo_ok=sum(t == 1 for t in got),
                                            median_tries=float(np.median(got)), max_tries=max(got),
                                            accepted_photo_accuracy_pct=round(100 * float(np.mean(accepted_acc)), 1))
    print("2 registration:", rep["2_registration_retake_loop"], flush=True)

    # ---------------- 3. presence thresholds on ORBIT frames (all 18 registered)
    users = {it["name"]: it["name"].split("--")[0] for it in its}
    cats = {it["name"]: B.CATEGORY.get(it["obj"], it["obj"]) for it in its}
    id2name = {v: k for k, v in ids.items()}
    rows = []
    fid = 0
    for it in its:
        for path, gt in it["tests"]:
            fid += 1
            r = client.post("/frames", data={"device_id": "orbit", "frame_id": str(fid)},
                            files={"frame": ("f.jpg", Path(path).read_bytes(), "image/jpeg")}).json()
            for d in r["detections"]:
                owner = id2name[d["item_id"]]
                kind = "present" if owner == it["name"] else ("same user" if users[owner] == users[it["name"]] else
                                                             ("look-alike" if cats[owner] == cats[it["name"]] else "other category"))
                rows.append(dict(kind=kind, photo_name=d["photo_name"], dino=d["dino"], vs_others=d["vs_others"],
                                 box_ok=bool(kind == "present" and B.iou(d["box_px"], gt) >= 0.5)))
    pos = [r for r in rows if r["kind"] == "present"]
    neg = [r for r in rows if r["kind"] in ("look-alike", "other category")]
    best = None
    qs = np.linspace(0, 0.99, 34)
    pn = np.array([r["photo_name"] for r in neg]); dn = np.array([r["dino"] for r in neg]); on = np.array([r["vs_others"] for r in neg])
    pp = np.array([r["photo_name"] for r in pos]); dp = np.array([r["dino"] for r in pos]); op = np.array([r["vs_others"] for r in pos])
    for a in np.quantile(pp, qs[:20]):
        for b in np.quantile(dp, qs[:20]):
            for c in np.quantile(op, qs[:20]):
                fp = float(np.mean((pn >= a) & (dn >= b) & (on >= c)))
                if fp <= 0.01:
                    tp = float(np.mean((pp >= a) & (dp >= b) & (op >= c)))
                    if best is None or tp > best[0]:
                        best = (tp, a, b, c, fp)
    tp, a, b, c, fp = best
    A.THRESHOLDS.update(photo_name=float(a), dino=float(b), vs_others=float(c))
    keep = lambda r: r["photo_name"] >= a and r["dino"] >= b and r["vs_others"] >= c
    by = {k: [r for r in rows if r["kind"] == k] for k in ("present", "look-alike", "other category", "same user")}
    rep["3_presence"] = dict(
        thresholds={"photo_name": round(float(a), 3), "dino": round(float(b), 3), "vs_others": round(float(c), 3)},
        caught_pct=round(100 * tp, 1), caught_with_correct_box_pct=round(100 * float(np.mean([keep(r) and r["box_ok"] for r in by["present"]])), 1),
        false_positive_pct={k: round(100 * float(np.mean([keep(r) for r in v])), 1) for k, v in by.items() if k != "present"},
        note="fitted and scored on the same frames (optimistic); same-user frames may genuinely contain the item")
    print("3 presence:", rep["3_presence"], flush=True)

    # ---------------- 4. EXIF orientation
    it = its[0]
    path, gt = it["tests"][0]
    up = Image.open(path).convert("RGB")
    side = up.transpose(Image.Transpose.ROTATE_90)            # sensor-style sideways pixels
    ex = Image.Exif(); ex[0x0112] = 6                          # "rotate 90 CW to display"
    res_up = client.post("/frames", data={"device_id": "exif", "frame_id": "1"}, files={"frame": ("a.jpg", jpeg(up), "image/jpeg")}).json()
    res_side = client.post("/frames", data={"device_id": "exif", "frame_id": "2"}, files={"frame": ("b.jpg", jpeg(side, ex.tobytes()), "image/jpeg")}).json()
    k = ids[it["name"]]
    b1 = next(d["box_px"] for d in res_up["detections"] if d["item_id"] == k)
    b2 = next(d["box_px"] for d in res_side["detections"] if d["item_id"] == k)
    rep["4_exif"] = dict(upright_box=b1, tagged_sideways_box=b2, max_px_diff=round(float(np.max(np.abs(np.array(b1) - np.array(b2)))), 1))
    print("4 exif:", rep["4_exif"], flush=True)

    # ---------------- 5. latency per phone-size frame
    src = next((ROOT / "data" / "downloads" / "commons_keys").glob("Flat_white*/image.jpg"))
    big = Image.open(src).convert("RGB")
    s = 960 / max(big.size)
    frame960 = jpeg(big.resize((round(big.width * s), round(big.height * s))))
    st = A.store()
    lat = {}
    for n in (18, 1):
        keep_ids = list(st.items)[:n]
        saved = dict(st.items)
        st.items = {i: saved[i] for i in keep_ids}
        ms = []
        for j in range(8):
            t0 = time.perf_counter()
            r = client.post("/frames", data={"device_id": f"lat{n}", "frame_id": str(j)}, files={"frame": ("f.jpg", frame960, "image/jpeg")})
            ms.append(1000 * (time.perf_counter() - t0))
        lat[f"{n} items registered"] = dict(request_ms_median=round(float(np.median(ms[2:])), 1), server_ms_last=r.json()["server_ms"])
        st.items = saved
    rep["5_latency_m3pro_mps"] = lat
    print("5 latency:", lat, flush=True)

    # ---------------- 6. latest frame wins
    results = {}

    def send(fid):
        results[fid] = st.handle_frame("burst", fid, frame960)

    threads = []
    for fid in range(1, 7):
        th = threading.Thread(target=send, args=(fid,)); th.start(); threads.append(th)
        time.sleep(0.15)                                     # frames every 150 ms, model takes ~400 ms
    for th in threads:
        th.join()
    rep["6_latest_frame_wins"] = dict(processed=[f for f, r in sorted(results.items()) if r is not None],
                                      skipped=[f for f, r in sorted(results.items()) if r is None])
    print("6 latest frame wins:", rep["6_latest_frame_wins"], flush=True)
    (ROOT / "reports" / "poc26_server.json").write_text(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()
