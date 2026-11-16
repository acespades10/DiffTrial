import asyncio
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import httpx
from pydantic import BaseModel, ValidationError

from .schemas import ProviderConfig


class ProviderError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class Cancelled(RuntimeError):
    pass


@dataclass
class Generation:
    value: BaseModel
    usage: dict


class Adapter(Protocol):
    async def generate(
        self, instructions: str, context: str, schema: type[BaseModel], cancelled: Callable[[], bool]
    ) -> Generation: ...
    async def check(self) -> dict: ...


class Probe(BaseModel):
    ready: bool


def parse_output(text, schema):
    text = text.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    try:
        return schema.model_validate_json(text)
    except (ValidationError, ValueError) as exc:
        raise ProviderError(
            "malformed_output", "Provider output did not match the required JSON schema"
        ) from exc


class HTTPAdapter:
    def __init__(self, config: ProviderConfig, transport=None):
        self.config = config
        self.http_transport = transport

    def headers(self):
        if self.config.kind == "ollama":
            return {}
        key = os.environ.get(self.config.key_env, "")
        if not key:
            raise ProviderError("missing_key", f"Set {self.config.key_env} in the local process environment")
        return {"Authorization": f"Bearer {key}"}

    async def models(self):
        if self.config.kind != "ollama":
            raise ProviderError("unsupported", "Installed model discovery is available for Ollama only")
        try:
            async with httpx.AsyncClient(timeout=10, transport=self.http_transport) as client:
                response = await client.get(f"{self.config.endpoint}/api/tags")
                self.check_status(response)
                return [m["name"] for m in response.json().get("models", [])]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise ProviderError(
                "unavailable", "Ollama is unavailable or returned an invalid model list"
            ) from exc

    @staticmethod
    def check_status(response):
        if response.is_success:
            return
        code = {
            401: "authentication",
            403: "authentication",
            404: "unsupported",
            400: "unsupported",
            422: "unsupported",
            429: "rate_limit",
        }.get(response.status_code, "upstream_error")
        raise ProviderError(
            code, f"Provider returned HTTP {response.status_code}; verify endpoint, model and transport"
        )

    async def check(self):
        if self.config.kind == "ollama" and self.config.model not in await self.models():
            raise ProviderError(
                "model_missing", "Selected model is not installed in Ollama. Pull it locally first."
            )
        result = await self.generate("Return JSON only.", 'Return {"ready":true}.', Probe, lambda: False)
        if not result.value.ready:
            raise ProviderError("probe_failed", "Provider did not confirm readiness")
        return {
            "verified": True,
            "model": self.config.model,
            "transport": self.config.transport,
            "usage": result.usage,
        }

    async def generate(self, instructions, context, schema, cancelled=lambda: False):
        task = asyncio.create_task(self._generate(instructions, context, schema))
        try:
            while not task.done():
                if cancelled():
                    raise Cancelled("Run cancelled or deadline reached")
                await asyncio.sleep(0.1)
            return await task
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def _generate(self, instructions, context, schema):
        contract = (
            instructions
            + "\nReturn exactly one JSON object conforming to this schema, with no markdown:\n"
            + json.dumps(schema.model_json_schema())
        )
        model = self.config.model
        if self.config.transport == "responses":
            path = "/responses"
            body = {
                "model": model,
                "instructions": contract,
                "input": [{"role": "user", "content": [{"type": "input_text", "text": context}]}],
                "stream": True,
                "store": False,
            }
        elif self.config.transport == "chat":
            path = "/chat/completions"
            body = {
                "model": model,
                "messages": [{"role": "system", "content": contract}, {"role": "user", "content": context}],
                "stream": False,
            }
        else:
            path = "/api/chat"
            body = {
                "model": model,
                "messages": [{"role": "system", "content": contract}, {"role": "user", "content": context}],
                "stream": False,
                "format": schema.model_json_schema(),
            }
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(120, connect=10), transport=self.http_transport, follow_redirects=False
            ) as client:
                async with client.stream(
                    "POST", self.config.endpoint + path, headers=self.headers(), json=body
                ) as response:
                    self.check_status(response)
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 1024 * 1024:
                            raise ProviderError("output_limit", "Provider response exceeded 1 MiB")
                    text, usage = self.decode(raw.decode(), response.headers.get("content-type", ""))
                    return Generation(parse_output(text, schema), usage)
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout", "Provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("connection", "Could not connect to the configured provider") from exc
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                "malformed_response", "Provider returned an unsupported response envelope"
            ) from exc

    def decode(self, raw, content_type):
        if self.config.transport == "responses":
            if "text/event-stream" in content_type or raw.startswith("data:") or raw.startswith("event:"):
                completed = None
                for line in raw.splitlines():
                    if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                        continue
                    item = json.loads(line[5:])
                    if item.get("type") in {"response.failed", "error", "response.incomplete"}:
                        raise ProviderError(
                            "generation_failed", "Provider reported an incomplete or failed generation"
                        )
                    if item.get("type") == "response.completed":
                        completed = item["response"]
                if completed is None:
                    raise ProviderError(
                        "incomplete_stream", "Responses stream ended without response.completed"
                    )
                data = completed
            else:
                data = json.loads(raw)
                if data.get("status") != "completed":
                    raise ProviderError("generation_failed", "Responses result was not completed")
            text = "".join(
                c["text"]
                for o in data.get("output", [])
                if o.get("type") == "message"
                for c in o.get("content", [])
                if c.get("type") == "output_text"
            )
            usage = data.get("usage") or {}
        elif self.config.transport == "chat":
            data = json.loads(raw)
            if data["choices"][0].get("finish_reason") != "stop":
                raise ProviderError("generation_failed", "Chat generation did not finish normally")
            text = data["choices"][0]["message"]["content"]
            u = data.get("usage") or {}
            usage = {"input_tokens": u.get("prompt_tokens"), "output_tokens": u.get("completion_tokens")}
        else:
            data = json.loads(raw)
            if not data.get("done"):
                raise ProviderError("generation_failed", "Ollama generation was incomplete")
            text = data["message"]["content"]
            usage = {"input_tokens": data.get("prompt_eval_count"), "output_tokens": data.get("eval_count")}
        normalized = {
            k: usage[k]
            for k in ("input_tokens", "output_tokens", "total_tokens")
            if isinstance(usage.get(k), int) and usage[k] >= 0
        }
        return text, normalized


class CodexLBAdapter(HTTPAdapter):
    """CodexLB's Responses SSE envelope, including the mandatory completion event."""


def adapter(config: ProviderConfig) -> HTTPAdapter:
    return CodexLBAdapter(config) if config.kind == "codexlb" else HTTPAdapter(config)
