# --- Javier: Gemini key pool for many simultaneous users (code written with help from Claude) ---
# The free tier limits each Google Cloud PROJECT (not each key): about 15 requests and ~250k tokens per minute for
# gemini-3.1-flash-lite (Nov 2026; check AI Studio's rate-limit page). One analysis averages ~5.5 calls and ~112k input
# tokens, so one project serves about two analyses at a time. To serve a class, the app holds keys from several
# DIFFERENT projects and spreads analyses across them.
#
# How it works:
#   - Keys come from Streamlit secrets (GEMINI_API_KEYS = ["...", "..."], or the old single GEMINI_API_KEY) or from the
#     environment (GEMINI_API_KEYS="k1,k2" or GEMINI_API_KEY). Keys are never printed; the app shows "key 1", "key 2".
#   - Each analysis takes ONE key for its whole run (pool.run()): the key with the fewest analyses running and the
#     fewest tokens used in the last minute. Keeping a run on one key keeps its token use predictable.
#   - pool.generate() makes every model call. If the run's key answers "rate limited", that key rests for a minute and
#     the run moves to another key; only when every key is resting does it wait 15 seconds and retry.
#   - Usage is counted per key from the model's own token counts, so the choice is based on what was really spent.
import contextvars
import os
import threading
import time
from collections import deque
from contextlib import contextmanager

from google import genai

REQUESTS_PER_MINUTE = 15          # per project, free tier (AI Studio, Oct 2026)
TOKENS_PER_MINUTE = 250_000       # per project, free tier: assumed, verify in AI Studio
REST_SECONDS = 60                 # a key that hit its limit is not used again for this long
WAIT_SECONDS = 15                 # wait when every key is resting (same as the old retry policy)
MAX_ATTEMPTS = 6


class ModelBusy(RuntimeError):
    """Raised when every retry failed. kind: "daily_quota" (the keys' free daily requests are used up),
    "rate_limit" (too many requests this minute), or "overloaded" (Google's side). The app words its message on it.
    A RuntimeError, so code that caught the old "gave up after repeated retries" error still catches this."""

    def __init__(self, kind):
        self.kind = kind
        super().__init__(f"gave up after repeated retries ({kind})")


def _is_daily_quota(error):
    return "PerDay" in str(error)                 # Gemini names the exhausted quota, e.g. ...RequestsPerDay...


def _is_rate_limit(error):
    return any(code in str(error) for code in ("429", "RESOURCE_EXHAUSTED"))


def _is_overload(error):
    return any(code in str(error) for code in ("503", "UNAVAILABLE"))


def read_keys():
    """All configured keys, in order, without duplicates."""
    many, one = None, None
    try:
        import streamlit as st
        many, one = st.secrets.get("GEMINI_API_KEYS"), st.secrets.get("GEMINI_API_KEY")
    except Exception:                                   # no secrets file (command line, tests)
        pass
    if not many and not one:
        many, one = os.environ.get("GEMINI_API_KEYS"), os.environ.get("GEMINI_API_KEY")
    if isinstance(many, str):
        many = many.split(",")
    keys = []
    for key in list(many or []) + [one]:
        key = (key or "").strip()
        if key and key not in keys:
            keys.append(key)
    return keys


class Key:
    def __init__(self, number, api_key):
        self.label = f"key {number}"
        self.client = genai.Client(api_key=api_key)
        self.active = 0                                  # analyses currently using this key
        self.calls = deque()                             # (time, tokens) of calls in the last minute
        self.resting_until = 0.0

    def last_minute(self, now):
        while self.calls and now - self.calls[0][0] > 60:
            self.calls.popleft()
        return len(self.calls), sum(tokens for _, tokens in self.calls)

    def resting(self, now):
        return now < self.resting_until

    def full(self, now):
        requests, tokens = self.last_minute(now)
        return requests >= REQUESTS_PER_MINUTE or tokens >= TOKENS_PER_MINUTE


