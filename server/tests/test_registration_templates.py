"""Registration pixels must survive restart, irrespective of who supplied the photo.

The recorder uses a fractional detector box and patterned pixels so these tests catch rounding,
JPEG recompression, repeated cropping and confusing a caretaker setup photo with a touch crop.
"""
import io

import numpy as np
import pytest
from PIL import Image, ImageOps

from marco.brain import RealBrain
from marco.registry import Registry
from marco.stub import StubBrain


BOX = (13.7, 9.2, 53.6, 41.9)


def photo(orientation=1):
    im = Image.fromarray(np.random.default_rng(9).integers(0, 256, (80, 96, 3), dtype=np.uint8))
    exif = Image.Exif()
    exif[0x0112] = orientation
    buf = io.BytesIO()
    im.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


class CropRecorder:
    def __init__(self, refuse=False):
        self.items, self.calls, self.refuse = {}, [], refuse

    def register(self, item_id, name, im, gate=True):
        self.calls.append((item_id, gate))
        if gate and self.refuse:
            return dict(quality="retake", reason="not recognized", box=None)
        crop = im.crop(tuple(int(v) for v in BOX)) if gate else im
        self.items[item_id] = dict(name=name, pixels=np.array(crop))
        return dict(quality="ok", reason="", box=list(BOX))

    def forget(self, item_id):
        self.items.pop(item_id, None)


@pytest.mark.parametrize("source", ["app", "photon"])
@pytest.mark.parametrize("orientation", [1, 6])
def test_setup_reload_preserves_exact_template_without_rechecking_name(tmp_path, source, orientation):
    detector = CropRecorder()
    first = RealBrain(detector, tmp_path)
    result, _ = first.register("mug", photo(orientation), source=source)
    iid = result["item_id"]
    expected = detector.items[iid]["pixels"]
    for _ in range(3):
        restored = CropRecorder(refuse=True)
        again = RealBrain(restored, tmp_path)
        np.testing.assert_array_equal(restored.items[iid]["pixels"], expected)
        assert restored.calls == [(iid, False)]
        assert again.world.items[iid].source == source
    original = Image.open(io.BytesIO(again.registry.photo(iid)))
    assert original.size == ImageOps.exif_transpose(Image.open(io.BytesIO(photo(orientation)))).size
    template = Image.open(io.BytesIO(again.registry.template(iid)))
    assert template.format == "PNG"
    np.testing.assert_array_equal(np.array(template), expected)


@pytest.mark.parametrize("source", ["app", "photon"])
def test_touch_crop_is_preserved_through_label_edit_and_reload(tmp_path, source):
    detector = CropRecorder()
    first = RealBrain(detector, tmp_path)
    first.touches["touch1"] = dict(crop_jpeg=photo(), position=None, item_id=None)
    first.label("touch1", None, "mug", "This is my mug", None, "m4a", source=source)
    iid = first.touches["touch1"]["item_id"]
    expected = detector.items[iid]["pixels"].copy()
    before = first.registry.template(iid)
    first.label(None, iid, "blue mug", "My blue mug", b"legacy audio", "m4a")
    assert first.registry.template(iid) == before
    restored = CropRecorder()
    again = RealBrain(restored, tmp_path)
    assert restored.calls == [(iid, False)]
    np.testing.assert_array_equal(restored.items[iid]["pixels"], expected)
    item = again.world.items[iid]
    assert (item.name, item.source, item.label_text) == ("blue mug", source, "My blue mug")
    assert len(again.audio) == 1


@pytest.mark.parametrize("source", ["app", "photon"])
def test_setup_label_edit_keeps_the_original_crop(tmp_path, source):
    detector = CropRecorder()
    first = RealBrain(detector, tmp_path)
    result, _ = first.register("mug", photo(), source=source)
    iid = result["item_id"]
    expected = detector.items[iid]["pixels"].copy()
    first.label(None, iid, "blue mug", "My blue mug", None, "m4a")
    restored = CropRecorder()
    RealBrain(restored, tmp_path)
    np.testing.assert_array_equal(restored.items[iid]["pixels"], expected)
    assert restored.calls == [(iid, False)]


