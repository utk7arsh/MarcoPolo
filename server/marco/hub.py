"""WebSocket channels: the phone, the Photon service and dashboards. Broadcast to everyone on a channel."""
from fastapi import WebSocket


class Hub:
    def __init__(self):
        self.channels: dict[str, set[WebSocket]] = {"phone": set(), "photon": set(), "dashboard": set()}

    def join(self, channel: str, ws: WebSocket):
        self.channels[channel].add(ws)

    def leave(self, channel: str, ws: WebSocket):
        self.channels[channel].discard(ws)

    async def send(self, channel: str, msg: dict):
        for ws in list(self.channels[channel]):
            try:
                await ws.send_json(msg)
            except Exception:
                self.channels[channel].discard(ws)
