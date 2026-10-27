"""Call-local response lifecycle; provider/model text never controls the watchdog."""

import time


class ResponseLifecycle:
    def __init__(self, turn, *, clock=time.monotonic):
        self.turn, self.clock = turn, clock
        self.started = clock()
        self.operation_started = None
        self.operation = None
        self.waiting_sent = False
        self.final_ready = False
        self.closed = False

    def dispatch(self, operation, turn):
        if not self.closed and turn == self.turn:
            self.operation, self.operation_started = operation, self.clock()

    def settle(self, operation):
        if self.operation == operation:
            self.operation = self.operation_started = None

    def due(self):
        return (
            not self.closed
            and not self.final_ready
            and not self.waiting_sent
            and self.operation_started is not None
            and self.clock() - self.started >= 1.8
            and self.clock() - self.operation_started >= 0.3
        )

    def claim_waiting(self):
        if not self.due():
            return False
        self.waiting_sent = True
        return True
