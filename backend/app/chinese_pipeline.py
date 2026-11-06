"""Deterministic, explainable grading helpers for Chinese compositions."""

from __future__ import annotations

from dataclasses import dataclass
import re


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_SENTENCE_END_RE = re.compile(r"[。！？!?]")
_SENTENCE_SPLIT_RE = re.compile(r"[。！？!?；;\n]+")

# Conservative phrase-level corrections avoid pretending to provide a full
# dictionary or language-model spell checker.
_COMMON_TYPO_CORRECTIONS = {
    "因该": "应该",
    "以经": "已经",
    "做为": "作为",
    "在见": "再见",
    "再这里": "在这里",
    "再那里": "在那里",
    "即然": "既然",
    "既使": "即使",
    "按装": "安装",
    "记算": "计算",
    "题纲": "提纲",
    "必需认真": "必须认真",
}

_INSTRUCTION_PHRASES = (
    "请根据",
    "请结合",
    "请围绕",
    "写一篇",
    "作文",
    "文章",
    "题目",
    "要求",
    "不少于",
    "谈一谈",
    "谈谈",
    "说明",
)

_CONNECTORS = (
    "首先",
    "其次",
    "然后",
    "最后",
    "因为",
    "所以",
    "但是",
    "然而",
    "因此",
    "总之",
    "例如",
    "一方面",
    "另一方面",
)

_BALANCED_PUNCTUATION = {
    "（": "）",
    "(": ")",
    "“": "”",
    "《": "》",
}

_REPETITION_EXEMPT = set("哈哈呵啊嗯哦啦呀")


@dataclass(frozen=True)
class TypoFinding:
    original: str
    suggestion: str
    count: int


@dataclass(frozen=True)
class ChineseAnalysis:
    score_ratio: float
    typo_score: float
    fluency_score: float
    relevance_score: float
    structure_score: float
    typos: tuple[TypoFinding, ...]
    feedback: str


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _chinese_length(text: str) -> int:
    return len(_CJK_RE.findall(text))


def detect_typos(text: str) -> tuple[TypoFinding, ...]:
    """Return conservative typo findings that can be explained to a student."""
    findings: list[TypoFinding] = []

    for original, suggestion in _COMMON_TYPO_CORRECTIONS.items():
        count = text.count(original)
        if count:
            findings.append(TypoFinding(original, suggestion, count))

    repeated_counts: dict[str, int] = {}
    for match in re.finditer(r"([\u4e00-\u9fff])\1{2,}", text):
        char = match.group(1)
        if char in _REPETITION_EXEMPT:
            continue
        repeated_counts[match.group(0)] = repeated_counts.get(match.group(0), 0) + 1

    for repeated, count in sorted(repeated_counts.items()):
        findings.append(TypoFinding(repeated, repeated[0], count))

    return tuple(findings)


def _punctuation_issue_count(text: str) -> int:
    issues = 0
    for opening, closing in _BALANCED_PUNCTUATION.items():
        issues += abs(text.count(opening) - text.count(closing))
    issues += len(re.findall(r"[,，。！？!?；;]{3,}", text))
    return issues


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(text) if part.strip()]


def _score_fluency(text: str, typo_count: int) -> float:
    sentences = _sentences(text)
    if not sentences:
        return 0.0

    score = 1.0
    issue_count = _punctuation_issue_count(text)
    score -= min(0.30, issue_count * 0.10)
    score -= min(0.40, typo_count * 0.08)

    long_sentences = sum(_chinese_length(sentence) > 80 for sentence in sentences)
    score -= min(0.30, long_sentences * 0.15)

    average_length = sum(_chinese_length(sentence) for sentence in sentences) / len(sentences)
    if average_length < 5 or average_length > 60:
        score -= 0.15

    if _chinese_length(text) >= 20 and not _SENTENCE_END_RE.search(text):
        score -= 0.15

    return _clamp(score)


