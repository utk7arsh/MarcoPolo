"""Find and Stop from the dashboard, relayed to the phone and confirmed by it (docs/INTERFACES.md §4 `command`,
§3.2 `command_ack`; frontend/docs/fastapi-handoff.md).

HTTP 202 only means "sent to the phone". The snapshot's `lastCommand` then follows the phone's answers:
  pending   sent, no answer yet
  accepted  the phone took it
  completed the phone applied it: guidance started (Find) or stopped (Stop). Not "the user found it".
  rejected  the phone refused (with its reason), the session ended, or no answer came in time
A command the phone never answers is rejected after the timeout with a reason that says the outcome is unknown:
the phone may have acted on it and lost the reply.
Retrying the same commandId with the same body returns the same record and sends nothing again; reusing an ID for
a different command is a 409. Commands go only to the phone socket bound to the current session.
"""
import re
import time
from collections import OrderedDict

ID = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
KEPT = 50
ACCEPTED_GRACE_S = 5.0          # an accepted command gets this long past its deadline to report the result


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + f".{int(t * 1000) % 1000:03d}Z"


class CommandError(Exception):
    """An HTTP error with the frontend's stable body: {"error": {"code", "message"}}."""

    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message

    def body(self):
        return {"error": {"code": self.code, "message": self.message}}


class CommandRelay:
    def __init__(self, timeout_s=10.0, now=time.time):
        self.timeout_s, self.now = float(timeout_s), now
        self.records: OrderedDict[str, dict] = OrderedDict()
        self.latest = None

    @staticmethod
    def normalize(body):
        if not isinstance(body, dict):
            raise CommandError(400, "invalid_request", "Send a JSON command object.")
        cid, dev, kind = body.get("commandId"), body.get("deviceId"), body.get("type")
        if not (isinstance(cid, str) and ID.match(cid)):
            raise CommandError(400, "invalid_request", "commandId is missing or malformed.")
        if not (isinstance(dev, str) and dev):
            raise CommandError(400, "invalid_request", "deviceId is missing.")
        if kind not in ("find", "stop"):
            raise CommandError(400, "invalid_request", "type must be find or stop.")
        item = body.get("itemId")
        if kind == "find" and not (isinstance(item, str) and item):
            raise CommandError(400, "invalid_request", "Find needs an itemId.")
        return dict(commandId=cid, deviceId=dev, type=kind, itemId=item if kind == "find" else None)

    def submit(self, body, *, session_id, device_id, connected, item):
        """Validate and record a command. Returns (record, phone_message or None for a retry). item(id) -> the
        world's public item dict or None. Raises CommandError."""
        self.expire()
        cmd = self.normalize(body)
        old = self.records.get(cmd["commandId"])
        if old is not None:
            if old["cmd"] != cmd:
                raise CommandError(409, "command_conflict", "That command ID was already used for a different command.")
            return old, None
        if not connected or not session_id:
            raise CommandError(409, "phone_disconnected", "iPhone is disconnected.")
        if cmd["deviceId"] != device_id:
            raise CommandError(409, "session_mismatch", "That iPhone session has ended. Reload the dashboard.")
        target = None
        if cmd["type"] == "find":
            it = item(cmd["itemId"])
            if it is None:
                raise CommandError(404, "unknown_item", "No item with that ID.")
            if it.get("position") is None or it.get("state") in ("stale", "missing", "picked_up", "registered"):
                raise CommandError(409, "location_unavailable", f"Marco doesn't know where the {it.get('name', 'item')} is right now.")
            if any(r["status"] in ("pending", "accepted") and r["cmd"]["type"] == "find" and r["session_id"] == session_id
                   for r in self.records.values()):
                raise CommandError(409, "busy", "Another Find is still waiting for the iPhone.")
            target = it
        t = self.now()
        rec = dict(cmd=cmd, status="pending", reason=None, session_id=session_id, created=t, deadline=t + self.timeout_s)
        self.records[cmd["commandId"]] = rec
        while len(self.records) > KEPT:
            self.records.popitem(last=False)
        self.latest = cmd["commandId"]
        msg = dict(type="command", command_id=cmd["commandId"], session_id=session_id, action=cmd["type"],
                   expires_wall=iso(rec["deadline"]))
        if target is not None:
            msg.update(item_id=target["item_id"], name=target.get("name"), position=target["position"], surface=target.get("surface"))
        return rec, msg

    def ack(self, msg):
        """A command_ack from the phone. Unknown, foreign-session, late and repeated answers are ignored."""
        rec = self.records.get(msg.get("command_id"))
        if rec is None or msg.get("session_id") != rec["session_id"] or rec["status"] in ("completed", "rejected"):
            return False
        status = msg.get("status")
        if status == "accepted" and rec["status"] == "pending":
            rec["status"] = "accepted"
        elif status == "applied":
            rec["status"], rec["reason"] = "completed", None
        elif status == "rejected":
            rec["status"], rec["reason"] = "rejected", str(msg.get("reason") or "The iPhone refused the command.")[:200]
        else:
            return False
        return True

    def failed(self, command_id, reason):
        rec = self.records.get(command_id)
        if rec is not None and rec["status"] in ("pending", "accepted"):
            rec["status"], rec["reason"] = "rejected", reason

    def expire(self):
        t = self.now()
        for rec in self.records.values():
            if rec["status"] == "pending" and t > rec["deadline"]:
                rec["status"] = "rejected"
                rec["reason"] = (f"no_answer: the iPhone didn't confirm within {self.timeout_s:.0f} s. "
                                 "It may or may not have acted; check the phone.")
            elif rec["status"] == "accepted" and t > rec["deadline"] + ACCEPTED_GRACE_S:
                rec["status"] = "rejected"
                rec["reason"] = "no_result: the iPhone accepted the command but didn't report the result."

    def session_replaced(self):
        for rec in self.records.values():
            if rec["status"] in ("pending", "accepted"):
                rec["status"], rec["reason"] = "rejected", "session_replaced: the iPhone started a new session."

    def last(self):
        rec = self.records.get(self.latest) if self.latest else None
        if rec is None:
            return None
        return dict(commandId=rec["cmd"]["commandId"], status=rec["status"], reason=rec["reason"])
