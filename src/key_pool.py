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
#
# Nov 10 (Javier, load test in eval/load_test.py): 6 analyses at once ran cleanly, 12 at once failed twice on every key
# at the same moment with "overloaded" and an unnamed "resource exhausted". Google throttles our total free-tier traffic,
# not each project, so more keys do not buy more analyses at once. Changes:
#   - Only ACTIVE_KEYS keys (default 4) are used at a time: the first 4 in the secrets that still have daily quota.
#     When a key runs out of its daily quota (Google names a ...PerDay limit) it is retired until midnight Pacific and
#     the next unused key takes its place (rolling replacement), so 4 keys stay active until all are spent.
#     Retirements are saved in cache/key_state.json, so a restarted run does not retry spent keys.
#   - An unnamed 429 or a 503 means Google is busy, not that the key is spent: the run stays on its key and waits
#     5, 10, 20, 40, then 60 seconds between tries. Batch runs (pool.patient = True: the backtest and the test-set
#     builder) keep trying for up to PATIENT_SECONDS; the app gives up after about a minute.
#   - A named per-minute limit keeps the old behavior: the key rests a minute and the run moves to another active key.
import contextvars
import json
import os
import re
import threading
import time
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google import genai

REQUESTS_PER_MINUTE = 15          # per project, free tier (AI Studio, Oct 2026)
TOKENS_PER_MINUTE = 250_000       # per project, free tier: assumed, verify in AI Studio
REST_SECONDS = 60                 # a key that hit its limit is not used again for this long
WAIT_SECONDS = 15                 # wait when every key is resting (same as the old retry policy)
MAX_ATTEMPTS = 6                  # named per-minute limits, as before
ACTIVE_KEYS = 4                   # keys used at a time (Nov 10); override with ACTIVE_KEYS in the secrets or environment
BACKOFF_SECONDS = [5, 10, 20, 40, 60]   # waits on the same key when Google is busy; then 60 s each
PATIENT_SECONDS = 15 * 60         # batch runs keep trying this long on a busy Google before giving up
APP_BUSY_SECONDS = 60             # the app gives up sooner, so a visitor is not left waiting
STATE_PATH = Path("cache/key_state.json")
SECONDS_BETWEEN_CALLS = 0.5       # Nov 6: at least this long between any two model calls, across all keys, so a batch
                                  # of runs starting together does not hit Google as one burst


class ModelBusy(RuntimeError):
    """Raised when every retry failed. kind: "daily_quota" (the keys' free daily requests are used up),
    "rate_limit" (too many requests this minute), or "overloaded" (Google's side). The app words its message on it.
    A RuntimeError, so code that caught the old "gave up after repeated retries" error still catches this."""

    def __init__(self, kind):
        self.kind = kind
        super().__init__(f"gave up after repeated retries ({kind})")


def _is_daily_quota(error):
    return "PerDay" in str(error)                 # Gemini names the exhausted quota, e.g. ...RequestsPerDay...


_reported = set()


def _report_limit(key, error):
    """Print, once per key and limit, which Google quota a 429 named (e.g. ...InputTokensPerModelPerMinute...)."""
    import re
    names = re.findall(r"quota(?:_?[Ii]d|Metric)['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_./-]+)", str(error))
    name = names[0] if names else str(error)[:200].replace("\n", " ")
    if (key.label, name) not in _reported:
        _reported.add((key.label, name))
        print(f"   [{key.label}] limit hit: {name}")


def _names_a_quota(error):
    """True when the 429 says which quota ran out. The unnamed 'Resource has been exhausted' means Google is busy."""
    return bool(re.search(r"quota(?:_?[Ii]d|Metric)|PerMinute|PerDay|free_tier", str(error)))


