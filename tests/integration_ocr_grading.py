"""Docker integration check for image -> OCR -> Celery grading -> MySQL."""

import asyncio
import os
import sys
from uuid import uuid4

from sqlalchemy import delete, func, select

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.database import AsyncSession, engine
from app.models import (
    Assignment,
    Class,
    GradingResult,
    Question,
    Subject,
    Submission,
    SubmissionImage,
    User,
)
from app.worker import enqueue_grade_submission


TEST_IMAGE_PATH = os.getenv(
    "OCR_TEST_IMAGE_PATH", "/tmp/ai_homework_ocr_integration.png"
)


async def _cleanup(
    submission_id: int | None,
    assignment_id: int | None,
    class_id: int | None,
    user_ids: list[int],
    subject_id: int | None,
) -> None:
    async with AsyncSession() as db:
        if submission_id:
            await db.execute(
                delete(GradingResult).where(
                    GradingResult.submission_id == submission_id
                )
            )
            await db.execute(
                delete(SubmissionImage).where(
                    SubmissionImage.submission_id == submission_id
                )
            )
            await db.execute(delete(Submission).where(Submission.id == submission_id))
        if assignment_id:
            await db.execute(
                delete(Question).where(Question.assignment_id == assignment_id)
            )
            await db.execute(delete(Assignment).where(Assignment.id == assignment_id))
        if class_id:
            await db.execute(delete(Class).where(Class.id == class_id))
        if user_ids:
            await db.execute(delete(User).where(User.id.in_(user_ids)))
        if subject_id:
            await db.execute(delete(Subject).where(Subject.id == subject_id))
        await db.commit()

        assignment_count = await db.scalar(
            select(func.count()).select_from(Assignment).where(
                Assignment.title == "CODEX_OCR_TEST"
            )
        )
        user_count = await db.scalar(
            select(func.count()).select_from(User).where(
                User.username.like("codex_ocr_%")
            )
        )
        if assignment_count or user_count:
            raise AssertionError("OCR integration cleanup left temporary records")


async def main() -> None:
    assignment_id = None
    submission_id = None
    class_id = None
    user_ids: list[int] = []
    created_subject_id = None

    try:
        async with AsyncSession() as db:
            suffix = uuid4().hex[:10]
            subject = (
                await db.execute(select(Subject).where(Subject.name == "语文"))
            ).scalar_one_or_none()
            if not subject:
                subject = Subject(name="语文", description="integration test")
                db.add(subject)
                await db.commit()
                await db.refresh(subject)
                created_subject_id = subject.id

            teacher = User(
                username=f"codex_ocr_teacher_{suffix}",
                password_hash="integration-test-not-login",
                display_name="CODEX OCR测试教师",
                role="teacher",
            )
            student = User(
                username=f"codex_ocr_student_{suffix}",
                password_hash="integration-test-not-login",
                display_name="CODEX OCR测试学生",
                role="student",
            )
            db.add_all([teacher, student])
            await db.commit()
            await db.refresh(teacher)
            await db.refresh(student)
            user_ids = [teacher.id, student.id]

            classroom = Class(
                name="CODEX OCR测试班",
                grade="integration-test",
                invite_code=f"OC{suffix}",
            )
            db.add(classroom)
            await db.commit()
            await db.refresh(classroom)
            class_id = classroom.id

            assignment = Assignment(
                title="CODEX_OCR_TEST",
                class_id=classroom.id,
                subject_id=subject.id,
                teacher_id=teacher.id,
            )
            db.add(assignment)
            await db.commit()
            await db.refresh(assignment)
            assignment_id = assignment.id

            db.add(Question(
                assignment_id=assignment.id,
                question_number=1,
                content="春天的校园",
                max_score=20,
            ))
            submission = Submission(
                assignment_id=assignment.id,
                student_id=student.id,
                status="grading",
            )
            db.add(submission)
            await db.commit()
            await db.refresh(submission)
            submission_id = submission.id

            db.add(SubmissionImage(
                submission_id=submission.id,
                image_path=TEST_IMAGE_PATH,
                page_number=1,
            ))
            await db.commit()

            task_id = enqueue_grade_submission(submission.id)
            print(f"ENQUEUED task_id={task_id} submission_id={submission.id}")

        for _ in range(60):
            await asyncio.sleep(0.5)
            async with AsyncSession() as db:
                current = (
                    await db.execute(
                        select(Submission).where(Submission.id == submission_id)
                    )
                ).scalar_one()
                if current.status != "completed":
                    continue

                image = (
                    await db.execute(
                        select(SubmissionImage).where(
                            SubmissionImage.submission_id == submission_id
                        )
                    )
                ).scalar_one()
                results = (
                    await db.execute(
                        select(GradingResult).where(
                            GradingResult.submission_id == submission_id
                        )
                    )
                ).scalars().all()

                if "春天的校园" not in (image.recognized_text or ""):
                    raise AssertionError(
                        f"OCR text was not persisted: {image.recognized_text!r}"
                    )
                if len(results) != 1 or "内容相关度" not in (results[0].feedback or ""):
                    raise AssertionError("Chinese grading result was not generated")

                print(
                    "PASS "
                    f"status={current.status} "
                    f"score={float(current.total_score)} "
                    f"recognized_text={image.recognized_text!r}"
                )
                return

        raise TimeoutError("OCR grading did not complete within 30 seconds")
    finally:
        await _cleanup(
            submission_id,
            assignment_id,
            class_id,
            user_ids,
            created_subject_id,
        )
        await engine.dispose()
        print("CLEANUP complete")


if __name__ == "__main__":
    asyncio.run(main())
