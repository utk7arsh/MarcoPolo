"""The dashboard's live view: small upright JPEGs from the phone, about 10 a second, passed straight to the dashboards
that are watching (docs/INTERFACES.md §3.2 `/v1/preview`, §6 `/preview`).

It never touches detection: the 1 frame/s frames still arrive on POST /v1/frames exactly as before, and this has its
own sockets, so a picture never queues in front of a pose or hand message on /v1/phone. Newest frame wins everywhere:
the phone has one frame in flight at most, the relay keeps only the latest, and each dashboard is sent the newest
frame whenever it is ready for one. A slow link shows fewer frames; it never delays anything. The phone sends only
while a dashboard is watching ({"type": "preview", "want": true}), so it costs nothing otherwise. Nothing is decoded
or recorded here.
"""
import asyncio
import os
import time

MAX_BYTES = 256_000           # a 480 px JPEG is ~20 KB; anything this big is not a preview
FRESH_S = 2.0                 # a dashboard that connects gets the latest frame only if it's this new
SEND_TIMEOUT_S = 5.0          # a dashboard that can't take a frame in this long is dropped (it reconnects)


class PreviewRelay:
    def __init__(self, hz=None, now=time.monotonic):
        self.hz = float(os.environ.get("MARCO_PREVIEW_HZ", "10") if hz is None else hz)   # 0 turns previews off
        self.min_gap_s = 0.8 / max(self.hz, 1e-9) if self.hz > 0 else float("inf")      # a phone sending faster is cut
        self.now = now
        self.phones = set()           # phone /v1/preview sockets
        self.watchers = {}            # dashboard /preview socket -> Event set when a newer frame is waiting
        self.latest = None            # (jpeg bytes, monotonic time received, sequence)
        self.seq = 0
        self.received = self.refused = 0
        self._last = float("-inf")
        self.lock = asyncio.Lock()    # control messages to the phones, one at a time

    def want_message(self):
        """What the phone needs to know: is anyone watching, and how often to send."""
        return dict(type="preview", want=bool(self.watchers) and self.hz > 0, hz=self.hz)

    def accept(self, data) -> bool:
        """One frame from the phone. Refused (False): not a JPEG, too big, previews off, or faster than hz."""
        t = self.now()
        if not isinstance(data, (bytes, bytearray)) or len(data) > MAX_BYTES or bytes(data[:2]) != b"\xff\xd8" \
                or t - self._last < self.min_gap_s:
            self.refused += 1
            return False
        self._last = t
        self.seq += 1
        self.latest = (bytes(data), t, self.seq)
        self.received += 1
        for ev in self.watchers.values():
            ev.set()
        return True

    def fresh(self):
        return self.latest is not None and self.now() - self.latest[1] <= FRESH_S

    async def tell_phones(self):
        msg = self.want_message()
        async with self.lock:
            for ws in list(self.phones):
                try:
                    await ws.send_json(msg)
                except Exception:
                    self.phones.discard(ws)

    async def serve_phone(self, ws):
        """A phone's /v1/preview socket (already accepted and authorised): tell it whether to send, take frames."""
        self.phones.add(ws)
        try:
            async with self.lock:
                await ws.send_json(self.want_message())
            while True:
                m = await ws.receive()
                if m.get("type") == "websocket.disconnect":
                    return
                if m.get("bytes") is not None:
                    self.accept(m["bytes"])
        finally:
            self.phones.discard(ws)

    async def serve_dashboard(self, ws):
        """A dashboard's /preview socket (already accepted and authorised): the newest frame, whenever it's ready."""
        ev = asyncio.Event()
        first = not self.watchers
        self.watchers[ws] = ev
        if first:
            await self.tell_phones()
        if self.fresh():
            ev.set()
        closed = asyncio.ensure_future(self._until_closed(ws))
        sent = 0
        try:
            while not closed.done():
                waiter = asyncio.ensure_future(ev.wait())
                await asyncio.wait({waiter, closed}, return_when=asyncio.FIRST_COMPLETED)
                waiter.cancel()
                if closed.done() or not ev.is_set():
                    continue
                ev.clear()
                jpeg, _, seq = self.latest
                if seq == sent:
                    continue
                await asyncio.wait_for(ws.send_bytes(jpeg), SEND_TIMEOUT_S)
                sent = seq
        except Exception:
            pass                                       # the browser went away, or stopped taking frames
        finally:
            closed.cancel()
            self.watchers.pop(ws, None)
            if not self.watchers:                      # a task of its own: this one may be being cancelled
                asyncio.get_running_loop().create_task(self.tell_phones())

    @staticmethod
    async def _until_closed(ws):
        while True:
            m = await ws.receive()
            if m.get("type") == "websocket.disconnect":
                return
