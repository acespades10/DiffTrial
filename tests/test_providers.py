import asyncio
import json

import httpx
import pytest
from difftrial.providers import Cancelled, HTTPAdapter, Probe, ProviderError, parse_output
from difftrial.schemas import ProviderConfig
from pydantic import ValidationError


def response_payload():
    return {
        "status": "completed",
        "output": [{"type": "message", "content": [{"type": "output_text", "text": '{"ready":true}'}]}],
        "usage": {"input_tokens": 10, "output_tokens": 4},
    }


async def test_codexlb_actual_responses_envelope(config, monkeypatch):
    monkeypatch.setenv("CODEX_LB_API_KEY", "test-key")

    async def serve(request):
        body = json.loads(request.content)
        assert request.url.path == "/v1/responses"
        assert body["stream"] is True and body["store"] is False
        assert body["input"][0]["content"][0]["type"] == "input_text"
        assert request.headers["Authorization"] == "Bearer test-key"
        event = {"type": "response.completed", "response": response_payload()}
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, text="data: " + json.dumps(event) + "\n\n"
        )

    result = await HTTPAdapter(config, httpx.MockTransport(serve)).check()
    assert result["verified"] and result["usage"]["input_tokens"] == 10


@pytest.mark.parametrize("transport", ["responses", "chat", "ollama"])
async def test_transports(transport, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    config = ProviderConfig(
        kind="ollama" if transport == "ollama" else "compatible",
        transport=transport,
        endpoint="http://127.0.0.1:11434",
        model="test",
        key_env="OPENAI_API_KEY",
    )

    def serve(request):
        if transport == "responses":
            return httpx.Response(200, json=response_payload())
        if transport == "chat":
            return httpx.Response(
                200,
                json={
                    "choices": [{"finish_reason": "stop", "message": {"content": '{"ready":true}'}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 2},
                },
            )
        return httpx.Response(
            200,
            json={
                "done": True,
                "message": {"content": '{"ready":true}'},
                "prompt_eval_count": 1,
                "eval_count": 2,
            },
        )

    result = await HTTPAdapter(config, httpx.MockTransport(serve)).generate("JSON", "probe", Probe)
    assert result.value.ready


@pytest.mark.parametrize(
    "status,code",
    [(401, "authentication"), (429, "rate_limit"), (404, "unsupported"), (500, "upstream_error")],
)
async def test_normalized_provider_errors(config, monkeypatch, status, code):
    monkeypatch.setenv("CODEX_LB_API_KEY", "test-key")
    transport = httpx.MockTransport(lambda _: httpx.Response(status, text="sensitive upstream diagnostic"))
    with pytest.raises(ProviderError) as caught:
        await HTTPAdapter(config, transport).check()
    assert caught.value.code == code
    assert "sensitive" not in str(caught.value)


@pytest.mark.parametrize("value", ["not json", '{"ready":"notboolean"}', "{}"])
def test_malformed_structured_output(value):
    with pytest.raises(ProviderError, match="required JSON schema"):
        parse_output(value, Probe)


async def test_provider_cancellation_closes_request(config, monkeypatch):
    monkeypatch.setenv("CODEX_LB_API_KEY", "test-key")
    stopped = asyncio.Event()

    async def slow(request):
        try:
            await asyncio.sleep(10)
        finally:
            stopped.set()

    adapter = HTTPAdapter(config, httpx.MockTransport(slow))
    with pytest.raises(Cancelled):
        await adapter.generate("", "", Probe, lambda: True)
    assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]


def test_responses_requires_completion(config):
    with pytest.raises(ProviderError) as caught:
        HTTPAdapter(config).decode(
            'data: {"type":"response.output_text.delta","delta":"ok"}\n', "text/event-stream"
        )
    assert caught.value.code == "incomplete_stream"


def test_provider_configuration_validation():
    with pytest.raises(ValidationError):
        ProviderConfig(kind="codexlb", transport="chat", endpoint="https://x.example", model="m")
    with pytest.raises(ValidationError):
        ProviderConfig(endpoint="https://user:secret@x.example", model="m")
