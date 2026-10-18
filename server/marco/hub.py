"""WebSocket channels: the phone, the Photon service and dashboards. Broadcast to everyone on a channel.

Every socket has its own outbox and writer task, so `send` never waits on a socket. Before, it awaited each socket in
turn: one dashboard that stopped reading (a laptop asleep, a stuck tab) held up the frame route and the phone's
loop, and with them every `find` answer. A full outbox drops its oldest message; a send stuck for longer than
`send_timeout_s` drops that socket (the phone and dashboards reconnect).
"""
import asyncio
import logging

from fastapi import WebSocket

log = logging.getLogger("marco")


class Hub:
    # Messages waiting per socket before the oldest is dropped. The phone's are small and matter (answers, touch,
    # proximity at 15/s: 1000 is over a minute of them); a dashboard's carry a JPEG every second.
    LIMITS = {"phone": 1000, "photon": 200, "dashboard": 30}

    def __init__(self, send_timeout_s: float = 10.0):
        self.channels: dict[str, set[WebSocket]] = {c: set() for c in self.LIMITS}
        self.send_timeout_s = send_timeout_s
        self._outbox: dict[WebSocket, asyncio.Queue] = {}
        self._writer: dict[WebSocket, asyncio.Task] = {}

    def join(self, channel: str, ws: WebSocket):
        """Call from the socket's route, on the event loop."""
        q = asyncio.Queue(maxsize=self.LIMITS[channel])
        self.channels[channel].add(ws)
        self._outbox[ws] = q
        self._writer[ws] = asyncio.get_running_loop().create_task(self._write(channel, ws, q))

    def leave(self, channel: str, ws: WebSocket):
        self.channels[channel].discard(ws)
        self._outbox.pop(ws, None)
        task = self._writer.pop(ws, None)
        if task is not None and task is not asyncio.current_task():
            task.cancel()

    async def send(self, channel: str, msg: dict):
        """Queues msg for every socket on the channel and returns at once."""
        for ws in list(self.channels[channel]):
            q = self._outbox.get(ws)
            if q is None:
                continue
            if q.full():
                q.get_nowait()
            q.put_nowait(msg)

    def backlog(self, ws: WebSocket) -> int:
        q = self._outbox.get(ws)
        return 0 if q is None else q.qsize()

    async def _write(self, channel: str, ws: WebSocket, q: asyncio.Queue):
        try:
            while True:
                msg = await q.get()
                await asyncio.wait_for(ws.send_json(msg), self.send_timeout_s)
        except asyncio.CancelledError:
            raise
        except Exception as e:                          # closed, or stuck past the timeout
            log.warning("dropping a %s socket: %s", channel, type(e).__name__)
            self.leave(channel, ws)
            try:
                await asyncio.wait_for(ws.close(code=1011), 1.0)
            except Exception:
                pass
