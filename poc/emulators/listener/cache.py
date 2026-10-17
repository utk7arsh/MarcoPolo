"""Compute and cache grid features for Apple's renderer and the ARI listeners."""
import pickle
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "audio"))
from features import grid_features  # noqa: E402
from hrir_io import load_apple  # noqa: E402
from sofa_io import ari_subjects, load_sofa  # noqa: E402

CACHE = HERE.parents[1] / "data" / "features_cache.pkl"


def load_all(rebuild=False):
    if CACHE.exists() and not rebuild:
        return pickle.loads(CACHE.read_bytes())
    feats = {"apple": grid_features(load_apple("hrtfhq", trim=(0, 512)))}
    for p in ari_subjects():
        feats[p.stem.replace("dtf_", "")] = grid_features(load_sofa(p))
    CACHE.write_bytes(pickle.dumps(feats))
    return feats


if __name__ == "__main__":
    f = load_all(rebuild=True)
    print("cached", list(f))
