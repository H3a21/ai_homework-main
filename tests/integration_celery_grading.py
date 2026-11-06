"""Docker integration check for RabbitMQ -> Celery -> grading -> MySQL."""

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
                Assignment.title == "CODEX_ASYNC_TEST"
            )
        )
        user_count = await db.scalar(
            select(func.count()).select_from(User).where(
                User.username.like("codex_%")
            )
        )
        if assignment_count or user_count:
            raise AssertionError(
                "Integration cleanup left temporary assignments or users"
            )


async def main() -> None:
    assignment_id = None
    submission_id = None
    class_id = None
    user_ids: list[int] = []
    created_subject_id = None
    subject_name = os.getenv("GRADING_TEST_SUBJECT", "语文")
    if subject_name == "英语":
        question_content = "Write about protecting the environment at school"
        question_answer = None
        recognized_text = (
            "Protecting the environment at school is important. Firstly, students "
            "can save water. Moreover, we can recycle paper and keep classrooms clean."
        )
        expected_feedback = "Content relevance:"
        expected_comment = "英语作业"
    elif subject_name == "数学":
        question_content = "2 + 2"
        question_answer = "4"
        recognized_text = "4"
        expected_feedback = "答案完全正确"
        expected_comment = "数学作业"
    else:
        question_content = "春天的校园"
        question_answer = None
        recognized_text = (
            "春天的校园很美。首先花开了，然后同学们读书，"
            "最后我们一起锻炼。"
        )
        expected_feedback = "内容相关度"
        expected_comment = "语文作业"

    try:
        async with AsyncSession() as db:
            suffix = uuid4().hex[:10]
            subject = (
                await db.execute(select(Subject).where(Subject.name == subject_name))
            ).scalar_one_or_none()
            if not subject:
                subject = Subject(name=subject_name, description="integration test")
                db.add(subject)
                await db.commit()
                await db.refresh(subject)
                created_subject_id = subject.id

            teacher = User(
                username=f"codex_teacher_{suffix}",
                password_hash="integration-test-not-login",
                display_name="CODEX测试教师",
                role="teacher",
            )
            student = User(
                username=f"codex_student_{suffix}",
                password_hash="integration-test-not-login",
                display_name="CODEX测试学生",
                role="student",
            )
            db.add_all([teacher, student])
            await db.commit()
            await db.refresh(teacher)
            await db.refresh(student)
            user_ids = [teacher.id, student.id]

            classroom = Class(
                name="CODEX异步测试班",
                grade="integration-test",
                invite_code=f"CX{suffix}",
            )
            db.add(classroom)
            await db.commit()
            await db.refresh(classroom)
            class_id = classroom.id

            assignment = Assignment(
                title="CODEX_ASYNC_TEST",
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
                content=question_content,
                answer=question_answer,
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
                image_path="/tmp/codex-async-test.jpg",
                page_number=1,
                recognized_text=recognized_text,
            ))
            await db.commit()

            task_id = enqueue_grade_submission(submission.id)
            print(f"ENQUEUED task_id={task_id} submission_id={submission.id}")

        for _ in range(30):
            await asyncio.sleep(0.5)
            async with AsyncSession() as db:
                current = (
                    await db.execute(
                        select(Submission).where(Submission.id == submission_id)
                    )
                ).scalar_one()
                if current.status == "completed":
                    results = (
                        await db.execute(
                            select(GradingResult).where(
                                GradingResult.submission_id == submission_id
                            )
                        )
                    ).scalars().all()
                    if len(results) != 1:
                        raise AssertionError(
                            f"Expected 1 grading result, found {len(results)}"
                        )
                    if expected_feedback not in (results[0].feedback or ""):
                        raise AssertionError(
                            f"Submission did not use the {subject_name} pipeline"
                        )
                    if expected_comment not in (current.comment or ""):
                        raise AssertionError(
                            f"Fallback comment was not generated: {current.comment!r}"
                        )
                    print(
                        "PASS "
                        f"status={current.status} "
                        f"score={float(current.total_score)} "
                        f"grading_results={len(results)} "
                        f"comment={current.comment!r}"
                    )
                    return

        raise TimeoutError("Celery grading did not complete within 15 seconds")
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
