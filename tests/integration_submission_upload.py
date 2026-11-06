"""Docker integration test for private MinIO submission image storage."""

import asyncio
import base64
import os
import sys
from uuid import uuid4

import httpx
from sqlalchemy import delete, select

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.config import settings
from app.database import AsyncSession, engine
from app.models import (
    Assignment,
    Class,
    Question,
    Submission,
    SubmissionImage,
    Subject,
)
from app.object_storage import get_minio_client


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
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
    submission_id = None
    object_name = None

    try:
        async with AsyncSession() as db:
            classroom = (
                await db.execute(select(Class).where(Class.invite_code == "DEMO2026"))
            ).scalar_one()
            subject = (await db.execute(select(Subject).order_by(Subject.id))).scalars().first()
            if subject is None:
                raise AssertionError("Seed subject is missing")

        async with httpx.AsyncClient(
            base_url="http://backend:8000",
            timeout=30,
        ) as client:
            teacher_token = await _login(
                client, "math_teacher", "198.51.100.30"
            )
            teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
            create_assignment = await client.post(
                "/api/assignments",
                headers=teacher_headers,
                json={
                    "title": f"MinIO integration {uuid4().hex[:8]}",
                    "class_id": classroom.id,
                    "subject_id": subject.id,
                    "questions": [
                        {
                            "question_number": 1,
                            "content": "2 + 2",
                            "answer": "4",
                            "max_score": 10,
                        }
                    ],
                },
            )
            create_assignment.raise_for_status()
            assignment_id = create_assignment.json()["id"]

            student_token = await _login(
                client, "student_a", "198.51.100.31"
            )
            student_headers = {"Authorization": f"Bearer {student_token}"}

            assignment_response = await client.get(
                f"/api/assignments/{assignment_id}", headers=student_headers
            )
            assignment_response.raise_for_status()
            question = assignment_response.json()["questions"][0]
            if "answer" in question:
                raise AssertionError("Student assignment response leaked the answer")

            upload = await client.post(
                "/api/submissions/images",
                headers=student_headers,
                files={"image": ("homework.png", PNG_BYTES, "image/png")},
            )
            upload.raise_for_status()
            object_name = upload.json()["image_path"]
            if not object_name.startswith("submissions/"):
                raise AssertionError("Unexpected MinIO object name")

            create_submission = await client.post(
                "/api/submissions",
                headers=student_headers,
                json={
                    "assignment_id": assignment_id,
                    "image_paths": [object_name],
                    "auto_grade": False,
                },
            )
            create_submission.raise_for_status()
            submission_id = create_submission.json()["id"]

            detail = await client.get(
                f"/api/submissions/{submission_id}", headers=student_headers
            )
            detail.raise_for_status()
            image_url = detail.json()["images"][0]["image_path"]
            image_response = await client.get(image_url, headers=student_headers)
            image_response.raise_for_status()
            if image_response.content != PNG_BYTES:
                raise AssertionError("Downloaded image differs from uploaded content")
            if image_response.headers.get("content-type") != "image/png":
                raise AssertionError("Downloaded image content type is incorrect")

            unauthenticated = await client.get(image_url)
            if unauthenticated.status_code != 401:
                raise AssertionError("Private image endpoint allowed anonymous access")

        print(
            "PASS private MinIO upload, submission binding, answer redaction, "
            "and authenticated image download"
        )
    finally:
        async with AsyncSession() as db:
            if submission_id is not None:
                await db.execute(
                    delete(SubmissionImage).where(
                        SubmissionImage.submission_id == submission_id
                    )
                )
                await db.execute(
                    delete(Submission).where(Submission.id == submission_id)
                )
            if assignment_id is not None:
                await db.execute(
                    delete(Question).where(Question.assignment_id == assignment_id)
                )
                await db.execute(
                    delete(Assignment).where(Assignment.id == assignment_id)
                )
            await db.commit()

        if object_name is not None:
            get_minio_client().remove_object(settings.MINIO_BUCKET, object_name)
        await engine.dispose()
        print("CLEANUP complete")


if __name__ == "__main__":
    asyncio.run(main())
