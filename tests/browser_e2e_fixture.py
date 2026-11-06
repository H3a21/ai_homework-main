"""Create and remove isolated records for Docker browser E2E tests."""

import argparse
import asyncio
import json
import os
import re
import sys

from sqlalchemy import delete, select

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.auth import _hash_password
from app.config import settings
from app.database import AsyncSession, engine
from app.models import (
    Assignment,
    Class,
    ClassMember,
    GradingBatch,
    GradingResult,
    KnowledgePoint,
    Question,
    StudentKnowledgeMastery,
    Subject,
    Submission,
    SubmissionImage,
    User,
)
from app.object_storage import get_minio_client
from app.report_cache import invalidate_report_cache


PASSWORD = "E2e-demo-123"


def _validate_run_id(run_id: str) -> str:
    if re.fullmatch(r"[0-9a-f]{8}", run_id) is None:
        raise ValueError("run_id must contain exactly 8 lowercase hex characters")
    return run_id


def _names(run_id: str) -> dict[str, str]:
    return {
        "teacher_username": f"e2e_teacher_{run_id}",
        "student_username": f"e2e_student_{run_id}",
        "batch_student_username": f"e2e_batch_student_{run_id}",
        "teacher_name": f"E2E教师-{run_id}",
        "student_name": f"E2E学生-{run_id}",
        "batch_student_name": f"E2E批次学生-{run_id}",
        "class_name": f"E2E班级-{run_id}",
        "invite_code": f"E2E{run_id}",
        "assignment_title": f"E2E学生提交-{run_id}",
        "teacher_assignment_title": f"E2E教师发布-{run_id}",
        "batch_assignment_title": f"E2E批量批改-{run_id}",
        "knowledge_point_name": f"E2E知识点-{run_id}",
    }


async def cleanup(run_id: str) -> None:
    names = _names(_validate_run_id(run_id))
    object_names: list[str] = []
    class_id = None
    student_id = None

    async with AsyncSession() as db:
        classroom = (
            await db.execute(
                select(Class).where(Class.invite_code == names["invite_code"])
            )
        ).scalar_one_or_none()
        student = (
            await db.execute(
                select(User).where(User.username == names["student_username"])
            )
        ).scalar_one_or_none()
        teacher = (
            await db.execute(
                select(User).where(User.username == names["teacher_username"])
            )
        ).scalar_one_or_none()
        batch_student = (
            await db.execute(
                select(User).where(
                    User.username == names["batch_student_username"]
                )
            )
        ).scalar_one_or_none()
        point = (
            await db.execute(
                select(KnowledgePoint).where(
                    KnowledgePoint.name == names["knowledge_point_name"]
                )
            )
        ).scalar_one_or_none()

        class_id = classroom.id if classroom else None
        student_id = student.id if student else None
        assignment_ids: list[int] = []
        if class_id is not None:
            assignment_ids = [
                row[0]
                for row in await db.execute(
                    select(Assignment.id).where(Assignment.class_id == class_id)
                )
            ]

        submission_ids: list[int] = []
        if assignment_ids:
            submission_ids = [
                row[0]
                for row in await db.execute(
                    select(Submission.id).where(
                        Submission.assignment_id.in_(assignment_ids)
                    )
                )
            ]
            await db.execute(
                delete(GradingBatch).where(
                    GradingBatch.assignment_id.in_(assignment_ids)
                )
            )
        if submission_ids:
            object_names = [
                row[0]
                for row in await db.execute(
                    select(SubmissionImage.image_path).where(
                        SubmissionImage.submission_id.in_(submission_ids)
                    )
                )
            ]
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
        if assignment_ids:
            await db.execute(
                delete(Question).where(Question.assignment_id.in_(assignment_ids))
            )
            await db.execute(
                delete(Assignment).where(Assignment.id.in_(assignment_ids))
            )
        if student_id is not None:
            await db.execute(
                delete(StudentKnowledgeMastery).where(
                    StudentKnowledgeMastery.student_id == student_id
                )
            )
        if point is not None:
            await db.execute(
                delete(StudentKnowledgeMastery).where(
                    StudentKnowledgeMastery.knowledge_point_id == point.id
                )
            )
            await db.execute(
                delete(KnowledgePoint).where(KnowledgePoint.id == point.id)
            )
        member_ids = [
            user.id
            for user in (student, teacher, batch_student)
            if user is not None
        ]
        if member_ids:
            await db.execute(
                delete(ClassMember).where(ClassMember.user_id.in_(member_ids))
            )
        if class_id is not None:
            await db.execute(delete(Class).where(Class.id == class_id))
        if member_ids:
            await db.execute(delete(User).where(User.id.in_(member_ids)))
        await db.commit()

    if student_id is not None and class_id is not None:
        await invalidate_report_cache(student_id, class_id)
    if object_names:
        client = get_minio_client()
        for object_name in object_names:
            if object_name.startswith("submissions/"):
                try:
                    client.remove_object(settings.MINIO_BUCKET, object_name)
                except Exception:
                    pass


