"""One thin seam for every model call. Two providers, same interface. Whichever key is present is used.

  parse(system, user, Model) -> Model      structured output validated against a Pydantic model
  text(system, user) -> str                free text (narratives)

Set LLM_PROVIDER=anthropic|openai to force one. Models: ANTHROPIC_MODEL (default claude-opus-5-5),
OPENAI_MODEL (default gpt-4.1). No key -> provider() returns None and callers fall back to deterministic output."""
from __future__ import annotations

import copy
import json
import os
from typing import Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def strict_schema(model_cls: Type[BaseModel]) -> dict:
    """Pydantic JSON schema -> strict schema: every property required, no defaults, no additionalProperties."""
    def fix(node):
        if isinstance(node, dict):
            node.pop("default", None)
            node.pop("title", None)
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            for v in node.values():
                fix(v)
        elif isinstance(node, list):
            for v in node:
                fix(v)
        return node
    return fix(copy.deepcopy(model_cls.model_json_schema()))


class AnthropicLLM:
    name = "anthropic"

    def __init__(self, model: str | None = None):
        import anthropic
        self.client = anthropic.Anthropic()
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-opus-5-5")

    def parse(self, system: str, user: str, model_cls: Type[T]) -> T:
        resp = self.client.messages.parse(
            model=self.model, max_tokens=8000,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}], output_format=model_cls)
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"model refused: {resp.stop_details}")
        if resp.parsed_output is None:
            raise RuntimeError(f"no structured output (stop_reason={resp.stop_reason})")
        return resp.parsed_output

    def text(self, system: str, user: str, max_tokens: int = 2000) -> str:
        resp = self.client.messages.create(model=self.model, max_tokens=max_tokens, system=system, messages=[{"role": "user", "content": user}])
        return "".join(b.text for b in resp.content if b.type == "text")


class OpenAILLM:
    name = "openai"

    def __init__(self, model: str | None = None):
        from openai import OpenAI
        self.client = OpenAI()
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4.1")

    def parse(self, system: str, user: str, model_cls: Type[T]) -> T:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_schema", "json_schema": {"name": model_cls.__name__, "strict": True, "schema": strict_schema(model_cls)}})
        msg = resp.choices[0].message
        if getattr(msg, "refusal", None):
            raise RuntimeError(f"model refused: {msg.refusal}")
        return model_cls.model_validate_json(msg.content)

    def text(self, system: str, user: str, max_tokens: int = 2000) -> str:
        resp = self.client.chat.completions.create(model=self.model, max_tokens=max_tokens,
                                                   messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        return resp.choices[0].message.content or ""


def provider():
    if not os.environ.get("OPENAI_API_KEY") and os.environ.get("OPEN_AI_API_KEY"):   # common spelling in .env files
        os.environ["OPENAI_API_KEY"] = os.environ["OPEN_AI_API_KEY"]
    forced = os.environ.get("LLM_PROVIDER")
    if forced == "anthropic" or (not forced and os.environ.get("ANTHROPIC_API_KEY")):
        return AnthropicLLM()
    if forced == "openai" or (not forced and os.environ.get("OPENAI_API_KEY")):
        return OpenAILLM()
    return None
