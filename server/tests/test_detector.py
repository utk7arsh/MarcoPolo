"""OwlDetector's presence logic and fast preprocessing, without OWLv2's weights (a stand-in model where needed)."""
import numpy as np
import pytest
from PIL import Image

from marco.perception import detector as D
from marco.perception.detector import TH, OwlDetector, appearance, appearance_check, vs_others

torch = pytest.importorskip("torch")


def test_vs_others_ignores_an_item_registered_twice_under_one_name():
    scores = np.array([5.0, 5.0, 1.0])
    assert vs_others(scores, 0, ["Diet coke", "diet  Coke ", "Pringles"]) == 4.0
    assert vs_others(scores, 2, ["Diet coke", "diet  Coke ", "Pringles"]) == -4.0


def test_vs_others_is_none_with_nothing_else_to_compare():
    assert vs_others(np.array([3.0]), 0, ["coffee"]) is None
    assert vs_others(np.array([3.0, 3.0, 2.9]), 1, ["coffee", "Coffee", "coffee"]) is None


def test_vs_others_still_compares_look_alikes_with_different_names():
    assert vs_others(np.array([5.0, 5.0]), 0, ["salt", "sugar"]) == 0.0


class StandInOwl:
    """Logit = patch feature . query; every patch has a fixed box."""

    def __init__(self, boxes):
        self.boxes = boxes

    def class_predictor(self, image_feats, query_embeds):
        return (image_feats @ query_embeds.transpose(1, 2),)

    def box_predictor(self, feats, fmap):
        return self.boxes


def stand_in_detector(items, crop_embeddings):
    """Patch 0 shows e0, patch 1 shows e1. items: id -> (name, query vector, registered DINO vector)."""
    det = OwlDetector.__new__(OwlDetector)
    det.torch, det.dev, det.dtype = torch, "cpu", torch.float32
    feats = torch.eye(4)[:2][None]
    det._pass = lambda im: (feats, feats)
    det.owl = StandInOwl(torch.tensor([[[0.25, 0.5, 0.2, 0.2], [0.75, 0.5, 0.2, 0.2]]]))
    det._dino = lambda crops: torch.stack(crop_embeddings)
    det.items = {i: dict(name=n, q_img=torch.tensor(q, dtype=torch.float32)[None, None],
                         q_txt=torch.tensor(q, dtype=torch.float32)[None, None], dino=torch.tensor(r, dtype=torch.float32))
                 for i, (n, q, r) in items.items()}
    return det


def unit(*v):
    v = np.asarray(v, float)
    return (v / np.linalg.norm(v)).tolist()


def test_detect_finds_an_item_registered_twice(monkeypatch):
    monkeypatch.setattr(D, "TOP_K", 1)                        # one box per item: the stand-in gives one crop each
    e0, e1 = unit(1, 0, 0, 0), unit(0, 1, 0, 0)
    det = stand_in_detector({"coke-a": ("Diet coke", [5, 0, 0, 0], e0), "coke-b": ("Diet Coke", [5, 0, 0, 0], e0),
                             "water": ("Sparkling water", [0, 5, 0, 0], unit(0.6, 0.8, 0, 0))},
                            [torch.tensor(e0), torch.tensor(e0), torch.tensor(e1)])
    out = {d["item_id"]: d for d in det.detect(Image.new("RGB", (100, 80)))}
    assert out["coke-a"]["vs_others"] == out["coke-b"]["vs_others"] == 5.0     # compared with the water, not its twin
    assert out["coke-a"]["present"] and out["coke-b"]["present"]
    assert out["water"]["dino"] == pytest.approx(0.8)                          # each item's own registration vector
    assert out["water"]["present"]
    assert out["coke-a"]["box"][0] < 50 < out["water"]["box"][0]
    assert all(d["dino"] >= TH["dino"] for d in out.values())


def test_detect_still_vetoes_look_alikes_with_different_names(monkeypatch):
    monkeypatch.setattr(D, "TOP_K", 1)
    e0 = unit(1, 0, 0, 0)
    det = stand_in_detector({"salt": ("salt", [5, 0, 0, 0], e0), "sugar": ("sugar", [5, 0, 0, 0], e0)},
                            [torch.tensor(e0), torch.tensor(e0)])
    out = det.detect(Image.new("RGB", (100, 80)))
    assert [d["vs_others"] for d in out] == [0.0, 0.0]
    assert not any(d["present"] for d in out)


@pytest.fixture(scope="module")
def processor():
    try:
        from transformers import Owlv2Processor
        return Owlv2Processor.from_pretrained(OwlDetector.OWL, local_files_only=True)
    except Exception as e:
        pytest.skip(f"OWLv2's processor isn't cached here ({type(e).__name__})")