@pytest.mark.parametrize("source", ["app", "photon"])
def test_legacy_unlabelled_setup_photo_recovers_crop_once(tmp_path, source):
    reg = Registry(tmp_path / "registry")
    reg.save("old", name="mug", source=source, photo=photo())
    detector = CropRecorder()
    first = RealBrain(detector, tmp_path)
    assert detector.calls == [("old", True)]
    original = Image.open(io.BytesIO(reg.photo("old"))).convert("RGB")
    expected = np.array(original.crop(tuple(int(v) for v in BOX)))
    np.testing.assert_array_equal(detector.items["old"]["pixels"], expected)
    restored = CropRecorder(refuse=True)
    RealBrain(restored, tmp_path)
    np.testing.assert_array_equal(restored.items["old"]["pixels"], expected)
    assert restored.calls == [("old", False)]
    assert first.registry.records["old"]["photo_kind"] == "full"


@pytest.mark.parametrize("source", ["app", "photon"])
def test_legacy_labelled_crop_is_not_cropped_again(tmp_path, source):
    reg = Registry(tmp_path / "registry")
    reg.save("touch", name="mug", source=source, label_text="My mug", photo=photo())
    detector = CropRecorder()
    RealBrain(detector, tmp_path)
    assert detector.calls == [("touch", False)]
    np.testing.assert_array_equal(detector.items["touch"]["pixels"], np.array(Image.open(io.BytesIO(photo()))))


@pytest.mark.parametrize("kind", ["full", "crop"])
@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_damaged_template_recovers_using_photo_kind_not_source(tmp_path, kind, damage):
    first = RealBrain(CropRecorder(), tmp_path)
    if kind == "full":
        iid = first.register("mug", photo(), source="photon")[0]["item_id"]
        # A label correction must not turn a full setup photo into a presumed touch crop.
        first.label(None, iid, "mug", "My mug", None, "m4a")
    else:
        first.touches["touch"] = dict(crop_jpeg=photo(), position=None, item_id=None)
        first.label("touch", None, "mug", "My mug", None, "m4a", source="app")
        iid = first.touches["touch"]["item_id"]
    path = tmp_path / "registry" / "templates" / f"{iid}.png"
    if damage == "missing":
        path.unlink()
    else:
        path.write_bytes(b"not an image")
    restored = CropRecorder()
    again = RealBrain(restored, tmp_path)
    original = Image.open(io.BytesIO(first.registry.photo(iid))).convert("RGB")
    expected = original.crop(tuple(int(v) for v in BOX)) if kind == "full" else original
    np.testing.assert_array_equal(restored.items[iid]["pixels"], np.array(expected))
    assert restored.calls == [(iid, kind == "full")]
    Image.open(io.BytesIO(again.registry.template(iid))).verify()


def test_saved_template_can_reload_even_if_display_photo_is_missing(tmp_path):
    detector = CropRecorder()
    first = RealBrain(detector, tmp_path)
    iid = first.register("mug", photo(), source="photon")[0]["item_id"]
    (tmp_path / "registry" / "photos" / f"{iid}.jpg").unlink()
    restored = CropRecorder()
    RealBrain(restored, tmp_path)
    np.testing.assert_array_equal(restored.items[iid]["pixels"], detector.items[iid]["pixels"])


def test_replacing_a_reference_photo_does_not_reuse_its_stale_template(tmp_path):
    first = RealBrain(CropRecorder(), tmp_path)
    iid = first.register("mug", photo(), source="photon")[0]["item_id"]
    first.registry.save(iid, name="mug", source="photon", photo=photo(6), photo_kind="full")
    restored = CropRecorder()
    RealBrain(restored, tmp_path)
    expected = ImageOps.exif_transpose(Image.open(io.BytesIO(photo(6)))).crop(tuple(int(v) for v in BOX))
    np.testing.assert_array_equal(restored.items[iid]["pixels"], np.array(expected))


