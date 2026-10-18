"""Authentication gate for every route and WebSocket. Fails closed.

MARCO_AUTH=closed (default)   every request is rejected (403 / WebSocket close 1008)
MARCO_AUTH=tailscale          the app runs on 127.0.0.1 behind `tailscale serve`, which adds the caller's tailnet
                              identity as Tailscale-User-Login; only logins in TAILSCALE_ALLOWED_LOGINS get in.
                              The header is trustworthy only because nothing but tailscale serve can reach the app,
                              which is why marco/app.py main() refuses any bind other than loopback.
AUTH_TEST_BYPASS=1            tests and local development on loopback only; never set it anywhere else.
"""
import os

from fastapi import HTTPException, Request, WebSocket


def caller_from_headers(headers) -> str | None:
    if os.environ.get("AUTH_TEST_BYPASS") == "1":
        return "test-bypass"
    if os.environ.get("MARCO_AUTH", "closed") == "tailscale":
        login = (headers.get("tailscale-user-login") or "").strip().lower()
        allowed = {s.strip().lower() for s in os.environ.get("TAILSCALE_ALLOWED_LOGINS", "").split(",") if s.strip()}
        if login and login in allowed:
            return login
    return None


def require_caller(request: Request) -> str:
    who = caller_from_headers(request.headers)
    if who is None:
        raise HTTPException(status_code=403, detail="not authorised (fail-closed gate; see server/README.md)")
    return who


async def ws_caller(ws: WebSocket) -> str | None:
    who = caller_from_headers(ws.headers)
    if who is None:
        await ws.close(code=1008, reason="not authorised")
    return who
