"""Docker integration test for knowledge graph, IRT updates, and API permissions."""

import asyncio
import os
import sys
from uuid import uuid4

import httpx
from sqlalchemy import delete, func, select

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.database import AsyncSession, engine
from app.models import (
    Assignment,
    Class,
    GradingResult,
    KnowledgePoint,
    KnowledgeRelation,
    Question,
    StudentKnowledgeMastery,
    Submission,
    SubmissionImage,
    Subject,
    User,
)
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
    assignment_id = None
    submission_id = None
    root_id = None
    child_id = None
    student_id = None
    subject_id = None
    observed_ratio = None

    try:
        async with AsyncSession() as db:
            subject = (
                await db.execute(select(Subject).where(Subject.id == 1))
            ).scalar_one()
            teacher = (
                await db.execute(select(User).where(User.username == "math_teacher"))
            ).scalar_one()
            student = (
                await db.execute(select(User).where(User.username == "student_a"))
            ).scalar_one()
            subject_id = subject.id
            student_id = student.id

            root = KnowledgePoint(
                subject_id=subject.id,
                name=f"CODEX根知识点-{suffix}",
            )
            db.add(root)
            await db.commit()
            await db.refresh(root)
            root_id = root.id

        async with httpx.AsyncClient(base_url="http://backend:8000", timeout=20.0) as client:
            teacher_token = await _login(client, "math_teacher")
            teacher_headers = {"Authorization": f"Bearer {teacher_token}"}

            point_response = await client.post(
                "/api/knowledge/points",
                headers=teacher_headers,
                json={
                    "subject_id": subject_id,
                    "name": f"CODEX目标知识点-{suffix}",
                    "parent_id": root_id,
                },
            )
            point_response.raise_for_status()
            child_id = point_response.json()["id"]

            relation_response = await client.post(
                "/api/knowledge/relations",
                headers=teacher_headers,
                json={
                    "prerequisite_id": root_id,
                    "target_id": child_id,
                    "strength": 0.8,
                },
            )
            relation_response.raise_for_status()

        async with AsyncSession() as db:
            classroom_id = (
                await db.execute(
                    select(Class.id).where(Class.invite_code == "DEMO2026")
                )
            ).scalar_one()
            assignment = Assignment(
                title=f"CODEX_PROFILE_TEST-{suffix}",
                class_id=classroom_id,
                subject_id=subject_id,
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
                knowledge_point_id=child_id,
                difficulty=0.0,
                discrimination=1.0,
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
                image_path="/tmp/codex-profile-test.jpg",
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
                                StudentKnowledgeMastery.knowledge_point_id == child_id,
                            )
                        )
                    ).scalar_one()
                    assert mastery.attempt_count == 1
                    observed_ratio = float(mastery.success_sum)
                    assert 0.0 < observed_ratio <= 1.0
                    assert float(mastery.ability_theta) > 0.0
                    break
        else:
            raise TimeoutError("Profile grading did not complete within 15 seconds")

        async with httpx.AsyncClient(base_url="http://backend:8000", timeout=20.0) as client:
            teacher_token = await _login(client, "math_teacher")
            student_token = await _login(client, "student_a")
            teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
            student_headers = {"Authorization": f"Bearer {student_token}"}

            graph = await client.get(
                f"/api/knowledge/graph?subject_id={subject_id}",
                headers=teacher_headers,
            )
            graph.raise_for_status()
            graph_data = graph.json()
            assert {root_id, child_id}.issubset(
                {point["id"] for point in graph_data["points"]}
            )
            assert any(
                relation["prerequisite_id"] == root_id
                and relation["target_id"] == child_id
                for relation in graph_data["relations"]
            )

            mastery_response = await client.get(
                f"/api/knowledge/mastery/{student_id}?subject_id={subject_id}",
                headers=teacher_headers,
            )
            mastery_response.raise_for_status()
            items = mastery_response.json()["items"]
            item = next(item for item in items if item["knowledge_point_id"] == child_id)
            assert item["attempt_count"] == 1
            assert item["average_score_ratio"] == observed_ratio
            assert item["is_weak"] == (item["mastery_level"] < 0.6)

            own_profile = await client.get(
                f"/api/knowledge/mastery/{student_id}",
                headers=student_headers,
            )
            assert own_profile.status_code == 200
            forbidden = await client.get(
                f"/api/knowledge/mastery/{teacher.id}",
                headers=student_headers,
            )
            assert forbidden.status_code == 403

        print("PASS knowledge graph, IRT update, and profile permissions")
    finally:
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
            if student_id and child_id:
                await db.execute(
                    delete(StudentKnowledgeMastery).where(
                        StudentKnowledgeMastery.student_id == student_id,
                        StudentKnowledgeMastery.knowledge_point_id == child_id,
                    )
                )
            if root_id and child_id:
                await db.execute(
                    delete(KnowledgeRelation).where(
                        KnowledgeRelation.prerequisite_id == root_id,
                        KnowledgeRelation.target_id == child_id,
                    )
                )
            if child_id:
                await db.execute(
                    delete(KnowledgePoint).where(KnowledgePoint.id == child_id)
                )
            if root_id:
                await db.execute(
                    delete(KnowledgePoint).where(KnowledgePoint.id == root_id)
                )
            await db.commit()
            remaining_points = await db.scalar(
                select(func.count()).select_from(KnowledgePoint).where(
                    KnowledgePoint.name.like(f"%{suffix}")
                )
            )
            remaining_assignments = await db.scalar(
                select(func.count()).select_from(Assignment).where(
                    Assignment.title == f"CODEX_PROFILE_TEST-{suffix}"
                )
            )
            if remaining_points or remaining_assignments:
                raise AssertionError("Knowledge profile integration cleanup was incomplete")
        await engine.dispose()
        print("CLEANUP complete")


if __name__ == "__main__":
    asyncio.run(main())
