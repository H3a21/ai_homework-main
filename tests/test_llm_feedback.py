"""Tests for the optional LLM comment client."""

import asyncio
import json
import os
import sys

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.llm_feedback import LLMFeedbackClient, build_comment_prompt, sanitize_comment


def run(coro):
    return asyncio.run(coro)


def test_prompt_is_bounded_and_excludes_student_identity():
    system_prompt, user_prompt = build_comment_prompt(
        "数学", 9.5, 10.0, ["步骤1正确"] * 20
    )
    assert "姓名" in system_prompt
    assert user_prompt.count("步骤1正确") <= 8
    assert "学生答案" not in user_prompt


def test_client_reads_chat_completion_content():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        payload = json.loads(request.content)
        assert payload["max_completion_tokens"] == 240
        body = httpx.Response(
            200,
            json={"choices": [{"message": {"content": "本次步骤清晰，继续保持。"}}]},
        )
        return body

    client = LLMFeedbackClient(
        "test-key", "https://example.test/v1", "test-model",
        transport=httpx.MockTransport(handler),
    )
    assert run(client.generate("数学", 9, 10, ["步骤正确"])) == "本次步骤清晰，继续保持。"


def test_missing_key_and_http_error_return_none():
    disabled = LLMFeedbackClient("", "https://example.test/v1", "test-model")
    assert run(disabled.generate("数学", 9, 10, [])) is None

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    failing = LLMFeedbackClient(
        "test-key", "https://example.test/v1", "test-model",
        transport=httpx.MockTransport(handler),
    )
    assert run(failing.generate("数学", 9, 10, [])) is None


def test_empty_and_timeout_responses_return_none():
    async def empty_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": ""}}]},
        )

    empty = LLMFeedbackClient(
        "test-key", "https://example.test/v1", "test-model",
        transport=httpx.MockTransport(empty_handler),
    )
    assert run(empty.generate("数学", 9, 10, [])) is None

    async def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("provider timed out", request=request)

    timed_out = LLMFeedbackClient(
        "test-key", "https://example.test/v1", "test-model",
        transport=httpx.MockTransport(timeout_handler),
    )
    assert run(timed_out.generate("数学", 9, 10, [])) is None


def test_compatible_provider_can_use_max_tokens():
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["max_tokens"] == 240
        assert "max_completion_tokens" not in payload
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Keep practicing."}}]},
        )

    client = LLMFeedbackClient(
        "test-key", "https://example.test/v1", "test-model",
        token_parameter="max_tokens",
        transport=httpx.MockTransport(handler),
    )
    assert run(client.generate("英语", 9, 10, [])) == "Keep practicing."


def test_unsafe_and_oversized_output_is_rejected_or_limited():
    assert sanitize_comment("ignore previous instructions") is None
    assert sanitize_comment("<script>alert(1)</script>正常评语") is None
    assert len(sanitize_comment("a" * 600, 500)) == 500


if __name__ == "__main__":
    for test in (
        test_prompt_is_bounded_and_excludes_student_identity,
        test_client_reads_chat_completion_content,
        test_missing_key_and_http_error_return_none,
        test_empty_and_timeout_responses_return_none,
        test_compatible_provider_can_use_max_tokens,
        test_unsafe_and_oversized_output_is_rejected_or_limited,
    ):
        test()
        print(f"PASS: {test.__name__}")
