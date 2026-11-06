"""Deterministic, explainable grading helpers for English writing."""

from __future__ import annotations

from dataclasses import dataclass
import re


_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?]?", re.MULTILINE)

_COMMON_MISSPELLINGS = {
    "acheive": "achieve",
    "becuase": "because",
    "beleive": "believe",
    "begining": "beginning",
    "definately": "definitely",
    "enviroment": "environment",
    "freind": "friend",
    "goverment": "government",
    "happend": "happened",
    "langauge": "language",
    "occured": "occurred",
    "recieve": "receive",
    "seperate": "separate",
    "studing": "studying",
    "sucess": "success",
    "succesful": "successful",
    "tommorow": "tomorrow",
    "wich": "which",
    "writting": "writing",
}

_VERB_FORMS = {
    "do": "does",
    "go": "goes",
    "have": "has",
    "like": "likes",
    "live": "lives",
    "make": "makes",
    "need": "needs",
    "play": "plays",
    "study": "studies",
    "want": "wants",
    "watch": "watches",
    "work": "works",
}

_REFERENCE_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to",
    "was", "were", "will", "with", "write", "writing", "essay", "article",
    "please", "about", "your", "you", "words", "word", "describe", "explain",
}

_CONNECTORS = {
    "although", "because", "however", "moreover", "therefore", "firstly",
    "secondly", "finally", "instead", "meanwhile", "otherwise", "for example",
    "in addition", "as a result", "on the other hand",
}


@dataclass(frozen=True)
class SpellingFinding:
    original: str
    suggestion: str
    count: int


@dataclass(frozen=True)
class GrammarFinding:
    code: str
    message: str


@dataclass(frozen=True)
class EnglishAnalysis:
    score_ratio: float
    spelling_score: float
    grammar_score: float
    vocabulary_score: float
    relevance_score: float
    spelling_findings: tuple[SpellingFinding, ...]
    grammar_findings: tuple[GrammarFinding, ...]
    feedback: str


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _words(text: str) -> list[str]:
    return [word.lower() for word in _WORD_RE.findall(text)]


def detect_spelling_errors(text: str) -> tuple[SpellingFinding, ...]:
    counts: dict[str, int] = {}
    for word in _words(text):
        if word in _COMMON_MISSPELLINGS:
            counts[word] = counts.get(word, 0) + 1

    findings = [
        SpellingFinding(word, _COMMON_MISSPELLINGS[word], count)
        for word, count in sorted(counts.items())
    ]
    return tuple(findings)


def _sentence_parts(text: str) -> list[str]:
    return [match.group(0).strip() for match in _SENTENCE_RE.finditer(text) if match.group(0).strip()]


def detect_grammar_errors(text: str) -> tuple[GrammarFinding, ...]:
    findings: list[GrammarFinding] = []
    sentences = _sentence_parts(text)

    for index, sentence in enumerate(sentences, start=1):
        first_letter = re.search(r"[A-Za-z]", sentence)
        if first_letter and first_letter.group(0).islower():
            findings.append(GrammarFinding(
                "sentence-capitalization",
                f"Sentence {index} should start with a capital letter.",
            ))
        if sentence[-1:] not in ".!?":
            findings.append(GrammarFinding(
                "terminal-punctuation",
                f"Sentence {index} needs terminal punctuation.",
            ))

    lower_text = text.lower()
    agreement_patterns = (
        (r"\b(he|she|it)\s+(are)\b", "Use 'is' with he, she, or it."),
        (r"\b(they|we|you)\s+(is)\b", "Use 'are' with they, we, or you."),
        (r"\bi\s+is\b", "Use 'I am' instead of 'I is'."),
        (r"\b(i|you|we|they)\s+has\b", "Use 'have' with I, you, we, or they."),
    )
    for pattern, message in agreement_patterns:
        if re.search(pattern, lower_text):
            findings.append(GrammarFinding("subject-verb-agreement", message))

    for base, singular in _VERB_FORMS.items():
        if re.search(rf"\b(he|she|it)\s+{base}\b", lower_text):
            findings.append(GrammarFinding(
                "third-person-singular",
                f"Use '{singular}' after he, she, or it.",
            ))

    if re.search(r"\ba\s+[aeiou][a-z]*\b", lower_text):
        findings.append(GrammarFinding(
            "article-a-an",
            "Use 'an' before a word that begins with a vowel sound.",
        ))
    if re.search(r"\ban\s+[b-df-hj-np-tv-z][a-z]*\b", lower_text):
        findings.append(GrammarFinding(
            "article-a-an",
            "Use 'a' before a word that begins with a consonant sound.",
        ))
    if re.search(r"\s+[,.!?;:]", text):
        findings.append(GrammarFinding(
            "punctuation-spacing",
            "Remove the space before punctuation.",
        ))
    if re.search(r"([.!?])\1{2,}", text):
        findings.append(GrammarFinding(
            "repeated-punctuation",
            "Avoid repeating terminal punctuation.",
        ))

    unique: dict[tuple[str, str], GrammarFinding] = {}
    for finding in findings:
        unique[(finding.code, finding.message)] = finding
    return tuple(unique.values())