async def setup(run_id: str) -> dict:
    run_id = _validate_run_id(run_id)
    await cleanup(run_id)
    names = _names(run_id)

    async with AsyncSession() as db:
        subject = (
            await db.execute(select(Subject).where(Subject.id == 1))
        ).scalar_one_or_none()
        if subject is None:
            raise RuntimeError("Subject id 1 is required by the current frontend")

        teacher = User(
            username=names["teacher_username"],
            password_hash=_hash_password(PASSWORD),
            display_name=names["teacher_name"],
            role="teacher",
        )
        student = User(
            username=names["student_username"],
            password_hash=_hash_password(PASSWORD),
            display_name=names["student_name"],
            role="student",
        )
        batch_student = User(
            username=names["batch_student_username"],
            password_hash=_hash_password(PASSWORD),
            display_name=names["batch_student_name"],
            role="student",
        )
        db.add_all([teacher, student, batch_student])
        await db.commit()
        await db.refresh(teacher)
        await db.refresh(student)
        await db.refresh(batch_student)

        classroom = Class(
            name=names["class_name"],
            grade="六年级",
            invite_code=names["invite_code"],
        )
        db.add(classroom)
        await db.commit()
        await db.refresh(classroom)
        db.add_all([
            ClassMember(
                class_id=classroom.id,
                user_id=teacher.id,
                role="head_teacher",
            ),
            ClassMember(
                class_id=classroom.id,
                user_id=student.id,
                role="student",
            ),
            ClassMember(
                class_id=classroom.id,
                user_id=batch_student.id,
                role="student",
            ),
        ])

        point = KnowledgePoint(
            subject_id=subject.id,
            name=names["knowledge_point_name"],
        )
        db.add(point)
        await db.commit()
        await db.refresh(point)

        assignment = Assignment(
            title=names["assignment_title"],
            class_id=classroom.id,
            subject_id=subject.id,
            teacher_id=teacher.id,
        )
        db.add(assignment)
        await db.commit()
        await db.refresh(assignment)
        db.add(
            Question(
                assignment_id=assignment.id,
                question_number=1,
                content="计算 2 + 2",
                answer="4",
                max_score=10,
                knowledge_point_id=point.id,
                difficulty=0,
                discrimination=1,
            )
        )
        await db.commit()

        batch_assignment = Assignment(
            title=names["batch_assignment_title"],
            class_id=classroom.id,
            subject_id=subject.id,
            teacher_id=teacher.id,
        )
        db.add(batch_assignment)
        await db.commit()
        await db.refresh(batch_assignment)
        db.add(
            Question(
                assignment_id=batch_assignment.id,
                question_number=1,
                content="计算 2 + 2",
                answer="4",
                max_score=10,
                difficulty=0,
                discrimination=1,
            )
        )
        await db.commit()

        for target_student in (student, batch_student):
            pending_submission = Submission(
                assignment_id=batch_assignment.id,
                student_id=target_student.id,
                status="pending",
            )
            db.add(pending_submission)
            await db.commit()
            await db.refresh(pending_submission)
            db.add(
                SubmissionImage(
                    submission_id=pending_submission.id,
                    image_path=f"cached-e2e-batch-{pending_submission.id}.png",
                    page_number=1,
                    recognized_text="4",
                )
            )
        await db.commit()

    return {
        **names,
        "password": PASSWORD,
        "class_id": classroom.id,
        "assignment_id": assignment.id,
        "batch_assignment_id": batch_assignment.id,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["setup", "cleanup"])
    parser.add_argument("run_id")
    args = parser.parse_args()

    try:
        if args.action == "setup":
            print(json.dumps(await setup(args.run_id), ensure_ascii=False))
        else:
            await cleanup(args.run_id)
            print(json.dumps({"cleaned": args.run_id}))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
