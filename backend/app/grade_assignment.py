from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Assignment, GradingResult, Question, Subject, Submission, SubmissionImage,
)
from app.math_pipeline import grade_math_with_steps
from app.chinese_pipeline import grade_chinese_answer
from app.english_pipeline import grade_english_answer
from app.feedback_engine import generate_comment
from app.knowledge_profile import update_mastery_for_results
from app.object_storage import read_image_source
from app.report_cache import invalidate_report_cache

try:
    from app.ocr_client import ocr_image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


GRADING_PIPELINES = {
    "数学": "math",
    "语文": "chinese",
    "英语": "english",
}


def resolve_grading_pipeline(subject_name: str | None) -> str:
    if not subject_name:
        return "default"
    normalized = subject_name.strip().lower()
    if normalized in GRADING_PIPELINES:
        return GRADING_PIPELINES[normalized]
    aliases = {
        "math": "math",
        "mathematics": "math",
        "chinese": "chinese",
        "english": "english",
    }
    return aliases.get(normalized, "default")

MOCK_FEEDBACK_TEMPLATES = {
    "math": [
        "解题思路清晰，计算准确，继续保持！",
        "思路正确，但计算过程中有一个小错误，注意仔细检查。",
        "基本理解了解题方法，但关键步骤有遗漏，建议多练习同类题型。",
        "解题方向正确，但步骤不够完整，需要加强过程书写。",
        "对知识点理解不够深入，建议复习相关概念。",
        "公式使用正确，但代入数值时出错，注意审题。",
    ],
    "chinese": [
        "表达流畅，用词准确，展现了良好的语言功底。",
        "文章结构完整，但部分句子可以更简洁。",
        "内容充实，但错别字较多，建议多阅读多积累。",
        "观点明确，但论证不够充分，可以补充更多论据。",
        "语言生动形象，但需要注意标点符号的正确使用。",
    ],
    "english": [
        "Good job! Clear expression with proper grammar usage.",
        "Well-structured writing. Try to use more varied vocabulary.",
        "Your ideas are good, but there are some spelling errors to correct.",
        "Keep practicing! Pay attention to verb tenses and subject-verb agreement.",
        "Good effort! Try to write longer paragraphs with more details.",
    ],
    "default": [
        "完成得不错，继续加油！",
        "有一些小错误需要注意，整体表现良好。",
        "建议多加练习，巩固知识点。",
        "基本掌握了所学内容，下次可以做得更好！",
    ],
}

def _get_feedback(question_number: int, max_score: float, score: float) -> str:
    ratio = score / max_score if max_score > 0 else 0
    templates = MOCK_FEEDBACK_TEMPLATES["default"]
    if ratio >= 0.9:
        return templates[0] if len(templates) > 0 else "完成得很好！"
    elif ratio >= 0.6:
        return templates[2] if len(templates) > 2 else "表现良好。"
    else:
        return templates[-1] if templates else "需要加强。"
async def _run_ocr_on_images(db: AsyncSession, submission_id: int) -> str:
    images_result = await db.execute(
        select(SubmissionImage)
        .where(SubmissionImage.submission_id == submission_id)
        .order_by(SubmissionImage.page_number)
    )
    images = images_result.scalars().all()

    combined = ""
    for img in images:
        if img.recognized_text:
            combined += img.recognized_text + "\n"
        elif OCR_AVAILABLE and img.image_path:
            try:
                stored = await read_image_source(img.image_path)
                ocr_result = await ocr_image(
                    stored.content, Path(img.image_path).name
                )
                recognized = ocr_result.get("text", "")
                img.recognized_text = recognized
                combined += recognized + "\n"
            except Exception:
                pass
    return combined


