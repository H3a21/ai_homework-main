"""Docker integration test for learning reports, caching, and invalidation."""

import asyncio
import os
import sys
from uuid import uuid4

import httpx
from sqlalchemy import delete, func, select

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.auth import _hash_password
from app.database import AsyncSession, engine
from app.models import (
    Assignment,
    Class,
    ClassMember,
    GradingResult,
    KnowledgePoint,
    Question,
    StudentKnowledgeMastery,
    Submission,
    SubmissionImage,
    User,
)
from app.report_cache import invalidate_report_cache
from app.worker import enqueue_grade_submission


async def _login(client: httpx.AsyncClient, username: str) -> str:
    test_ip = "198.51.100.10" if "teacher" in username else "198.51.100.11"
    response = await client.post(
        "/api/auth/login",
        json={"username": username, "password": "demo123"},
        headers={"X-Forwarded-For": test_ip},
    )
    response.raise_for_status()
    return response.json()["access_token"]


async def main() -> None:
    suffix = uuid4().hex[:10]
    class_id = None
    student_id = None
    temp_student_id = None
    assignment_id = None
    submission_id = None
    knowledge_point_ids: list[int] = []

    try:
        async with AsyncSession() as db:
            classroom = (
                await db.execute(select(Class).where(Class.invite_code == "DEMO2026"))
            ).scalar_one()
            teacher = (
                await db.execute(select(User).where(User.username == "math_teacher"))
            ).scalar_one()
            student = (
                await db.execute(select(User).where(User.username == "student_a"))
            ).scalar_one()
            class_id = classroom.id
            student_id = student.id

            temp_student = User(
                username=f"codex_report_student_{suffix}",
                password_hash=_hash_password("demo123"),
                display_name=f"报告测试学生-{suffix}",
                role="student",
            )
            db.add(temp_student)
            await db.commit()
            await db.refresh(temp_student)
            temp_student_id = temp_student.id
            db.add(ClassMember(
                class_id=classroom.id,
                user_id=temp_student.id,
                role="student",
            ))

            strong_point = KnowledgePoint(
                subject_id=1,
                name=f"CODEX报告强项-{suffix}",
            )
            weak_point = KnowledgePoint(
                subject_id=1,
                name=f"CODEX报告弱项-{suffix}",
            )
            db.add_all([strong_point, weak_point])
            await db.commit()
            await db.refresh(strong_point)
            await db.refresh(weak_point)
            knowledge_point_ids = [strong_point.id, weak_point.id]

            db.add_all([
                StudentKnowledgeMastery(
                    student_id=student.id,
                    knowledge_point_id=strong_point.id,
                    mastery_level=0.90,
                    ability_theta=1.20,
                    attempt_count=3,
                    success_sum=2.70,
                ),
                StudentKnowledgeMastery(
                    student_id=student.id,
                    knowledge_point_id=weak_point.id,
                    mastery_level=0.40,
                    ability_theta=-0.50,
                    attempt_count=2,
                    success_sum=0.80,
                ),
                StudentKnowledgeMastery(
                    student_id=temp_student.id,
                    knowledge_point_id=strong_point.id,
                    mastery_level=0.50,
                    ability_theta=0.00,
                    attempt_count=1,
                    success_sum=0.50,
                ),
            ])
            await db.commit()

        await invalidate_report_cache(student_id, class_id)
        await invalidate_report_cache(temp_student_id, class_id)

        async with httpx.AsyncClient(base_url="http://backend:8000", timeout=20.0) as client:
            teacher_token = await _login(client, "math_teacher")
            student_token = await _login(client, "student_a")
            teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
            student_headers = {"Authorization": f"Bearer {student_token}"}

            student_url = f"/api/reports/students/{student_id}?subject_id=1"
            first_student = await client.get(student_url, headers=teacher_headers)
            first_student.raise_for_status()
            student_report = first_student.json()
            assert student_report["cache"]["hit"] is False
            assert student_report["overview"]["knowledge_point_count"] == 2
            assert student_report["overview"]["weak_point_count"] == 1
            assert len(student_report["radar"]) == 2

            second_student = await client.get(student_url, headers=teacher_headers)
            second_student.raise_for_status()
            assert second_student.json()["cache"]["hit"] is True

            class_url = f"/api/reports/classes/{class_id}?subject_id=1"
            first_class = await client.get(class_url, headers=teacher_headers)
            first_class.raise_for_status()
            class_report = first_class.json()
            assert class_report["cache"]["hit"] is False
            assert class_report["overview"]["student_count"] >= 2
            point = next(
                item for item in class_report["knowledge_points"]
                if item["knowledge_point_id"] == knowledge_point_ids[0]
            )
            assert point["average_mastery"] == 0.7
            assert point["weak_student_count"] == 1

            second_class = await client.get(class_url, headers=teacher_headers)
            second_class.raise_for_status()
            assert second_class.json()["cache"]["hit"] is True

            own_report = await client.get(student_url, headers=student_headers)
            assert own_report.status_code == 200
            forbidden = await client.get(
                f"/api/reports/students/{temp_student_id}",
                headers=student_headers,
            )
            assert forbidden.status_code == 403

        async with AsyncSession() as db:
            assignment = Assignment(
                title=f"CODEX_REPORT_INVALIDATION-{suffix}",
                class_id=class_id,
                subject_id=1,
                teacher_id=teacher.id,
            )
            db.add(assignment)
            await db.commit()
            await db.refresh(assignment)
            assignment_id = assignment.id
            question = Question(
                assignment_id=assignment.id,
                question_number=1,
                content="2 + 2",
                answer="4",
                max_score=10,
                knowledge_point_id=knowledge_point_ids[0],
            )
            submission = Submission(
                assignment_id=assignment.id,
                student_id=student_id,
                status="grading",
            )
            db.add_all([question, submission])
            await db.commit()
            await db.refresh(submission)
            submission_id = submission.id
            db.add(SubmissionImage(
                submission_id=submission.id,
                image_path="/tmp/codex-report-invalidation.jpg",
                page_number=1,
                recognized_text="4",
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
                    mastery = (
                        await db.execute(
                            select(StudentKnowledgeMastery).where(
                                StudentKnowledgeMastery.student_id == student_id,
                                StudentKnowledgeMastery.knowledge_point_id
                                == knowledge_point_ids[0],
                            )
                        )
                    ).scalar_one()
                    assert mastery.attempt_count == 4
                    break
        else:
            raise TimeoutError("Report invalidation grading did not complete")

        async with httpx.AsyncClient(base_url="http://backend:8000", timeout=20.0) as client:
            teacher_token = await _login(client, "math_teacher")
            headers = {"Authorization": f"Bearer {teacher_token}"}
            refreshed_student = await client.get(
                f"/api/reports/students/{student_id}?subject_id=1",
                headers=headers,
            )
            refreshed_student.raise_for_status()
            assert refreshed_student.json()["cache"]["hit"] is False
            refreshed_class = await client.get(
                f"/api/reports/classes/{class_id}?subject_id=1",
                headers=headers,
            )
            refreshed_class.raise_for_status()
            assert refreshed_class.json()["cache"]["hit"] is False

        print("PASS personal/class reports, Redis cache, permissions, and invalidation")
    finally:
        if student_id and class_id:
            await invalidate_report_cache(student_id, class_id)
        if temp_student_id and class_id:
            await invalidate_report_cache(temp_student_id, class_id)
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
                await db.execute(delete(Question).where(Question.assignment_id == assignment_id))
                await db.execute(delete(Assignment).where(Assignment.id == assignment_id))
            if knowledge_point_ids:
                await db.execute(
                    delete(StudentKnowledgeMastery).where(
                        StudentKnowledgeMastery.knowledge_point_id.in_(knowledge_point_ids)
                    )
                )
            if temp_student_id:
                await db.execute(
                    delete(ClassMember).where(ClassMember.user_id == temp_student_id)
                )
                await db.execute(delete(User).where(User.id == temp_student_id))
            if knowledge_point_ids:
                await db.execute(
                    delete(KnowledgePoint).where(
                        KnowledgePoint.id.in_(knowledge_point_ids)
                    )
                )
            await db.commit()

            remaining = await db.scalar(
                select(func.count()).select_from(User).where(
                    User.username == f"codex_report_student_{suffix}"
                )
            )
            if remaining:
                raise AssertionError("Learning report integration cleanup was incomplete")
        await engine.dispose()
        print("CLEANUP complete")


if __name__ == "__main__":
    asyncio.run(main())
