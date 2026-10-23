"""Bound the pinned EMA scheduler's outbox without trapping cancellation in put()."""

import queue
import threading


class CancellableOutbox(queue.Queue):
    def __init__(self):
        super().__init__(maxsize=1)
        self.stopped = threading.Event()
        self.peak = 0

    def put(self, item):
        while not self.stopped.is_set():
            try:
                super().put(item, timeout=0.05)
                self.peak = max(self.peak, self.qsize())
                return
            except queue.Full:
                pass

    def stop(self):
        self.stopped.set()