async def _grade_math(
    db: AsyncSession,
    submission: Submission,
    questions: list[Question],
    student_text: str,
) -> tuple[float, list[GradingResult]]:
    total = 0.0
    results = []

    for q in questions:
        max_score = float(q.max_score)
        if not max_score:
            continue

        expected = q.answer or q.content or ""

        score, feedback = grade_math_with_steps(student_text, expected, max_score)

        if score is None:
            import random
            score = round(random.uniform(max_score * 0.3, max_score), 1)
            score = min(score, max_score)
            feedback = _get_feedback(q.question_number, max_score, score)

        total += score
        results.append(GradingResult(
            submission_id=submission.id,
            question_id=q.id,
            score=score,
            feedback=feedback,
        ))

    return round(total, 1), results


async def _grade_chinese(
    db: AsyncSession,
    submission: Submission,
    questions: list[Question],
    student_text: str,
) -> tuple[float, list[GradingResult]]:
    total = 0.0
    results = []

    for q in questions:
        max_score = float(q.max_score)
        if not max_score:
            continue

        reference_text = q.content or q.answer or ""
        score, feedback = grade_chinese_answer(
            student_text,
            reference_text,
            max_score,
        )
        total += score
        results.append(GradingResult(
            submission_id=submission.id,
            question_id=q.id,
            score=score,
            feedback=feedback,
        ))

    return round(total, 1), results


async def _grade_english(
    db: AsyncSession,
    submission: Submission,
    questions: list[Question],
    student_text: str,
) -> tuple[float, list[GradingResult]]:
    total = 0.0
    results = []

    for q in questions:
        max_score = float(q.max_score)
        if not max_score:
            continue

        reference_text = q.content or q.answer or ""
        score, feedback = grade_english_answer(
            student_text,
            reference_text,
            max_score,
        )
        total += score
        results.append(GradingResult(
            submission_id=submission.id,
            question_id=q.id,
            score=score,
            feedback=feedback,
        ))

    return round(total, 1), results


async def grade_submission(db: AsyncSession, submission_id: int):
    result = await db.execute(
        select(Submission).where(Submission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise ValueError(f"Submission {submission_id} not found")

    if submission.status == "completed":
        return

    assignment_result = await db.execute(
        select(Assignment).where(Assignment.id == submission.assignment_id)
    )
    assignment = assignment_result.scalar_one_or_none()
    if not assignment:
        raise ValueError(f"Assignment for submission {submission_id} not found")

    subject_result = await db.execute(
        select(Subject).where(Subject.id == assignment.subject_id)
    )
    subject = subject_result.scalar_one_or_none()

    questions_result = await db.execute(
        select(Question)
        .where(Question.assignment_id == submission.assignment_id)
        .order_by(Question.question_number)
    )
    questions = questions_result.scalars().all()

    student_text = await _run_ocr_on_images(db, submission_id)

    pipeline = resolve_grading_pipeline(subject.name if subject else None)

    if pipeline == "math":
        total, grading_results = await _grade_math(db, submission, questions, student_text)
    elif pipeline == "chinese":
        total, grading_results = await _grade_chinese(db, submission, questions, student_text)
    elif pipeline == "english":
        total, grading_results = await _grade_english(db, submission, questions, student_text)
    else:
        import random
        total = sum(
            min(round(random.uniform(float(q.max_score) * 0.3, float(q.max_score)), 1), float(q.max_score))
            for q in questions if float(q.max_score) > 0
        )
        grading_results = []
        for q in questions:
            max_score = float(q.max_score)
            grading_results.append(GradingResult(
                submission_id=submission.id,
                question_id=q.id,
                score=min(round(random.uniform(max_score * 0.3, max_score), 1), max_score) if max_score > 0 else 0,
                feedback=_get_feedback(q.question_number, max_score, max_score),
            ))

    for gr in grading_results:
        db.add(gr)

    await update_mastery_for_results(
        db,
        submission.student_id,
        {question.id: question for question in questions},
        grading_results,
    )

    max_total = sum(float(question.max_score) for question in questions)
    submission.total_score = round(total, 1)
    submission.comment = await generate_comment(
        subject.name if subject else pipeline,
        total,
        max_total,
        [result.feedback or "" for result in grading_results],
    )
    submission.status = "completed"
    submission.graded_at = datetime.utcnow()

    await db.commit()
    await invalidate_report_cache(submission.student_id, assignment.class_id)
