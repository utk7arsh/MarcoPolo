"""Registrations and labels survive a restart (marco/registry.py), and DELETE /v1/items?source=photon (the
caretaker's /restart) forgets exactly what Photon added: from memory, from the detector and from disk."""
import importlib
import json

import pytest
from fastapi.testclient import TestClient

from helpers import emulated, frame_parts, jpeg_bytes, pose_msg
from marco.registry import Registry


def boot(tmp_path, monkeypatch):
    """A fresh server process on the same data folder (what a restart or a redeploy is)."""
    monkeypatch.setenv("MARCO_DATA", str(tmp_path))
    monkeypatch.setenv("MARCO_MODE", "stub")
    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")
    import marco.app
    import marco.stub
    importlib.reload(marco.stub)
    return TestClient(importlib.reload(marco.app).app)


def photon_label(c, name="cumin", text="That's the cumin, love", audio=b"voice-1"):
    """The phone asks what_is_this about something unknown; Photon answers on /v1/labels."""
    _, T, _, _ = emulated()
    data, files, _ = frame_parts()
    assert c.post("/v1/frames", data=data, files=files).status_code == 202
    with c.websocket_connect("/v1/phone") as ws:
        ws.send_json(pose_msg(T))
        ws.send_json(dict(type="query", query_id="q", kind="what_is_this"))
        tid = ws.receive_json()["touch_id"]
    r = c.post("/v1/labels", data={"touch_id": tid, "name": name, "text": text, "source": "photon"},
               files={"audio": ("voice.m4a", audio, "audio/mp4")})
    assert r.status_code == 200
    return r.json()["item_id"]


def by_name(c):
    """Items by name, without the stub's built-in fake items (source "seed"), which no delete touches."""
    return {i["name"]: i for i in c.get("/v1/items").json() if i.get("source") != "seed"}


def test_registrations_and_labels_survive_a_restart(tmp_path, monkeypatch):
    c = boot(tmp_path, monkeypatch)
    keys = c.post("/v1/items", data={"name": "keys", "source": "photon"}, files={"photo": ("k.jpg", jpeg_bytes(), "image/jpeg")}).json()
    remote = c.post("/v1/items", data={"name": "remote"}, files={"photo": ("r.jpg", jpeg_bytes(), "image/jpeg")}).json()
    cumin = photon_label(c)
    voice = c.post("/v1/labels", data={"item_id": keys["item_id"], "name": "keys", "text": "Dad's keys"},
                   files={"audio": ("keys.m4a", b"voice-keys", "audio/mp4")})
    assert voice.status_code == 200

    c = boot(tmp_path, monkeypatch)                                        # restart
    items = by_name(c)
    assert items["keys"]["item_id"] == keys["item_id"] and items["keys"]["source"] == "photon"
    assert items["keys"]["label_text"] == "Dad's keys"
    assert items["remote"]["item_id"] == remote["item_id"] and items["remote"]["source"] == "app"
    assert items["cumin"]["item_id"] == cumin and items["cumin"]["label_text"] == "That's the cumin, love"
    assert c.get(items["cumin"]["label_audio_url"]).content == b"voice-1"
    assert c.get(items["keys"]["label_audio_url"]).content == b"voice-keys"
    assert "fake-keys" not in {i["item_id"] for i in c.get("/v1/items").json()}, "the stub's seeds are not saved"
    assert {i["source"] for i in c.get("/v1/items").json()} <= {"app", "photon"}


