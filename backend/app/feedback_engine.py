"""Deterministic fallback comments for grading results."""

from __future__ import annotations

from collections.abc import Iterable

from app.llm_feedback import generate_llm_comment


_SUBJECT_LABELS = {
    "数学": "数学作业",
    "语文": "语文作业",
    "英语": "英语作业",
    "math": "数学作业",
    "chinese": "语文作业",
    "english": "英语作业",
}

_ISSUE_RULES = (
    ("疑似错别字", "注意检查错别字，完成后再通读一遍。"),
    ("Possible spelling errors:", "注意拼写，建议整理并复习本次出现的易错词。"),
    ("Grammar notes:", "复习相关语法规则，并检查句子结构和动词形式。"),
    ("通顺度较弱", "尝试缩短过长句子，并补充必要的标点。"),
    ("结构完整度较弱", "先列出开头、展开和结尾，再组织完整段落。"),
    ("内容相关度较弱", "回到题目要求，补充与主题直接相关的内容。"),
    ("有错误", "检查计算和推理过程，特别是出现错误的步骤。"),
    ("有误", "检查计算和推理过程，特别是出现错误的步骤。"),
    ("差异较大", "重新核对题目条件和关键计算步骤。"),
    ("Vocabulary: needs improvement", "尝试使用更丰富的词汇，减少重复表达。"),
    ("Content relevance: needs improvement", "围绕题目补充更具体的内容和例子。"),
)


def _subject_label(subject: str | None) -> str:
    normalized = (subject or "").strip().lower()
    return _SUBJECT_LABELS.get(normalized, "本次作业")


def _issue_suggestions(feedback: Iterable[str]) -> list[str]:
    combined = " ".join(str(item) for item in feedback if item)
    suggestions: list[str] = []
    for marker, suggestion in _ISSUE_RULES:
        if marker.lower() in combined.lower() and suggestion not in suggestions:
            suggestions.append(suggestion)
    return suggestions[:3]


def generate_fallback_comment(
    subject: str | None,
    total_score: float,
    max_score: float,
    feedback: Iterable[str] = (),
) -> str:
    """Build a stable comment without external LLM or network dependencies."""
    label = _subject_label(subject)
    ratio = total_score / max_score if max_score > 0 else 0.0
    suggestions = _issue_suggestions(feedback)

    if ratio >= 0.90:
        opening = f"{label}完成得很好，基础掌握和综合表现都比较扎实。"
        closing = "继续保持认真审题和规范表达，争取把优势稳定下来。"
    elif ratio >= 0.60:
        opening = f"{label}整体完成情况较好，已经掌握了主要内容。"
        closing = "建议针对本次反馈进行订正，再做一组同类练习巩固。"
    else:
        opening = f"{label}已经完成，但基础内容还需要进一步巩固。"
        closing = "建议先订正错题，再按知识点分步骤练习。"

    if suggestions:
        return opening + " " + " ".join(suggestions) + " " + closing
    return opening + " " + closing


async def generate_comment(
    subject: str | None,
    total_score: float,
    max_score: float,
    feedback: Iterable[str] = (),
) -> str:
    """Prefer personalized feedback, but always keep grading available offline."""
    feedback_items = [str(item) for item in feedback if item]
    llm_comment = await generate_llm_comment(
        subject,
        total_score,
        max_score,
        feedback_items,
    )
    return llm_comment or generate_fallback_comment(
        subject,
        total_score,
        max_score,
        feedback_items,
    )
