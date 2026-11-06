import random
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Assignment, GradingResult, Question, Submission, SubmissionImage,
)
from app.object_storage import read_image_source

try:
    from app.ocr_client import ocr_image
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

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

MOCK_COMMENTS = [
    "整体表现良好，基础知识掌握扎实，建议在应用题方面多加练习。",
    "作业完成认真，书写工整。部分题目需要仔细审题，减少粗心错误。",
    "对课堂知识的理解较好，但在综合运用方面还有提升空间。",
    "继续保持良好的学习态度！建议针对错题进行针对性复习。",
    "作业完成度较高，体现了认真的学习态度。部分知识点需要巩固。",
]


def _get_feedback(question_number: int, max_score: float, score: float) -> str:
    ratio = score / max_score if max_score > 0 else 0
    templates = MOCK_FEEDBACK_TEMPLATES["default"]
    if ratio >= 0.9:
        return random.choice(templates[:2])
    elif ratio >= 0.6:
        return random.choice(templates[2:4])
    else:
        return random.choice(templates[2:])


def _pick_comment() -> str:
    return random.choice(MOCK_COMMENTS)


def _simple_text_match(student_text: str, expected_text: str) -> float:
    st = student_text.replace(" ", "").replace("\n", "")
    et = expected_text.replace(" ", "").replace("\n", "")
    if not et:
        return 0.5
    common = sum(1 for c in st if c in et)
    return common / max(len(et), 1)


async def mock_grade(db: AsyncSession, submission_id: int):
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
        raise ValueError(f"Assignment {submission.assignment_id} not found")

    questions_result = await db.execute(
        select(Question)
        .where(Question.assignment_id == submission.assignment_id)
        .order_by(Question.question_number)
    )
    questions = questions_result.scalars().all()

    images_result = await db.execute(
        select(SubmissionImage)
        .where(SubmissionImage.submission_id == submission_id)
        .order_by(SubmissionImage.page_number)
    )
    images = images_result.scalars().all()

    combined_ocr_text = ""
    for img in images:
        if img.recognized_text:
            combined_ocr_text += img.recognized_text + "\n"
        elif OCR_AVAILABLE and img.image_path:
            try:
                stored = await read_image_source(img.image_path)
                ocr_result = await ocr_image(
                    stored.content, Path(img.image_path).name
                )
                recognized = ocr_result.get("text", "")
                img.recognized_text = recognized
                combined_ocr_text += recognized + "\n"
            except Exception:
                pass

    total = 0.0
    for q in questions:
        max_score = float(q.max_score)
        if max_score <= 0:
            score = 0.0
        elif combined_ocr_text:
            match = _simple_text_match(combined_ocr_text, q.content or "")
            score = round(max_score * (0.3 + 0.7 * match), 1)
            score = min(score, max_score)
        else:
            score = round(random.uniform(max_score * 0.3, max_score), 1)
            score = min(score, max_score)

        feedback = _get_feedback(q.question_number, max_score, score)
        total += score

        grading = GradingResult(
            submission_id=submission.id,
            question_id=q.id,
            score=score,
            feedback=feedback,
        )
        db.add(grading)

    submission.total_score = round(total, 1)
    submission.comment = _pick_comment()
    submission.status = "completed"
    submission.graded_at = datetime.utcnow()

    await db.commit()
