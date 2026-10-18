import asyncio
import importlib
import io
import json
import wave

import httpx
import pytest
from fastapi.testclient import TestClient

from marco.speech import MAX_PCM, SpeechOutput, SpeechSettings, SpeechUnavailable


def run(coroutine):
    return asyncio.run(coroutine)


def service(handler, **kwargs):
    return SpeechOutput(SpeechSettings(key="test-secret"), transport=httpx.MockTransport(handler), **kwargs)


def test_tts_request_and_mono_wav_are_cached():
    calls = []
    def provider(request):
        calls.append(request)
        assert str(request.url) == "https://api.elevenlabs.io/v1/text-to-speech/JBFqnCBsd6RMkjVDRZzb?output_format=pcm_24000"
        assert request.headers["xi-api-key"] == "test-secret"
        assert json.loads(request.content) == dict(text="Polo! Behind you.", model_id="eleven_flash_v2_5", language_code="en")
        return httpx.Response(200, content=b"\x01\x00" * 2400, headers={"content-type": "audio/pcm"})
    output = service(provider)
    async def check():
        first, cached = await output.render("  Polo! Behind you.  ")
        assert not cached
        second, cached = await output.render("Polo! Behind you.")
        assert cached and second == first
        with wave.open(io.BytesIO(first)) as wav:
            assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()) == (1, 2, 24000, 2400)
    run(check())
    assert len(calls) == 1


def test_duplicate_requests_share_one_generation_even_if_one_caller_cancels():
    calls = []
    async def provider(request):
        calls.append(request)
        await asyncio.sleep(.02)
        return httpx.Response(200, content=b"\0\0" * 100, headers={"content-type": "application/octet-stream"})
    output = service(provider)
    async def check():
        first = asyncio.create_task(output.render("Got it."))
        await asyncio.sleep(.005)
        second = asyncio.create_task(output.render("Got it."))
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        audio, shared = await second
        assert shared and audio.startswith(b"RIFF")
        await asyncio.sleep(0)
        assert not output.pending
    run(check())
    assert len(calls) == 1


@pytest.mark.parametrize("status,content,mime", [
    (401, b"test-secret provider body", "application/json"),
    (429, b"rate limited", "application/json"),
    (500, b"failed", "text/plain"),
    (200, b"", "audio/pcm"), (200, b"123", "audio/pcm"),
    (200, b"{}", "application/json"),
    (200, b"\0" * (MAX_PCM + 2), "audio/pcm"),
])
def test_failures_are_safe_and_do_not_enter_cache(status, content, mime):
    output = service(lambda _: httpx.Response(status, content=content, headers={"content-type": mime}))
    with pytest.raises(SpeechUnavailable) as error:
        run(output.render("Where are my keys?"))
    assert "test-secret" not in str(error.value)
    assert not output.cache


def test_deadline_and_lru_limits():
    async def slow(_):
        await asyncio.sleep(.1)
        return httpx.Response(200)
    with pytest.raises(SpeechUnavailable):
        run(service(slow, timeout=.01).render("Hello"))
    output = service(lambda _: httpx.Response(200, content=b"\0\0", headers={"content-type": "audio/pcm"}), max_entries=1)
    async def check():
        await output.render("one")
        await output.render("two")
        assert len(output.cache) == 1 and next(iter(output.cache))[2] == "two"
        assert output.cache_bytes <= output.max_bytes
    run(check())


def test_missing_key_invalid_input_and_backpressure_make_no_request():
    calls = []
    output = service(lambda r: calls.append(r))
    for text in ("", "   ", "x" * 361, "\0"):
        with pytest.raises(ValueError):
            run(output.render(text))
    with pytest.raises(SpeechUnavailable):
        run(SpeechOutput(SpeechSettings()).render("Hello"))
    output.pending = {str(i): None for i in range(8)}
    with pytest.raises(SpeechUnavailable):
        run(output.render("Hello"))
    assert not calls


def test_route_auth_validation_and_audio(monkeypatch, tmp_path):
    monkeypatch.setenv("MARCO_DATA", str(tmp_path))
    monkeypatch.setenv("MARCO_MODE", "stub")
    monkeypatch.delenv("AUTH_TEST_BYPASS", raising=False)
    monkeypatch.setenv("MARCO_AUTH", "closed")
    import marco.app
    app = importlib.reload(marco.app)
    calls = []
    def provider(r):
        calls.append(r)
        return httpx.Response(200, content=b"\0\0" * 100, headers={"content-type": "audio/pcm"})
    app.speech = service(provider)
    with TestClient(app.app) as client:
        assert client.post("/v1/speech", json={"text": "Hello"}).status_code == 403
        assert not calls
        monkeypatch.setenv("AUTH_TEST_BYPASS", "1")
        for body in ({}, {"text": " "}, {"text": "x" * 361}, {"text": 3}):
            assert client.post("/v1/speech", json=body).status_code == 422
        first = client.post("/v1/speech", json={"text": "Got it."})
        assert first.status_code == 200 and first.headers["content-type"] == "audio/wav"
        assert first.headers["x-marco-speech-provider"] == "elevenlabs"
        assert first.content.startswith(b"RIFF")
        assert client.post("/v1/speech", json={"text": "Got it."}).headers["x-marco-speech-cache"] == "hit"
        app.speech = SpeechOutput(SpeechSettings())
        assert client.post("/v1/speech", json={"text": "Hi"}).status_code == 503
    assert len(calls) == 1