def _extract_reference_keywords(reference_text: str) -> set[str]:
    cleaned = reference_text
    for phrase in _INSTRUCTION_PHRASES:
        cleaned = cleaned.replace(phrase, " ")
    cleaned = re.sub(r"\d+\s*字", " ", cleaned)

    keywords: set[str] = set()
    for segment in re.findall(r"[\u4e00-\u9fff]{2,}", cleaned):
        if len(segment) <= 6:
            keywords.add(segment)
        for size in (2, 3, 4):
            if len(segment) >= size:
                keywords.update(segment[index:index + size] for index in range(len(segment) - size + 1))
    return keywords


def _student_ngrams(text: str) -> set[str]:
    ngrams: set[str] = set()
    for segment in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        for size in (2, 3, 4):
            if len(segment) >= size:
                ngrams.update(segment[index:index + size] for index in range(len(segment) - size + 1))
    return ngrams


def _score_relevance(text: str, reference_text: str) -> float:
    keywords = _extract_reference_keywords(reference_text)
    if not keywords:
        return 0.70

    student_terms = _student_ngrams(text)
    if not student_terms:
        return 0.0

    matched = sum(keyword in text or keyword in student_terms for keyword in keywords)
    coverage = matched / len(keywords)
    return _clamp(0.15 + coverage * 0.85)


def _score_structure(text: str) -> float:
    chinese_length = _chinese_length(text)
    if chinese_length == 0:
        return 0.0

    sentence_count = len(_sentences(text))
    paragraph_count = len([line for line in text.splitlines() if line.strip()])
    connector_count = sum(text.count(connector) for connector in _CONNECTORS)

    length_score = min(1.0, chinese_length / 120.0)
    sentence_score = min(1.0, sentence_count / 4.0)
    paragraph_score = min(1.0, max(paragraph_count, 1) / 3.0)
    connector_score = min(1.0, connector_count / 3.0)

    score = (
        length_score * 0.35
        + sentence_score * 0.30
        + paragraph_score * 0.20
        + connector_score * 0.15
    )
    return _clamp(score)


def _level(value: float) -> str:
    if value >= 0.80:
        return "较好"
    if value >= 0.55:
        return "一般"
    return "较弱"


def analyze_chinese_answer(student_text: str, reference_text: str = "") -> ChineseAnalysis:
    text = student_text.strip()
    if not text:
        return ChineseAnalysis(
            score_ratio=0.0,
            typo_score=0.0,
            fluency_score=0.0,
            relevance_score=0.0,
            structure_score=0.0,
            typos=(),
            feedback="未检测到可批改的语文作答内容。",
        )

    typos = detect_typos(text)
    typo_count = sum(item.count for item in typos)
    typo_score = _clamp(1.0 - min(0.60, typo_count * 0.12))
    fluency_score = _score_fluency(text, typo_count)
    relevance_score = _score_relevance(text, reference_text)
    structure_score = _score_structure(text)

    score_ratio = _clamp(
        typo_score * 0.15
        + fluency_score * 0.25
        + relevance_score * 0.35
        + structure_score * 0.25
    )

    feedback_parts = [
        f"内容相关度{_level(relevance_score)}",
        f"句子通顺度{_level(fluency_score)}",
        f"结构完整度{_level(structure_score)}",
    ]
    if typos:
        typo_text = "、".join(
            f"{item.original}→{item.suggestion}（{item.count}处）" for item in typos
        )
        feedback_parts.append(f"疑似错别字或重复字：{typo_text}")
    else:
        feedback_parts.append("未发现规则库可确认的常见错别字")

    return ChineseAnalysis(
        score_ratio=round(score_ratio, 4),
        typo_score=round(typo_score, 4),
        fluency_score=round(fluency_score, 4),
        relevance_score=round(relevance_score, 4),
        structure_score=round(structure_score, 4),
        typos=typos,
        feedback="；".join(feedback_parts) + "。",
    )


def grade_chinese_answer(
    student_text: str,
    reference_text: str,
    max_score: float,
) -> tuple[float, str]:
    if max_score <= 0:
        return 0.0, "满分值未设置。"

    analysis = analyze_chinese_answer(student_text, reference_text)
    score = round(max_score * analysis.score_ratio, 1)
    return min(max(score, 0.0), max_score), analysis.feedback
