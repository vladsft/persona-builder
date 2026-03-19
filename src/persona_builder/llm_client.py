"""
Unified LLM client abstraction.

Reads LLM_PROVIDER from env ("anthropic", "openai", or "gemini") and
dispatches to the matching SDK.  Callers use only two functions:

    create(model, system, messages, max_tokens) -> str
    stream(model, system, messages, max_tokens) -> Iterator[str]
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

# ---------------------------------------------------------------------------
# Provider helpers
# ---------------------------------------------------------------------------

_PROVIDER_KEY_MAP = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


def get_provider() -> str:
    """Return the active LLM provider name (lowercase)."""
    return os.getenv("LLM_PROVIDER", "anthropic").lower()


def get_api_key(provider: str | None = None) -> str:
    """Return the API key for the given (or active) provider."""
    provider = provider or get_provider()
    env_var = _PROVIDER_KEY_MAP.get(provider)
    if not env_var:
        raise ValueError(f"Unknown LLM provider: {provider!r}")
    key = os.getenv(env_var, "")
    if not key:
        raise RuntimeError(
            f"API key not set: please set {env_var} in .env or environment."
        )
    return key


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


def _make_cached_system(system: str) -> list[dict[str, Any]]:
    """Wrap the system prompt as a cacheable content block (Anthropic prompt caching).

    The cache has a 5-minute TTL that resets on each hit, so within a chat
    session the ~4 200-token system prompt is billed at 10% after the first call.
    """
    return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]


def _anthropic_create(
    model: str,
    system: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=get_api_key("anthropic"))
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=_make_cached_system(system),
        messages=messages,
    )
    return response.content[0].text


def _anthropic_stream(
    model: str,
    system: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> Iterator[str]:
    import anthropic

    client = anthropic.Anthropic(api_key=get_api_key("anthropic"))
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=_make_cached_system(system),
        messages=messages,
    ) as stream:
        yield from stream.text_stream


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


def _openai_create(
    model: str,
    system: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=get_api_key("openai"))
    oai_messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    oai_messages.extend(messages)
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=oai_messages,
    )
    return response.choices[0].message.content or ""


def _openai_stream(
    model: str,
    system: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> Iterator[str]:
    from openai import OpenAI

    client = OpenAI(api_key=get_api_key("openai"))
    oai_messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    oai_messages.extend(messages)
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=oai_messages,
        stream=True,
    )
    for chunk in response:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


# ---------------------------------------------------------------------------
# Google Gemini
# ---------------------------------------------------------------------------


def _gemini_create(
    model: str,
    system: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=get_api_key("gemini"))
    contents = _messages_to_gemini_contents(messages)
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
        ),
    )
    return response.text or ""


def _gemini_stream(
    model: str,
    system: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> Iterator[str]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=get_api_key("gemini"))
    contents = _messages_to_gemini_contents(messages)
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
        ),
    ):
        if chunk.text:
            yield chunk.text


def _messages_to_gemini_contents(
    messages: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Convert OpenAI-style messages to Gemini contents format."""
    contents: list[dict[str, Any]] = []
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    return contents


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_CREATE_DISPATCH = {
    "anthropic": _anthropic_create,
    "openai": _openai_create,
    "gemini": _gemini_create,
}

_STREAM_DISPATCH = {
    "anthropic": _anthropic_stream,
    "openai": _openai_stream,
    "gemini": _gemini_stream,
}


def create(
    model: str,
    system: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> str:
    """Return a complete text response (non-streaming)."""
    provider = get_provider()
    fn = _CREATE_DISPATCH.get(provider)
    if not fn:
        raise ValueError(f"Unknown LLM provider: {provider!r}")
    return fn(model, system, messages, max_tokens)


def stream(
    model: str,
    system: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> Iterator[str]:
    """Yield text chunks as they arrive (streaming)."""
    provider = get_provider()
    fn = _STREAM_DISPATCH.get(provider)
    if not fn:
        raise ValueError(f"Unknown LLM provider: {provider!r}")
    yield from fn(model, system, messages, max_tokens)