def test_delete_by_source_forgets_only_photons_items_and_stays_forgotten(tmp_path, monkeypatch):
    c = boot(tmp_path, monkeypatch)
    c.post("/v1/items", data={"name": "keys", "source": "photon"}, files={"photo": ("k.jpg", jpeg_bytes(), "image/jpeg")})
    c.post("/v1/items", data={"name": "remote"}, files={"photo": ("r.jpg", jpeg_bytes(), "image/jpeg")})
    cumin = photon_label(c)
    audio_url = by_name(c)["cumin"]["label_audio_url"]

    r = c.delete("/v1/items", params={"source": "photon"})
    assert r.status_code == 200
    assert sorted(i["name"] for i in r.json()["removed"]) == ["cumin", "keys"]
    assert set(by_name(c)) == {"remote"}
    assert c.get(audio_url).status_code == 404
    reg = tmp_path / "registry"
    assert not (reg / "photos" / f"{cumin}.jpg").exists() and not list((reg / "audio").iterdir())
    assert [r["name"] for r in json.loads((reg / "items.json").read_text())] == ["remote"]

    with c.websocket_connect("/v1/phone") as ws:                           # the forgotten touch doesn't break "what is this?"
        ws.send_json(dict(type="query", query_id="q4", kind="what_is_this"))
        assert ws.receive_json()["status"] in ("unknown", "no_touch")

    assert c.delete("/v1/items", params={"source": "photon"}).json()["removed"] == []    # idempotent
    c = boot(tmp_path, monkeypatch)                                        # and it stays gone after a restart
    assert set(by_name(c)) == {"remote"}


def test_delete_needs_a_valid_source(tmp_path, monkeypatch):
    c = boot(tmp_path, monkeypatch)
    assert c.delete("/v1/items").status_code == 422                       # never "delete everything" by accident
    assert c.delete("/v1/items", params={"source": "../etc"}).status_code == 422
    assert c.post("/v1/items", data={"name": "keys", "source": "Bad Source"}, files={"photo": ("k.jpg", jpeg_bytes(), "image/jpeg")}).status_code == 422


def test_delete_is_behind_the_fail_closed_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("MARCO_DATA", str(tmp_path))
    monkeypatch.delenv("AUTH_TEST_BYPASS", raising=False)
    monkeypatch.delenv("MARCO_AUTH", raising=False)
    import marco.app
    c = TestClient(importlib.reload(marco.app).app)
    assert c.delete("/v1/items", params={"source": "photon"}).status_code == 403


def test_the_real_brain_reregisters_saved_photos_with_the_detector(tmp_path):
    from marco.brain import RealBrain
    from marco.perception.detector import TruthDetector
    truth = {"keys": {"position": [0, 0.8, -1], "size": 0.08}, "remote": {"position": [1, 0.5, -1], "size": 0.15}}
    b = RealBrain(TruthDetector(truth), tmp_path)
    keys, _ = b.register("keys", jpeg_bytes(), source="photon")
    remote, _ = b.register("remote", jpeg_bytes())
    b.label(None, keys["item_id"], "keys", "Dad's keys", b"voice", "m4a")

    b2 = RealBrain(TruthDetector(truth), tmp_path)                         # restart
    assert set(b2.detector.items) == {keys["item_id"], remote["item_id"]}, "detection works straight after a restart"
    it = b2.world.items[keys["item_id"]]
    assert (it.name, it.source, it.label_text) == ("keys", "photon", "Dad's keys")
    assert b2.audio[it.label_audio_url.rsplit("/", 1)[-1]] == (b"voice", "m4a")

    removed, _ = b2.remove("photon")
    assert [r["name"] for r in removed] == ["keys"]
    assert set(b2.detector.items) == {remote["item_id"]}
    assert set(RealBrain(TruthDetector(truth), tmp_path).world.items) == {remote["item_id"]}


def test_a_new_voice_label_replaces_the_old_file(tmp_path):
    r = Registry(tmp_path)
    r.save("item1", name="cumin", source="photon", audio_id="a1", audio=b"one", audio_ext="m4a")
    r.save("item1", name="cumin", source="photon", audio_id="a2", audio=b"two", audio_ext="m4a")
    assert [p.name for p in (tmp_path / "audio").iterdir()] == ["a2.m4a"]
    assert Registry(tmp_path).audio() == {"a2": (b"two", "m4a")}
    with pytest.raises(ValueError):
        r.save("../x", name="x", source="photon")


def test_without_a_data_folder_nothing_is_written(tmp_path):
    r = Registry(None)
    r.save("item1", name="cumin", source="photon", photo=b"x")
    r.remove(["item1"])
    assert r.items() == [] and not r.enabled
