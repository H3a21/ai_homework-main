"""Docker integration for batch API, Celery aggregation, and WebSocket progress."""

import asyncio
import json
import os
import sys
from uuid import uuid4

import httpx
from sqlalchemy import delete, select
import websockets

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.database import AsyncSession, engine
from app.models import (
    Assignment,
    Class,
    ClassMember,
    GradingAttempt,
    GradingBatch,
    GradingBatchItem,
    GradingResult,
    Question,
    Submission,
    SubmissionImage,
    Subject,
    User,
)


async def _login(client: httpx.AsyncClient, username: str, test_ip: str) -> str:
    response = await client.post(
        "/api/auth/login",
        json={"username": username, "password": "demo123"},
        headers={"X-Forwarded-For": test_ip},
    )
    response.raise_for_status()
    return response.json()["access_token"]


async def main() -> None:
    assignment_id = None
    question_id = None
    submission_ids: list[int] = []
    batch_id = None
    temporary_student_id = None

    try:
        async with AsyncSession() as db:
            classroom = (
                await db.execute(select(Class).where(Class.invite_code == "DEMO2026"))
            ).scalar_one()
            subject = (
                await db.execute(select(Subject).where(Subject.id == 1))
            ).scalar_one()
            teacher = (
                await db.execute(select(User).where(User.username == "math_teacher"))
            ).scalar_one()
            student = (
                await db.execute(select(User).where(User.username == "student_a"))
            ).scalar_one()

            suffix = uuid4().hex[:8]
            temporary_student = User(
                username=f"batch_student_{suffix}",
                password_hash="integration-test-not-login",
                display_name="批次测试学生",
                role="student",
            )
            db.add(temporary_student)
            await db.commit()
            await db.refresh(temporary_student)
            temporary_student_id = temporary_student.id
            db.add(
                ClassMember(
                    class_id=classroom.id,
                    user_id=temporary_student.id,
                    role="student",
                )
            )

            assignment = Assignment(
                title=f"Batch integration {suffix}",
                class_id=classroom.id,
                subject_id=subject.id,
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
            )
            db.add(question)
            await db.commit()
            await db.refresh(question)
            question_id = question.id

            for target_student in (student, temporary_student):
                submission = Submission(
                    assignment_id=assignment.id,
                    student_id=target_student.id,
                    status="pending",
                )
                db.add(submission)
                await db.commit()
                await db.refresh(submission)
                submission_ids.append(submission.id)
                db.add(
                    SubmissionImage(
                        submission_id=submission.id,
                        image_path=f"cached-batch-{submission.id}.png",
                        page_number=1,
                        recognized_text="4",
                    )
                )
            await db.commit()

        async with httpx.AsyncClient(
            base_url="http://backend:8000",
            timeout=30,
        ) as client:
            teacher_token = await _login(client, "math_teacher", "198.51.100.60")
            student_token = await _login(client, "student_a", "198.51.100.61")
            headers = {"Authorization": f"Bearer {teacher_token}"}

            response = await client.post(
                "/api/grading-batches",
                json={"assignment_id": assignment_id},
                headers=headers,
            )
            response.raise_for_status()
            created = response.json()
            batch_id = created["id"]
            if created["total_submissions"] != 2 or len(created["items"]) != 2:
                raise AssertionError(f"Unexpected batch response: {created}")
            if not all(item["task_id"] for item in created["items"]):
                raise AssertionError("Batch response is missing Celery task IDs")

            denied = await client.get(
                f"/api/grading-batches/{batch_id}",
                headers={"Authorization": f"Bearer {student_token}"},
            )
            if denied.status_code != 403:
                raise AssertionError("Student accessed teacher batch detail")

            events = []
            async with websockets.connect(
                f"ws://frontend/api/ws/batches/{batch_id}",
                origin="http://localhost:8080",
                open_timeout=10,
            ) as websocket:
                await websocket.send(
                    json.dumps({"type": "auth", "token": teacher_token})
                )
                while True:
                    message = json.loads(
                        await asyncio.wait_for(websocket.recv(), timeout=45)
                    )
                    if message.get("type") == "heartbeat":
                        continue
                    events.append(message)
                    if message.get("status") in ("completed", "failed"):
                        break

            detail = await client.get(
                f"/api/grading-batches/{batch_id}",
                headers=headers,
            )
            detail.raise_for_status()
            batch = detail.json()
            if batch["status"] != "completed":
                raise AssertionError(f"Batch did not complete: {batch}")
            if batch["completed_submissions"] != 2 or batch["failed_submissions"] != 0:
                raise AssertionError(f"Batch aggregate is incorrect: {batch}")
            if not all(item["status"] == "completed" for item in batch["items"]):
                raise AssertionError(f"Batch items did not complete: {batch['items']}")

            no_pending = await client.post(
                "/api/grading-batches",
                json={"assignment_id": assignment_id},
                headers=headers,
            )
            if no_pending.status_code != 409:
                raise AssertionError("Second batch should reject an assignment without pending work")

        async with AsyncSession() as db:
            completed_submissions = (
                await db.execute(
                    select(Submission).where(Submission.id.in_(submission_ids))
                )
            ).scalars().all()
            if any(item.status != "completed" for item in completed_submissions):
                raise AssertionError("Batch left a submission incomplete")
            attempts = (
                await db.execute(
                    select(GradingAttempt).where(
                        GradingAttempt.submission_id.in_(submission_ids)
                    )
                )
            ).scalars().all()
            if len(attempts) != 2 or any(item.status != "completed" for item in attempts):
                raise AssertionError("Batch grading attempts were not persisted")

        event_types = [event.get("type") for event in events]
        print(
            "PASS "
            f"batch_id={batch_id} submissions=2 completed=2 "
            f"events={event_types} permissions=403"
        )
    finally:
        async with AsyncSession() as db:
            if batch_id is not None:
                await db.execute(
                    delete(GradingBatchItem).where(
                        GradingBatchItem.batch_id == batch_id
                    )
                )
                await db.execute(
                    delete(GradingBatch).where(GradingBatch.id == batch_id)
                )
            if submission_ids:
                await db.execute(
                    delete(GradingResult).where(
                        GradingResult.submission_id.in_(submission_ids)
                    )
                )
                await db.execute(
                    delete(SubmissionImage).where(
                        SubmissionImage.submission_id.in_(submission_ids)
                    )
                )
                await db.execute(
                    delete(Submission).where(Submission.id.in_(submission_ids))
                )
            if question_id is not None:
                await db.execute(delete(Question).where(Question.id == question_id))
            if assignment_id is not None:
                await db.execute(
                    delete(Assignment).where(Assignment.id == assignment_id)
                )
            if temporary_student_id is not None:
                await db.execute(
                    delete(ClassMember).where(
                        ClassMember.user_id == temporary_student_id
                    )
                )
                await db.execute(
                    delete(User).where(User.id == temporary_student_id)
                )
            await db.commit()
        await engine.dispose()
        print("CLEANUP complete")


if __name__ == "__main__":
    asyncio.run(main())