def pacific_day():
    """Today's date in California, where the free daily quota resets at midnight."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    except Exception:                                   # no time zone data (Windows without tzdata): Pacific standard
        return (datetime.now(timezone.utc) - timedelta(hours=8)).date().isoformat()


def _setting(name, default):
    try:
        import streamlit as st
        value = st.secrets.get(name)
    except Exception:
        value = None
    value = value or os.environ.get(name)
    return int(value) if value else default


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
        self.retired_on = None                           # Pacific date its daily quota ran out
        self.calls = deque()                             # (time, tokens) of calls in the last minute
        self.resting_until = 0.0

    def last_minute(self, now):
        while self.calls and now - self.calls[0][0] > 60:
            self.calls.popleft()
        return len(self.calls), sum(tokens for _, tokens in self.calls)

    def resting(self, now):
        return now < self.resting_until

    def retired(self):
        return self.retired_on == pacific_day()

    def full(self, now):
        requests, tokens = self.last_minute(now)
        return requests >= REQUESTS_PER_MINUTE or tokens >= TOKENS_PER_MINUTE


class KeyPool:
    def __init__(self, api_keys):
        self.keys = [Key(i + 1, k) for i, k in enumerate(api_keys)]
        self.active_size = _setting("ACTIVE_KEYS", ACTIVE_KEYS)
        self.patient = False                             # batch scripts set True: wait out a busy Google for longer
        self.lock = threading.Lock()
        self._load_state()
        self.current = contextvars.ContextVar("gemini_key", default=None)
        self.pace_lock = threading.Lock()
        self.last_call = 0.0
        # --- Vicente (issue #55): a meter per analysis, so the cost counts EVERY call of the run (main agent, MD&A
        # locator, anonymizer brand scan) and the thinking tokens, which Google bills as output.
        self.meter = contextvars.ContextVar("usage_meter", default=None)

    # --- daily quota: which keys are active ---------------------------------------------------------------------------
    def _tail(self, key):
        try:
            return key.client._api_client.api_key[-4:]
        except Exception:
            return key.label

    def _load_state(self):
        """Keys retired today, from an earlier run (matched by the key's last 4 characters, never the full key)."""
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return
        if state.get("day") != pacific_day():
            return
        for key in self.keys:
            if self._tail(key) in state.get("retired", []):
                key.retired_on = state["day"]

    def _save_state(self):
        try:
            STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            STATE_PATH.write_text(json.dumps({"day": pacific_day(),
                                              "retired": [self._tail(k) for k in self.keys if k.retired()]}),
                                  encoding="utf-8")
        except Exception:                                # a read-only disk must not stop an analysis
            pass

    def active_keys(self):
        """The first ACTIVE_KEYS keys that still have daily quota, in secrets order (rolling replacement)."""
        return [k for k in self.keys if not k.retired()][:self.active_size]

    def capacity(self):
        """How many analyses can run at once: one per active key."""
        return len(self.active_keys())

    def _retire(self, key):
        with self.lock:
            if not key.retired():
                key.retired_on = pacific_day()
                self._save_state()
                print(f"   [{key.label}] daily quota used up: retired until midnight Pacific; "
                      f"active now: {', '.join(k.label for k in self.active_keys()) or 'none'}")

    # --- choosing a key ----------------------------------------------------------------------------------------------
    def _best(self, exclude=None):
        """The active key with the most room: not resting, fewest analyses running, fewest tokens in the last minute.
        If every active key is resting, the one that wakes up first."""
        now = time.time()
        active = self.active_keys()
        if not active:
            raise ModelBusy("daily_quota")
        candidates = [k for k in active if k is not exclude] or active
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
        meter_token = self.meter.set({"model_calls": 0, "prompt_tokens": 0, "output_tokens": 0, "thinking_tokens": 0})
        try:
            yield key
        finally:
            with self.lock:
                self.current.get().active -= 1        # the run may have moved to another key
            self.current.reset(token)
            self.meter.reset(meter_token)

    def usage(self):
        """Everything the current analysis has used so far, across all its model calls (issue #55)."""
        return dict(self.meter.get() or {})

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
        meter = self.meter.get()
        u = getattr(response, "usage_metadata", None)
        if u:
            tokens = (u.prompt_token_count or 0) + (u.candidates_token_count or 0)
        if meter is not None:
            meter["model_calls"] += 1
            if u:
                meter["prompt_tokens"] += u.prompt_token_count or 0
                meter["output_tokens"] += u.candidates_token_count or 0
                meter["thinking_tokens"] += getattr(u, "thoughts_token_count", 0) or 0
        with self.lock:
            key.calls.append((time.time(), tokens))

    # --- the one function that calls the model ----------------------------------------------------------------------
    def generate(self, model, contents, config, on_event=None):
        """client.models.generate_content on the run's key, with failover between keys and waits when all are busy."""
        if not self.keys:
            raise RuntimeError("No Gemini API key configured (GEMINI_API_KEYS or GEMINI_API_KEY).")
        problem = "rate_limit"
        named_failures, busy_since, busy_tries = 0, None, 0
        while named_failures < MAX_ATTEMPTS:
            key = self.current.get()
            if key is None:                               # a call outside pool.run() (command line helpers)
                with self.lock:
                    key = self._best()
            elif key.retired():                           # its daily quota ran out: move to a key that has some
                key = self._move(key)
                if key.retired():
                    raise ModelBusy("daily_quota")
            now = time.time()
            if len(self.keys) > 1 and (key.resting(now) or key.full(now)):
                other = self._best(exclude=key)
                # move only to a key that is better off: awake, and with room unless this key is resting
                if not other.resting(now) and (key.resting(now) or not other.full(now)):
                    key = self._move(key) if self.current.get() is key else other
            if key.resting(time.time()):                  # every key is resting: wait, then try again
                named_failures += 1
                self._wait(on_event, "every key rate-limited" if problem == "rate_limit" else problem)
                continue
            self._pace()
            try:
                response = key.client.models.generate_content(model=model, contents=contents, config=config)
            except Exception as error:
                busy = _is_overload(error) or (_is_rate_limit(error) and not _names_a_quota(error))
                if busy:                                  # Google is busy: stay on this key and back off
                    _report_limit(key, error)
                    problem = "overloaded"
                    busy_since = busy_since or time.time()
                    limit = PATIENT_SECONDS if self.patient else APP_BUSY_SECONDS
                    if time.time() - busy_since > limit:
                        raise ModelBusy(problem)
                    wait = BACKOFF_SECONDS[min(busy_tries, len(BACKOFF_SECONDS) - 1)]
                    busy_tries += 1
                    self._wait(on_event, problem, wait)
                    continue
                if _is_rate_limit(error):
                    _report_limit(key, error)
                    if _is_daily_quota(error):            # spent for today: retire it, the next key takes its place
                        problem = "daily_quota"
                        self._retire(key)
                        continue
                    problem = "rate_limit"
                    named_failures += 1
                    if len(self.active_keys()) == 1:      # one key: the old policy, wait and retry the same key
                        self._wait(on_event, problem)
                    else:
                        self._rest(key)                   # the next attempt moves to another key (or waits
                    continue                              # if every key is resting)
                raise
            self._record(key, response)
            return response
        raise ModelBusy(problem)

    def _pace(self):
        """Space out call starts across all keys and threads."""
        with self.pace_lock:
            wait = SECONDS_BETWEEN_CALLS - (time.time() - self.last_call)
            if wait > 0:
                time.sleep(wait)
            self.last_call = time.time()

    @staticmethod
    def _wait(on_event, reason="rate_limit", seconds=None):
        seconds = seconds or WAIT_SECONDS
        labels = {"overloaded": "Google busy (503 or unnamed 429)", "daily_quota": "daily quota used up",
                  "rate_limit": "rate limit", "every key rate-limited": "every key rate-limited"}
        print(f"   ({labels.get(reason, reason)}, waiting {seconds} seconds...)")
        if on_event:
            on_event({"type": "wait", "seconds": seconds, "reason": reason})
        time.sleep(seconds)

    def status(self):
        """For the page: per key, analyses running, calls and tokens in the last minute, resting or not."""
        now = time.time()
        with self.lock:
            active = self.active_keys()
            return [{"key": k.label, "running": k.active, "calls_last_minute": k.last_minute(now)[0],
                     "tokens_last_minute": k.last_minute(now)[1], "resting": k.resting(now),
                     "active": k in active, "retired": k.retired()} for k in self.keys]


pool = KeyPool(read_keys())