def test_source_deletion_also_removes_only_its_template(tmp_path):
    brain = RealBrain(CropRecorder(), tmp_path)
    app = brain.register("mug", photo())[0]["item_id"]
    photon = brain.register("cup", photo(), source="photon")[0]["item_id"]
    brain.remove("photon")
    templates = tmp_path / "registry" / "templates"
    assert {p.name for p in templates.iterdir()} == {f"{app}.png"}
    assert not (tmp_path / "registry" / "photos" / f"{photon}.jpg").exists()
    restored = RealBrain(CropRecorder(), tmp_path)
    assert set(restored.world.items) == {app}


def test_retake_writes_neither_registry_record_nor_template(tmp_path):
    brain = RealBrain(CropRecorder(refuse=True), tmp_path)
    result, _ = brain.register("mug", photo(), source="photon")
    assert result["quality"] == "retake" and result["item_id"] is None
    assert brain.registry.items() == []
    assert not list((tmp_path / "registry" / "templates").glob("*.png"))


@pytest.mark.parametrize("source", ["app", "photon"])
def test_legacy_rejected_name_falls_back_to_saved_photo_without_losing_item(tmp_path, source):
    reg = Registry(tmp_path / "registry")
    reg.save("old", name="mug", source=source, photo=photo())
    detector = CropRecorder(refuse=True)
    again = RealBrain(detector, tmp_path)
    assert detector.calls == [("old", True), ("old", False)]
    np.testing.assert_array_equal(detector.items["old"]["pixels"], np.array(Image.open(io.BytesIO(photo()))))
    assert again.registry.template("old") is not None
    restored = CropRecorder()
    RealBrain(restored, tmp_path)
    assert restored.calls == [("old", False)]


@pytest.mark.parametrize("kind", ["full", "crop"])
@pytest.mark.parametrize("source", ["app", "photon"])
def test_stub_photo_kind_survives_correction_and_switch_to_real_mode(tmp_path, source, kind):
    stub = StubBrain(tmp_path)
    if kind == "full":
        iid = stub.register("mug", photo(), source=source)[0]["item_id"]
    else:
        stub.touches["touch"] = dict(crop_jpeg=photo(), position=None, item_id=None)
        stub.label("touch", None, "mug", "My mug", None, "m4a", source=source)
        iid = stub.touches["touch"]["item_id"]
    stub.label(None, iid, "blue mug", "My blue mug", None, "m4a")
    detector = CropRecorder()
    real = RealBrain(detector, tmp_path)
    assert detector.calls == [(iid, kind == "full")]
    assert real.registry.records[iid]["photo_kind"] == kind


def test_actual_owl_registration_uses_the_same_pixels_as_persistence(tmp_path):
    """Exercise OwlDetector.register itself, substituting model outputs without downloading weights."""
    from marco.perception.detector import OwlDetector
    torch = pytest.importorskip("torch")
    detector = OwlDetector.__new__(OwlDetector)
    detector.torch, detector.items = torch, {}
    seen = []

    class Model:
        def class_predictor(self, **kwargs):
            return (torch.tensor([[[10.0]]]),)

        def box_predictor(self, *args):
            return torch.tensor([[[0.4, 0.4, 0.45, 0.35]]])

        def embed_image_query(self, *args):
            return (torch.ones((1, 1, 4)),)

    def image_pass(im):
        seen.append(np.array(im))
        return torch.ones((1, 1, 4)), torch.ones((1, 1, 4))

    detector.owl = Model()
    detector._pass = image_pass
    detector._text = lambda name: torch.ones((1, 1, 4))
    detector._dino = lambda images: torch.ones((len(images), 4))
    brain = RealBrain(detector, tmp_path)
    iid = brain.register("mug", photo(), source="photon")[0]["item_id"]
    expected = seen[1].copy()  # The pixels actually sent to the image-query encoder.
    assert expected.shape != seen[0].shape
    np.testing.assert_array_equal(np.array(Image.open(io.BytesIO(brain.registry.template(iid)))), expected)
    seen.clear()
    RealBrain(detector, tmp_path)
    np.testing.assert_array_equal(seen[1], expected)
