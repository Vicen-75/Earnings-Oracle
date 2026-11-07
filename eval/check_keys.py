# --- Javier: check every Gemini key in the secrets, one tiny call each (code written with help from Claude) ---
# Tells which keys work and, for those that fail, which limit they hit (per day, per minute) or what else is wrong.
# Keys are shown as "key 1", "key 2"... in the order of GEMINI_API_KEYS, plus their last 4 characters so you can find
# them in AI Studio. The full key is never printed.
#
# Run from the repository root:   python -m eval.check_keys
import re
import time

from google.genai import types

from src.key_pool import pool
from src.llm import MODEL

CONFIG = types.GenerateContentConfig(max_output_tokens=5, thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"))


def diagnose(error):
    text = str(error)
    quota = re.findall(r'quotaId["\']?\s*[:=]\s*["\']?([A-Za-z0-9_-]+)', text)
    if "PerDay" in text:
        return "DAILY QUOTA USED UP" + (f" ({quota[0]})" if quota else "")
    if "429" in text or "RESOURCE_EXHAUSTED" in text:
        return "RATE LIMITED, per minute" + (f" ({quota[0]})" if quota else "")
    if "API_KEY_INVALID" in text or "API key not valid" in text:
        return "INVALID KEY"
    if "PERMISSION_DENIED" in text or "403" in text:
        return "PERMISSION DENIED (API not enabled for this project, or key restricted)"
    if "503" in text or "UNAVAILABLE" in text:
        return "GOOGLE OVERLOADED (try again in a minute)"
    return f"OTHER: {text[:160]}"


def main():
    print(f"{len(pool.keys)} key(s) in the secrets, model {MODEL}\n")
    working = 0
    for i, key in enumerate(pool.keys, start=1):
        try:
            tail = key.client._api_client.api_key[-4:]
        except Exception:
            tail = "????"
        try:
            key.client.models.generate_content(model=MODEL, contents="Say OK.", config=CONFIG)
            print(f"key {i:>2} (...{tail}): OK")
            working += 1
        except Exception as error:
            print(f"key {i:>2} (...{tail}): {diagnose(error)}")
        time.sleep(1)
    print(f"\n{working} of {len(pool.keys)} keys working right now.")
    print("Remember: keys from the SAME Google Cloud project share one quota, so working keys from one project "
          "still count as one.")


if __name__ == "__main__":
    main()
