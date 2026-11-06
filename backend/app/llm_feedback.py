"""Optional OpenAI-compatible personalized grading comments."""

from __future__ import annotations

import re
from collections.abc import Iterable

import httpx

from app.config import settings


_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_UNSAFE_OUTPUT = re.compile(
    r"(?:ignore\s+(?:all\s+)?previous|system\s+message|developer\s+message|"
    r"api[_ -]?key|sk-[a-zA-Z0-9]{10,}|<\s*script|https?://)",
    re.IGNORECASE,
)


def _clean_input(value: str | None, limit: int) -> str:
    text = _CONTROL_CHARACTERS.sub(" ", str(value or ""))
    return " ".join(text.split())[:limit].strip()


def build_comment_prompt(
    subject: str | None,
    total_score: float,
    max_score: float,
    feedback: Iterable[str],
) -> tuple[str, str]:
    """Build a bounded prompt containing grading evidence, not student identity."""
    subject_text = _clean_input(subject, 40) or "本次作业"
    feedback_lines = []
    for index, item in enumerate(feedback):
        if index >= 8:
            break
        cleaned = _clean_input(item, 240)
        if cleaned:
            feedback_lines.append(f"- {cleaned}")
    evidence = "\n".join(feedback_lines) or "- 未提供逐题文字反馈"
    system_prompt = (
        "你是一个谨慎的作业批改反馈助手。只根据给出的学科、分数和逐题反馈写总评，"
        "不得编造未出现的错误，不得输出姓名、联系方式、密钥、链接或任何隐私信息。"
        "输出2到4句简洁评语，不使用标题、Markdown或项目符号；数学和语文使用中文，"
        "英语使用自然简洁的英文。"
    )
    user_prompt = (
        f"学科：{subject_text}\n"
        f"总分：{total_score:.1f}/{max_score:.1f}\n"
        f"逐题反馈：\n{evidence}\n"
        "请给出一段具体、鼓励但不过度夸大的学习建议。"
    )
    return system_prompt, user_prompt


def sanitize_comment(value: object, max_chars: int = 500) -> str | None:
    """Reject prompt-injection-like or sensitive output before storing it."""
    if not isinstance(value, str):
        return None
    if _UNSAFE_OUTPUT.search(value):
        return None
    text = _CONTROL_CHARACTERS.sub(" ", value)
    text = re.sub(r"```+", "", text)
    text = re.sub(r"<[^>]{0,200}>", "", text)
    text = " ".join(text.split()).strip()
    if not text:
        return None
    return text[:max_chars].rstrip() or None


class LLMFeedbackClient:
    """Small dependency-light client for OpenAI and compatible Chat APIs."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 8.0,
        max_completion_tokens: int = 240,
        max_output_chars: int = 500,
        token_parameter: str = "max_completion_tokens",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.model = model.strip()
        self.timeout_seconds = timeout_seconds
        self.max_completion_tokens = max_completion_tokens
        self.max_output_chars = max_output_chars
        self.token_parameter = (
            token_parameter
            if token_parameter in {"max_completion_tokens", "max_tokens"}
            else "max_completion_tokens"
        )
        self.transport = transport

    @classmethod
    def from_settings(cls) -> "LLMFeedbackClient":
        return cls(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            model=settings.LLM_MODEL,
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
            max_completion_tokens=settings.LLM_MAX_COMPLETION_TOKENS,
            max_output_chars=settings.LLM_MAX_OUTPUT_CHARS,
            token_parameter=settings.LLM_TOKEN_PARAMETER,
        )

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    @property
    def endpoint(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    async def generate(
        self,
        subject: str | None,
        total_score: float,
        max_score: float,
        feedback: Iterable[str],
    ) -> str | None:
        if not self.enabled or max_score < 0:
            return None

        system_prompt, user_prompt = build_comment_prompt(
            subject, total_score, max_score, feedback
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "n": 1,
        }
        payload[self.token_parameter] = self.max_completion_tokens
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(self.endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content")
            return sanitize_comment(content, self.max_output_chars)
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            return None


async def generate_llm_comment(
    subject: str | None,
    total_score: float,
    max_score: float,
    feedback: Iterable[str],
) -> str | None:
    return await LLMFeedbackClient.from_settings().generate(
        subject, total_score, max_score, feedback
    )