class KeyPool:
    def __init__(self, api_keys):
        self.keys = [Key(i + 1, k) for i, k in enumerate(api_keys)]
        self.lock = threading.Lock()
        self.current = contextvars.ContextVar("gemini_key", default=None)

    # --- choosing a key ----------------------------------------------------------------------------------------------
    def _best(self, exclude=None):
        """The key with the most room: not resting, fewest analyses running, fewest tokens in the last minute.
        If every key is resting, the one that wakes up first."""
        now = time.time()
        candidates = [k for k in self.keys if k is not exclude] or self.keys
        awake = [k for k in candidates if not k.resting(now)]
        if not awake:
            return min(candidates, key=lambda k: k.resting_until)
        return min(awake, key=lambda k: (k.full(now), k.active, k.last_minute(now)[1]))

    @contextmanager
    def run(self):
        """Hold one key for a whole analysis. Nested runs (the locator inside the agent) reuse the outer key."""
        if self.current.get() is not None:
            yield self.current.get()
            return
        with self.lock:
            key = self._best()
            key.active += 1
        token = self.current.set(key)
        try:
            yield key
        finally:
            with self.lock:
                self.current.get().active -= 1        # the run may have moved to another key
            self.current.reset(token)

    def _move(self, old):
        """Move the current run from a key that hit its limit to the key with the most room."""
        with self.lock:
            new = self._best(exclude=old)
            if new is not old and self.current.get() is old:
                old.active -= 1
                new.active += 1
                self.current.set(new)
        return new

    def _rest(self, key):
        with self.lock:
            key.resting_until = time.time() + REST_SECONDS

    def _record(self, key, response):
        tokens = 0
        if getattr(response, "usage_metadata", None):
            tokens = (response.usage_metadata.prompt_token_count or 0) + \
                     (response.usage_metadata.candidates_token_count or 0)
        with self.lock:
            key.calls.append((time.time(), tokens))

    # --- the one function that calls the model ----------------------------------------------------------------------
    def generate(self, model, contents, config, on_event=None):
        """client.models.generate_content on the run's key, with failover between keys and waits when all are busy."""
        if not self.keys:
            raise RuntimeError("No Gemini API key configured (GEMINI_API_KEYS or GEMINI_API_KEY).")
        problem = "rate_limit"
        for attempt in range(MAX_ATTEMPTS):
            key = self.current.get()
            if key is None:                               # a call outside pool.run() (command line helpers)
                with self.lock:
                    key = self._best()
            now = time.time()
            if len(self.keys) > 1 and (key.resting(now) or key.full(now)):
                other = self._best(exclude=key)
                # move only to a key that is better off: awake, and with room unless this key is resting
                if not other.resting(now) and (key.resting(now) or not other.full(now)):
                    key = self._move(key) if self.current.get() is key else other
            if key.resting(time.time()):                  # every key is resting: wait, then try again
                self._wait(on_event)
                continue
            try:
                response = key.client.models.generate_content(model=model, contents=contents, config=config)
            except Exception as error:
                if _is_rate_limit(error):
                    problem = "daily_quota" if _is_daily_quota(error) else "rate_limit"
                    if len(self.keys) == 1:               # one key: the old policy, wait and retry the same key
                        self._wait(on_event)
                    else:
                        self._rest(key)                   # the next attempt moves to another key (or waits
                    continue                              # if every key is resting)
                if _is_overload(error):
                    problem = "overloaded"
                    self._wait(on_event)
                    continue
                raise
            self._record(key, response)
            return response
        raise ModelBusy(problem)

    @staticmethod
    def _wait(on_event):
        print(f"   (rate limit or overload, waiting {WAIT_SECONDS} seconds...)")
        if on_event:
            on_event({"type": "wait", "seconds": WAIT_SECONDS})
        time.sleep(WAIT_SECONDS)

    def status(self):
        """For the page: per key, analyses running, calls and tokens in the last minute, resting or not."""
        now = time.time()
        with self.lock:
            return [{"key": k.label, "running": k.active, "calls_last_minute": k.last_minute(now)[0],
                     "tokens_last_minute": k.last_minute(now)[1], "resting": k.resting(now)} for k in self.keys]


pool = KeyPool(read_keys())
