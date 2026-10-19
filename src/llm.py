# --- Vicente: Gemini helper, adapted from IS883 Session 4 Part 0 (code written with help from Claude) ---
import os
import time
from google import genai
from google.genai import types

MODEL = "gemini-3.1-flash-lite"


def get_api_key():
    """Read the key from Streamlit Cloud secrets, or from an environment variable. Never hard-code it."""
    try:
        import streamlit as st
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.environ.get("GEMINI_API_KEY")


client = genai.Client(api_key=get_api_key())


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
    for attempt in range(4):
        try:
            response = client.models.generate_content(model=MODEL, contents=prompt, config=config)
        except Exception as error:
            if "429" in str(error) or "503" in str(error):
                print("   (rate limit or overload, waiting 15 seconds...)")
                time.sleep(15)
                continue
            raise
        if show_usage:
            print("tokens in/out:", response.usage_metadata.prompt_token_count,
                  response.usage_metadata.candidates_token_count)
        return response.text or "[the model returned no text]"
    return "[gave up after repeated retries]"
