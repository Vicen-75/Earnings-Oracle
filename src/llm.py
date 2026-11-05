# --- Vicente: Gemini helper, adapted from IS883 Session 4 Part 0 (code written with help from Claude) ---
from google.genai import types

from src.key_pool import pool

MODEL = "gemini-3.1-flash-lite"


# Nov 6 (Javier): keys now live in src/key_pool.py, which can hold several keys from different projects
# (GEMINI_API_KEYS in the secrets) and spreads analyses across them. The single GEMINI_API_KEY still works.
client = pool.keys[0].client if pool.keys else None      # kept for older scripts; new code calls pool.generate()


def ask_gemini(prompt, system_instruction=None, seed=None, temperature=None,
               max_output_tokens=None, response_schema=None, show_usage=False):
    """Send ONE request to Gemini and return its text, retrying if the free tier is busy."""
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        seed=seed,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        response_mime_type="application/json" if response_schema else None,
        response_schema=response_schema,
        thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
    )
    try:
        response = pool.generate(MODEL, prompt, config)
    except RuntimeError:
        return "[gave up after repeated retries]"
    if show_usage:
        print("tokens in/out:", response.usage_metadata.prompt_token_count,
              response.usage_metadata.candidates_token_count)
    return response.text or "[the model returned no text]"