def processor_only_detector(processor):
    det = OwlDetector.__new__(OwlDetector)
    det.torch, det.dev, det.dtype, det.proc = torch, "cpu", torch.float32, processor
    det.fast_pixels = det._check_fast_pixels()
    return det


def test_fast_pixels_match_the_processor_on_phone_frames(processor):
    det = processor_only_detector(processor)
    assert det.fast_pixels and det.side == 960
    rng = np.random.default_rng(3)
    for h, w in ((720, 960), (960, 720)):
        im = Image.fromarray(rng.integers(0, 256, (h, w, 3), np.uint8))
        want = processor(images=im, return_tensors="pt")["pixel_values"]
        assert float((det._pixels(im) - want).abs().max()) <= 1e-4


def test_other_sizes_and_modes_go_through_the_processor(processor):
    det = processor_only_detector(processor)
    calls = []
    real = det.proc

    class Spy:
        image_processor = real.image_processor

        def __call__(self, **kw):
            calls.append(kw["images"].size)
            return real(**kw)

    det.proc = Spy()
    det._pixels(Image.new("RGB", (640, 480)))
    det._pixels(Image.new("RGBA", (960, 720)))
    det._pixels(Image.new("RGB", (960, 720)))
    assert calls == [(640, 480), (960, 720)]


def test_fast_pixels_turn_off_when_the_processor_disagrees(processor):
    det = OwlDetector.__new__(OwlDetector)
    det.torch, det.dev, det.dtype = torch, "cpu", torch.float32

    class GreyPadding:
        image_processor = processor.image_processor

        def __call__(self, **kw):
            px = processor(**kw)["pixel_values"]
            return {"pixel_values": px + 0.01}

    det.proc = GreyPadding()
    assert det._check_fast_pixels() is False



def colour_check_on(monkeypatch):
    monkeypatch.setattr(D, "TH_LIGHT", 40.0)                               # off by default (POC 29); on to test it
    monkeypatch.setattr(D, "TH_CHROMA", 30.0)


def test_appearance_tells_a_black_bottle_from_a_clear_mug(monkeypatch):
    colour_check_on(monkeypatch)
    monkeypatch.setattr(D, "TH_SHAPE", 2.5)                                # off by default; on here to test it
    bottle = appearance(Image.new("RGB", (30, 100), (20, 20, 24)))         # dark, tall
    assert appearance_check(bottle, appearance(Image.new("RGB", (32, 96), (35, 33, 38)))) == ""   # it, in other light
    mug = appearance_check(bottle, appearance(Image.new("RGB", (70, 66), (200, 205, 210))))       # light, squat
    assert "lightness" in mug and "shape" in mug
    assert "colourfulness" in appearance_check(bottle, appearance(Image.new("RGB", (30, 100), (230, 40, 30))))
    assert appearance_check(None, bottle) == ""                             # an old registration without a look


def test_the_item_is_found_behind_a_better_scoring_look_alike(monkeypatch):
    """Patch 0 (left) is a light look-alike OWLv2 scores higher; patch 1 (right) is the dark item. Trying more than
    the best box finds it; DINOv2 rates both the same, as it did live with a black bottle and a clear mug."""
    e0 = unit(1, 0, 0, 0)
    det = stand_in_detector({"bottle": ("bottle", [5, 3, 0, 0], e0)}, [])
    det._dino = lambda crops: torch.stack([torch.tensor(e0)] * len(crops))
    det.items["bottle"]["look"] = appearance(Image.new("RGB", (20, 20), (15, 15, 18)))
    scene = Image.new("RGB", (100, 80), (230, 230, 230))
    scene.paste((10, 10, 12), (50, 0, 100, 80))                             # the right half is dark
    colour_check_on(monkeypatch)
    monkeypatch.setattr(D, "TOP_K", 1)
    one = det.detect(scene)[0]
    assert not one["present"] and "lightness" in one["look"]                # only the look-alike was tried
    monkeypatch.setattr(D, "TOP_K", 3)
    best = det.detect(scene)[0]
    assert best["present"] and best["rank"] == 1 and best["box"][0] > 50   # the second box: the item



def test_by_default_no_appearance_check_runs(monkeypatch):
    """Colour and shape are both off by default (POC 29): a light object passes; turning colour on refuses it."""
    bottle = appearance(Image.new("RGB", (30, 100), (20, 20, 24)))
    light = appearance(Image.new("RGB", (30, 100), (200, 205, 210)))
    assert appearance_check(bottle, appearance(Image.new("RGB", (70, 66), (30, 30, 34)))) == ""   # squat from above: fine
    assert appearance_check(bottle, light) == ""
    assert D.TOP_K == 1
    colour_check_on(monkeypatch)
    assert "lightness" in appearance_check(bottle, light)
