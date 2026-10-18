"""ElevenLabs is an output voice only. No recognition, labels or generated answers.

Short lines are synthesized once, bounded in memory, and returned as mono WAV for
the phone's existing spatial player. Failure leaves on-device speech to the phone.
"""
import asyncio
from collections import OrderedDict
from dataclasses import dataclass
import io
import os
import re
import wave

import httpx

MAX_TEXT = 360
MAX_PCM = 24_000 * 2 * 20          # twenty seconds, mono signed 16-bit


class SpeechUnavailable(Exception):
    """Safe to expose: never includes provider bodies, submitted text or keys."""


@dataclass(frozen=True)
class SpeechSettings:
    key: str = ""
    voice: str = "JBFqnCBsd6RMkjVDRZzb"
    model: str = "eleven_flash_v2_5"

    @classmethod
    def from_env(cls):
        return cls(key=os.environ.get("ELEVENLABS_API_KEY", "").strip(),
                   voice=os.environ.get("ELEVENLABS_VOICE_ID", cls.voice).strip(),
                   model=os.environ.get("ELEVENLABS_TTS_MODEL", cls.model).strip())


class SpeechOutput:
    def __init__(self, settings: SpeechSettings, *, transport=None, timeout=2.5,
                 max_entries=128, max_bytes=8 * 1024 * 1024):
        self.settings = settings
        self.transport = transport
        self.timeout = timeout
        self.max_entries, self.max_bytes = max_entries, max_bytes
        self.cache = OrderedDict()
        self.cache_bytes = 0
        self.pending = {}
        self.slots = asyncio.Semaphore(2)

    async def render(self, text: str) -> tuple[bytes, bool]:
        text = text.strip()
        if not text or len(text) > MAX_TEXT or "\x00" in text:
            raise ValueError("speech text must contain 1 to 360 characters")
        cfg = self.settings
        if not cfg.key or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", cfg.voice):
            raise SpeechUnavailable("speech output is not configured")
        key = (cfg.voice, cfg.model, text)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key], True
        if key in self.pending:
            return await asyncio.shield(self.pending[key]), True
        if len(self.pending) >= 8:
            raise SpeechUnavailable("speech output is busy")
        task = asyncio.create_task(self._generate(key, text))
        self.pending[key] = task
        # A disconnected phone must neither leak the pending slot nor cause an
        # unobserved task exception. Other callers can share the same generation.
        def finished(done):
            self.pending.pop(key, None)
            if not done.cancelled():
                done.exception()
        task.add_done_callback(finished)
        return await asyncio.shield(task), False

    async def _generate(self, key, text):
        try:
            async with asyncio.timeout(self.timeout):
                async with self.slots:
                    async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout) as client:
                        cfg = self.settings
                        async with client.stream(
                            "POST", f"https://api.elevenlabs.io/v1/text-to-speech/{cfg.voice}",
                            params={"output_format": "pcm_24000"},
                            headers={"xi-api-key": cfg.key, "Accept": "audio/pcm"},
                            json={"text": text, "model_id": cfg.model, "language_code": "en"},
                        ) as response:
                            if response.status_code != 200:
                                raise SpeechUnavailable("speech provider unavailable")
                            mime = response.headers.get("content-type", "").split(";")[0]
                            if mime not in {"audio/pcm", "audio/x-pcm", "audio/raw", "application/octet-stream"}:
                                raise SpeechUnavailable("invalid speech audio")
                            pcm = bytearray()
                            async for chunk in response.aiter_bytes():
                                pcm.extend(chunk)
                                if len(pcm) > MAX_PCM:
                                    raise SpeechUnavailable("speech audio too large")
        except (httpx.HTTPError, TimeoutError):
            raise SpeechUnavailable("speech output timed out or unavailable") from None
        if len(pcm) < 2 or len(pcm) % 2:
            raise SpeechUnavailable("invalid speech audio")
        out = io.BytesIO()
        with wave.open(out, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24_000)
            wav.writeframes(pcm)
        audio = out.getvalue()
        if len(audio) <= self.max_bytes and self.max_entries > 0:
            self.cache[key] = audio
            self.cache_bytes += len(audio)
            while len(self.cache) > self.max_entries or self.cache_bytes > self.max_bytes:
                _, removed = self.cache.popitem(last=False)
                self.cache_bytes -= len(removed)
        return audio
