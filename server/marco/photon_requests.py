"""Short, bounded replay of unanswered requests when the private bridge reconnects.

This is memory only, like the touch crops themselves. The bridge deduplicates by
touch_id; a posted label resolves the request. Nothing here sends an iMessage.
"""
from collections import OrderedDict
import time


class PendingLabelRequests:
    def __init__(self, *, max_entries=128, max_age_s=600, clock=time.monotonic):
        self.max_entries, self.max_age_s, self.clock = max_entries, max_age_s, clock
        self._requests = OrderedDict()

    def add(self, message):
        self._requests[message["touch_id"]] = (self.clock(), dict(message))
        self._requests.move_to_end(message["touch_id"])
        self.pending()
        while len(self._requests) > self.max_entries:
            self._requests.popitem(last=False)

    def resolve(self, touch_id):
        self._requests.pop(touch_id, None)

    def clear(self):
        """POST /v1/reset: no question about an item that no longer exists is replayed to the bridge."""
        self._requests.clear()

    def pending(self):
        now = self.clock()
        expired = [key for key, (created, _) in self._requests.items() if now - created >= self.max_age_s]
        for key in expired:
            del self._requests[key]
        return [dict(message) for _, message in self._requests.values()]
