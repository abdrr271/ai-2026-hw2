"""Shared, deliberately small plumbing for the three HW2 experiments.

The assignment compares prompts and context, so this module keeps provider
selection and defensive JSON handling identical in every sublab.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
load_dotenv(ROOT / ".env")


def model_settings() -> tuple[OpenAI, str, str]:
    """Return one OpenAI-compatible client and the model used in every run."""
    router_key = os.environ.get("OPENROUTER_API_KEY")
    if router_key:
        return (
            OpenAI(api_key=router_key, base_url="https://openrouter.ai/api/v1", timeout=75),
            # This is the one model used by all three sublabs unless the
            # student deliberately overrides it in their ignored .env.
            os.environ.get("OPENROUTER_MODEL", "qwen/qwen3.8-27b"),
            "openrouter",
        )
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        return OpenAI(api_key=openai_key, timeout=75), "gpt-5.6-luna", "openai"
    raise RuntimeError(
        "Set OPENROUTER_API_KEY or OPENAI_API_KEY in .env. The key is never printed."
    )


def call_model(messages: list[dict[str, str]], *, max_tokens: int = 700,
               temperature: float = 0.0) -> dict[str, Any]:
    """Make one non-streaming chat call and preserve provider-reported usage."""
    client, model, provider = model_settings()
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if provider == "openrouter":
        kwargs["extra_body"] = {"reasoning": {"effort": "none"}}
    response = client.chat.completions.create(**kwargs)
    usage = response.usage
    return {
        "text": response.choices[0].message.content or "",
        "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        "model": model,
        "provider": provider,
    }


def parse_json_object(text: str) -> dict[str, Any]:
    """Accept clean JSON, a fenced object, or an object wrapped in brief prose."""
    text = text.strip()
    candidates = [text]
    candidates.extend(re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I))
    candidates.extend(text[index:] for index, char in enumerate(text) if char == "{")
    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            value, _ = decoder.raw_decode(candidate.lstrip())
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("model reply did not contain a JSON object: " + repr(text[:300]))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
