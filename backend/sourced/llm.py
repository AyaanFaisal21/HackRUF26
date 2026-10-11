"""One thin seam for every model call. Three providers, same interface. Whichever key is present is used.

  parse(system, user, Model) -> Model      structured output validated against a Pydantic model
  text(system, user) -> str                free text (narratives)

Set LLM_PROVIDER=anthropic|openai|gemini to force one. Models: ANTHROPIC_MODEL (default claude-opus-5-5),
OPENAI_MODEL (default gpt-4.1), GEMINI_MODEL (default gemini-3.8-flash). Order when several keys are present: Anthropic,
OpenAI, Gemini. No key -> provider() returns None and callers fall back to deterministic output."""
from __future__ import annotations

import base64
import copy
import json
import os
from typing import Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

TRANSCRIBE = ("Transcribe this document exactly as written, as plain text. Keep the line breaks and the order on the page. "
              "Do not summarize, correct, translate, or add anything. Write [illegible] for anything you cannot read. "
              "If there are several images they are pages in order; put a line containing only <page> between pages.")


def _pages(text: str) -> str:
    return "\f".join(p.strip("\n") for p in text.split("<page>"))


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

    def transcribe(self, images: list[tuple[bytes, str]]) -> str:
        content = [{"type": "image", "source": {"type": "base64", "media_type": mt, "data": base64.b64encode(b).decode()}} for b, mt in images]
        content.append({"type": "text", "text": TRANSCRIBE})
        resp = self.client.messages.create(model=self.model, max_tokens=6000, messages=[{"role": "user", "content": content}])
        return _pages("".join(b.text for b in resp.content if b.type == "text"))


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

    def transcribe(self, images: list[tuple[bytes, str]]) -> str:
        content = [{"type": "text", "text": TRANSCRIBE}]
        content += [{"type": "image_url", "image_url": {"url": f"data:{mt};base64,{base64.b64encode(b).decode()}", "detail": "high"}} for b, mt in images]
        resp = self.client.chat.completions.create(model=self.model, max_tokens=6000, messages=[{"role": "user", "content": content}])
        return _pages(resp.choices[0].message.content or "")


class GeminiLLM:
    name = "gemini"

    def __init__(self, model: str | None = None):
        from google import genai
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

    def _config(self, system: str, **kw):
        from google.genai import types
        return types.GenerateContentConfig(system_instruction=system, **kw)

    def parse(self, system: str, user: str, model_cls: Type[T]) -> T:
        resp = self.client.models.generate_content(model=self.model, contents=user,
                                                   config=self._config(system, response_mime_type="application/json", response_schema=model_cls))
        if resp.parsed is None:
            return model_cls.model_validate_json(resp.text or "")
        return resp.parsed

    def text(self, system: str, user: str, max_tokens: int = 2000) -> str:
        resp = self.client.models.generate_content(model=self.model, contents=user, config=self._config(system, max_output_tokens=max_tokens))
        return resp.text or ""

    def transcribe(self, images: list[tuple[bytes, str]]) -> str:
        from google.genai import types
        parts = [types.Part.from_bytes(data=b, mime_type=mt) for b, mt in images] + [TRANSCRIBE]
        resp = self.client.models.generate_content(model=self.model, contents=parts)
        return _pages(resp.text or "")


def provider():
    if not os.environ.get("OPENAI_API_KEY") and os.environ.get("OPEN_AI_API_KEY"):   # common spelling in .env files
        os.environ["OPENAI_API_KEY"] = os.environ["OPEN_AI_API_KEY"]
    forced = os.environ.get("LLM_PROVIDER")
    if forced == "anthropic" or (not forced and os.environ.get("ANTHROPIC_API_KEY")):
        return AnthropicLLM()
    if forced == "openai" or (not forced and os.environ.get("OPENAI_API_KEY")):
        return OpenAILLM()
    if forced == "gemini" or (not forced and (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))):
        return GeminiLLM()
    return None
