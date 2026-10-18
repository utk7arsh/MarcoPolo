"""Which detector models fit 1 frame per second on this machine? Times one OWLv2 image pass (the bulk of each frame)
for each model, in the precision the server uses here (half on CUDA), plus DINOv2 crop checks, and estimates the
per-frame time against the budget. Needs no recordings; with --session it also times the whole pipeline.

  python tools/gpu_check.py                                   # base and large OWLv2, DINOv2 small
  python tools/gpu_check.py --session data/sessions/rec2-find # plus the full pipeline (bench_frame.py)
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

OWLS = ["google/owlv2-base-patch16-ensemble", "google/owlv2-large-patch14-ensemble"]
DINO = "facebook/dinov2-small"
BUDGET_S = 1.0
UPLOAD_MARGIN_S = 0.3          # the phone's upload and the network: keep this much of the second free
PIPELINE_OVERHEAD_S = 0.06     # class heads, placement, world model, map, feeds (measured on the Mac)


def verdict(owl_s, dino_s, budget_s=BUDGET_S, margin_s=UPLOAD_MARGIN_S):
    """Estimated seconds per frame, and whether it leaves the upload margin inside the 1 s budget."""
    est = owl_s + dino_s + PIPELINE_OVERHEAD_S
    return round(est, 3), est <= budget_s - margin_s


def device_info():
    import torch
    if torch.cuda.is_available():
        p = torch.cuda.get_device_properties(0)
        return "cuda", f"{p.name}, {p.total_memory / 2**30:.1f} GB"
    if torch.backends.mps.is_available():
        return "mps", "Apple GPU (MPS)"
    return "cpu", "CPU only"


def time_owl(model_id, dev, n=8):
    import numpy as np
    import torch
    from PIL import Image
    from transformers import Owlv2ForObjectDetection, Owlv2Processor
    dtype = torch.float16 if dev == "cuda" else torch.float32          # what marco/perception/detector.py uses
    proc = Owlv2Processor.from_pretrained(model_id)
    model = Owlv2ForObjectDetection.from_pretrained(model_id, use_safetensors=True, dtype=dtype).to(dev).eval()
    im = Image.fromarray(np.random.default_rng(0).integers(0, 255, (720, 960, 3), dtype=np.uint8))
    px = proc(images=im, return_tensors="pt")["pixel_values"].to(dev, dtype)
    if dev == "cuda":
        torch.cuda.reset_peak_memory_stats()
    with torch.no_grad():
        for _ in range(2):
            model.image_embedder(pixel_values=px)[0].float().sum().item()
        t = time.perf_counter()
        for _ in range(n):
            model.image_embedder(pixel_values=px)[0].float().sum().item()
        s = (time.perf_counter() - t) / n
    mem = round(torch.cuda.max_memory_allocated() / 2**30, 2) if dev == "cuda" else None
    del model
    return s, mem, str(dtype).replace("torch.", "")


def time_dino(dev, crops=10, n=8):
    import numpy as np
    import torch
    from PIL import Image
    from transformers import AutoImageProcessor, AutoModel
    proc = AutoImageProcessor.from_pretrained(DINO)
    model = AutoModel.from_pretrained(DINO, use_safetensors=True).to(dev).eval()
    ims = [Image.fromarray(np.random.default_rng(i).integers(0, 255, (160, 120, 3), dtype=np.uint8)) for i in range(crops)]
    with torch.no_grad():
        x = proc(images=ims, return_tensors="pt").to(dev)
        model(**x).pooler_output.sum().item()
        t = time.perf_counter()
        for _ in range(n):
            x = proc(images=ims, return_tensors="pt").to(dev)
            model(**x).pooler_output.sum().item()
    return (time.perf_counter() - t) / n


def main(session=None, items=(3, 10, 20)):
    dev, name = device_info()
    print(f"device: {dev} ({name})")
    dino_s = time_dino(dev)
    print(f"DINOv2-small, 10 item crops: {dino_s * 1000:.0f} ms")
    out = dict(device=dev, name=name, dino_10_crops_s=round(dino_s, 3), models={})
    for m in OWLS:
        s, mem, dtype = time_owl(m, dev)
        est, ok = verdict(s, dino_s)
        out["models"][m] = dict(image_pass_s=round(s, 3), dtype=dtype, peak_gb=mem, est_frame_s=est, fits_1fps=ok)
        print(f"{m.split('/')[1]:36s} {dtype:8s} image pass {s * 1000:6.0f} ms"
              f"{f', peak {mem} GB' if mem is not None else ''}  -> about {est:.2f} s per frame: "
              f"{'fits 1 frame/s with room for the upload' if ok else 'too slow for 1 frame/s'}")
    if session:
        for m in OWLS:
            print(f"full pipeline with {m}:")
            env = {**os.environ, "MARCO_OWL_MODEL": m}
            subprocess.run([sys.executable, str(Path(__file__).with_name("bench_frame.py")), session, "--items", *map(str, items)],
                           env=env, check=False)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default=None, help="also time the full pipeline on this recorded session")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    res = main(a.session)
    if a.json:
        print(json.dumps(res))
