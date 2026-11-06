"""Docker integration test for Celery-to-WebSocket grading events."""

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
    AuditLog,
    Class,
    GradingAttempt,
    GradingResult,
    Question,
    Submission,
    SubmissionImage,
    Subject,
    User,
)


async def _login(
    client: httpx.AsyncClient,
    username: str,
    test_ip: str,
) -> str:
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
    submission_id = None

    try:
        async with AsyncSession() as db:
            classroom = (
                await db.execute(select(Class).where(Class.invite_code == "DEMO2026"))
            ).scalar_one()
            subject = (await db.execute(select(Subject).order_by(Subject.id))).scalars().first()
            teacher = (
                await db.execute(select(User).where(User.username == "math_teacher"))
            ).scalar_one()
            student = (
                await db.execute(select(User).where(User.username == "student_a"))
            ).scalar_one()
            if subject is None:
                raise AssertionError("Seed subject is missing")

            assignment = Assignment(
                title=f"Realtime integration {uuid4().hex[:8]}",
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

            submission = Submission(
                assignment_id=assignment.id,
                student_id=student.id,
                status="pending",
            )
            db.add(submission)
            await db.commit()
            await db.refresh(submission)
            submission_id = submission.id
            db.add(
                SubmissionImage(
                    submission_id=submission.id,
                    image_path="cached-realtime.png",
                    page_number=1,
                    recognized_text="4",
                )
            )
            await db.commit()

        websocket_url = (
            f"ws://frontend/api/ws/submissions/{submission_id}"
        )
        events = []
        async with httpx.AsyncClient(
            base_url="http://backend:8000", timeout=30
        ) as client:
            student_token = await _login(
                client, "student_a", "198.51.100.40"
            )
            teacher_token = await _login(
                client, "math_teacher", "198.51.100.41"
            )
            async with websockets.connect(
                websocket_url,
                origin="http://localhost:8080",
                open_timeout=10,
            ) as websocket:
                await websocket.send(
                    json.dumps({"type": "auth", "token": student_token})
                )
                snapshot = json.loads(await asyncio.wait_for(websocket.recv(), 10))
                if snapshot.get("status") != "pending":
                    raise AssertionError(f"Unexpected snapshot: {snapshot}")

                trigger = await client.post(
                    f"/api/submissions/{submission_id}/grade",
                    headers={"Authorization": f"Bearer {teacher_token}"},
                )
                trigger.raise_for_status()
                task_id = trigger.json()["task_id"]
                while True:
                    message = json.loads(
                        await asyncio.wait_for(websocket.recv(), timeout=45)
                    )
                    if message.get("type") == "heartbeat":
                        continue
                    events.append(message)
                    if message.get("status") == "completed":
                        break

            teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
            attempts_response = await client.get(
                f"/api/history/submissions/{submission_id}/attempts",
                headers=teacher_headers,
            )
            attempts_response.raise_for_status()
            if attempts_response.json()[0]["status"] != "completed":
                raise AssertionError("Teacher history API missed completed attempt")

            audit_response = await client.get(
                f"/api/history/submissions/{submission_id}/audit",
                headers=teacher_headers,
            )
            audit_response.raise_for_status()
            if not any(
                record["action"] == "submission.grade"
                for record in audit_response.json()
            ):
                raise AssertionError("Teacher audit API missed grade action")

            student_denied = await client.get(
                f"/api/history/submissions/{submission_id}/attempts",
                headers={"Authorization": f"Bearer {student_token}"},
            )
            if student_denied.status_code != 403:
                raise AssertionError("Student accessed teacher grading history API")

        statuses = [event.get("status") for event in events]
        if "grading" not in statuses or "completed" not in statuses:
            raise AssertionError(f"Missing realtime statuses: {statuses}")

        async with AsyncSession() as db:
            completed = (
                await db.execute(
                    select(Submission).where(Submission.id == submission_id)
                )
            ).scalar_one()
            if completed.status != "completed":
                raise AssertionError("Celery grading did not complete")

            attempts = (
                await db.execute(
                    select(GradingAttempt).where(
                        GradingAttempt.submission_id == submission_id
                    )
                )
            ).scalars().all()
            if len(attempts) != 1 or attempts[0].status != "completed":
                raise AssertionError("Completed grading attempt was not persisted")
            if not attempts[0].raw_ocr_result["pages"]:
                raise AssertionError("OCR snapshot is missing from grading attempt")
            if not attempts[0].result_snapshot["questions"]:
                raise AssertionError("Result snapshot is missing from grading attempt")

            audit = (
                await db.execute(
                    select(AuditLog).where(
                        AuditLog.resource_type == "submission",
                        AuditLog.resource_id == submission_id,
                        AuditLog.action == "submission.grade",
                    )
                )
            ).scalar_one_or_none()
            if audit is None or audit.outcome != "success":
                raise AssertionError("Submission grade audit event was not persisted")

        print(
            f"PASS task_id={task_id} events={statuses} with history and audit"
        )
    finally:
        async with AsyncSession() as db:
            if submission_id is not None:
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
                await db.execute(
                    delete(Submission).where(Submission.id == submission_id)
                )
            if question_id is not None:
                await db.execute(
                    delete(Question).where(Question.id == question_id)
                )
            if assignment_id is not None:
                await db.execute(
                    delete(Assignment).where(Assignment.id == assignment_id)
                )
            await db.commit()
        await engine.dispose()
        print("CLEANUP complete")


if __name__ == "__main__":
    asyncio.run(main())
