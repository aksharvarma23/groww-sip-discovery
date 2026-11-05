"""Label one piece of text with the same codebook, using Google's Gemini API.

Used by the dashboard's "Try it" tab. Same system prompt and the same
validation as engine/label.py, so a live result is checked exactly like the
batch labels: labels outside the codebook are reset, and the evidence quote
must appear word for word in the text.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from codebook import FREE_FIELDS, MULTI_FIELDS, SINGLE_FIELDS  # noqa: E402
from label import SYSTEM, validate  # noqa: E402

DEFAULT_MODEL = "gemini-2.5-flash"


def _schema_hint() -> str:
    lines = ["Return ONE JSON object with exactly these keys:"]
    for k, d in SINGLE_FIELDS.items():
        lines.append(f'  "{k}": one of {list(d)}')
    for k, d in MULTI_FIELDS.items():
        lines.append(f'  "{k}": list of values from {list(d)}')
    for k in FREE_FIELDS:
        lines.append(f'  "{k}": string')
    lines.append('  "confidence": number between 0 and 1')
    return "\n".join(lines)


def _thinking(model: str):
    """Keep reasoning short: labelling is a lookup task, and a long think makes the demo hang."""
    from google.genai import types
    if model.startswith("gemini-2."):
        return types.ThinkingConfig(thinking_budget=0)
    return types.ThinkingConfig(thinking_level="low")


FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]


def _call(client, model, prompt, base, thinking: bool):
    from google.genai import types
    cfg = types.GenerateContentConfig(**base, thinking_config=_thinking(model)) if thinking \
        else types.GenerateContentConfig(**base)
    return client.models.generate_content(model=model, contents=prompt, config=cfg)


def label_text(text: str, api_key: str, model: str = DEFAULT_MODEL, timeout_s: int = 30,
               fallbacks: list[str] | None = None) -> dict:
    """Try the configured model, then fallbacks. Returns the validated labels plus
    `_model` (which model answered) and `_errors` (what failed on the way)."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key,
                          http_options=types.HttpOptions(timeout=timeout_s * 1000,
                                                         retry_options=types.HttpRetryOptions(attempts=1)))
    prompt = (_schema_hint() + "\n\nLabel this item.\n\n"
              + json.dumps({"id": "live", "source": "user_input", "context": "", "text": text[:1800]},
                           ensure_ascii=False))
    base = dict(system_instruction=SYSTEM, temperature=0, response_mime_type="application/json",
                max_output_tokens=1500)
    errors = []
    for m in dict.fromkeys([model] + (fallbacks if fallbacks is not None else FALLBACK_MODELS)):
        for thinking in (True, False):
            try:
                resp = _call(client, m, prompt, base, thinking)
                raw = json.loads(resp.text)
            except Exception as e:  # server error, timeout, bad JSON, unsupported setting
                errors.append(f"{m} (thinking={'low' if thinking else 'default'}): "
                              f"{e.__class__.__name__}: {str(e)[:160]}")
                continue
            if isinstance(raw, list):
                raw = raw[0]
            raw["id"] = "live"
            lab = validate(raw, text[:1800])
            lab["_model"], lab["_errors"] = m, errors
            return lab
    raise RuntimeError("All models failed:\n" + "\n".join(errors))
