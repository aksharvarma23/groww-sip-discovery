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


def label_text(text: str, api_key: str, model: str = DEFAULT_MODEL, timeout_s: int = 40) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key,
                          http_options=types.HttpOptions(timeout=timeout_s * 1000,
                                                         retry_options=types.HttpRetryOptions(attempts=1)))
    prompt = (_schema_hint() + "\n\nLabel this item.\n\n"
              + json.dumps({"id": "live", "source": "user_input", "context": "", "text": text[:1800]},
                           ensure_ascii=False))
    base = dict(system_instruction=SYSTEM, temperature=0, response_mime_type="application/json",
                max_output_tokens=1200)
    try:
        cfg = types.GenerateContentConfig(**base, thinking_config=_thinking(model))
        resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
    except Exception as e:  # some models reject a thinking setting; retry once without it
        if "thinking" not in str(e).lower():
            raise
        resp = client.models.generate_content(model=model, contents=prompt,
                                              config=types.GenerateContentConfig(**base))
    raw = json.loads(resp.text)
    if isinstance(raw, list):
        raw = raw[0]
    raw["id"] = "live"
    return validate(raw, text[:1800])
