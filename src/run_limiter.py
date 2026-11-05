# --- Javier: waiting line for analyses (code written with help from Claude) ---
# With 35 people clicking at once, starting every analysis right away would burst past the free-tier limits of every
# key and most runs would stall on rate-limit errors. Instead, at most MAX_RUNS analyses run at the same time across
# all visitors; everyone else waits in a first-come, first-served line and sees their place in it.
#
# MAX_RUNS defaults to two analyses per key (one project's minute of tokens covers about two runs). Set
# MAX_CONCURRENT_RUNS in the Streamlit secrets to override it.
#
# Streamlit runs each visitor's script in its own thread of the same process, so one module-level line is shared by
# everyone. A visitor who leaves or clicks something else gives their place back (the finally block).
import os
import threading
import time
from collections import deque
from contextlib import contextmanager

from src.key_pool import pool

RUNS_PER_KEY = 2
MAX_WAIT_SECONDS = 15 * 60
CHECK_EVERY_SECONDS = 2


def _max_runs():
    try:
        import streamlit as st
        configured = st.secrets.get("MAX_CONCURRENT_RUNS")
    except Exception:
        configured = None
    configured = configured or os.environ.get("MAX_CONCURRENT_RUNS")
    return int(configured) if configured else max(2, RUNS_PER_KEY * len(pool.keys))


class WaitingLine:
    def __init__(self, limit):
        self.limit = limit
        self.line = deque()
        self.running = 0
        self.changed = threading.Condition()

    @contextmanager
    def slot(self, on_wait=None):
        """Wait for a free slot, then hold it while the analysis runs.
        on_wait(position, running) is called while waiting (position 1 = next in line)."""
        ticket = object()
        acquired = False
        started = time.time()
        with self.changed:
            self.line.append(ticket)
        try:
            while True:
                with self.changed:
                    position = self.line.index(ticket) + 1
                    if position == 1 and self.running < self.limit:
                        self.line.popleft()
                        self.running += 1
                        acquired = True
                        break
                    running = self.running
                if time.time() - started > MAX_WAIT_SECONDS:
                    raise TimeoutError("waited too long for a free slot")
                if on_wait:
                    on_wait(position, running)
                with self.changed:
                    self.changed.wait(timeout=CHECK_EVERY_SECONDS)
            yield
        finally:
            with self.changed:
                if acquired:
                    self.running -= 1
                elif ticket in self.line:
                    self.line.remove(ticket)
                self.changed.notify_all()

    def status(self):
        with self.changed:
            return {"running": self.running, "limit": self.limit, "waiting": len(self.line)}


waiting_line = WaitingLine(_max_runs())