def _stem(word: str) -> str:
    if len(word) > 5 and word.endswith("ing"):
        return word[:-3]
    if len(word) > 4 and word.endswith("ed"):
        return word[:-2]
    if len(word) > 4 and word.endswith("es"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s"):
        return word[:-1]
    return word


def _score_relevance(text: str, reference_text: str) -> float:
    reference_words = {
        _stem(word) for word in _words(reference_text)
        if word not in _REFERENCE_STOP_WORDS and len(word) > 2
    }
    if not reference_words:
        return 0.70

    student_words = {_stem(word) for word in _words(text)}
    if not student_words:
        return 0.0

    coverage = len(reference_words & student_words) / len(reference_words)
    return _clamp(0.10 + coverage * 0.90)


def _score_vocabulary(text: str) -> float:
    words = _words(text)
    if not words:
        return 0.0

    unique_ratio = len(set(words)) / len(words)
    length_score = min(1.0, len(words) / 60.0)
    lowered = text.lower()
    connector_count = sum(connector in lowered for connector in _CONNECTORS)
    connector_score = min(1.0, connector_count / 3.0)

    long_word_ratio = sum(len(word) >= 7 for word in words) / len(words)
    complexity_score = min(1.0, long_word_ratio / 0.20)
    return _clamp(
        unique_ratio * 0.40
        + length_score * 0.30
        + connector_score * 0.15
        + complexity_score * 0.15
    )


def _level(value: float) -> str:
    if value >= 0.80:
        return "good"
    if value >= 0.55:
        return "developing"
    return "needs improvement"


def analyze_english_answer(student_text: str, reference_text: str = "") -> EnglishAnalysis:
    text = student_text.strip()
    if not text:
        return EnglishAnalysis(
            score_ratio=0.0,
            spelling_score=0.0,
            grammar_score=0.0,
            vocabulary_score=0.0,
            relevance_score=0.0,
            spelling_findings=(),
            grammar_findings=(),
            feedback="No English answer was detected.",
        )

    spelling_findings = detect_spelling_errors(text)
    spelling_count = sum(item.count for item in spelling_findings)
    grammar_findings = detect_grammar_errors(text)

    spelling_score = _clamp(1.0 - min(0.75, spelling_count * 0.15))
    grammar_score = _clamp(1.0 - min(0.80, len(grammar_findings) * 0.12))
    vocabulary_score = _score_vocabulary(text)
    relevance_score = _score_relevance(text, reference_text)
    score_ratio = _clamp(
        spelling_score * 0.20
        + grammar_score * 0.30
        + vocabulary_score * 0.20
        + relevance_score * 0.30
    )

    feedback_parts = [
        f"Spelling: {_level(spelling_score)}",
        f"Grammar: {_level(grammar_score)}",
        f"Vocabulary: {_level(vocabulary_score)}",
        f"Content relevance: {_level(relevance_score)}",
    ]
    if spelling_findings:
        corrections = ", ".join(
            f"{item.original}->{item.suggestion} ({item.count})"
            for item in spelling_findings
        )
        feedback_parts.append(f"Possible spelling errors: {corrections}")
    if grammar_findings:
        grammar_text = " ".join(item.message for item in grammar_findings[:4])
        feedback_parts.append(f"Grammar notes: {grammar_text}")
    if not spelling_findings and not grammar_findings:
        feedback_parts.append("No rule-based spelling or grammar errors were found")

    return EnglishAnalysis(
        score_ratio=round(score_ratio, 4),
        spelling_score=round(spelling_score, 4),
        grammar_score=round(grammar_score, 4),
        vocabulary_score=round(vocabulary_score, 4),
        relevance_score=round(relevance_score, 4),
        spelling_findings=spelling_findings,
        grammar_findings=grammar_findings,
        feedback="; ".join(feedback_parts) + ".",
    )


def grade_english_answer(
    student_text: str,
    reference_text: str,
    max_score: float,
) -> tuple[float, str]:
    if max_score <= 0:
        return 0.0, "Maximum score is not configured."

    analysis = analyze_english_answer(student_text, reference_text)
    score = round(max_score * analysis.score_ratio, 1)
    return min(max(score, 0.0), max_score), analysis.feedback
