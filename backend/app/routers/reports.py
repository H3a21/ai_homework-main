from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.learning_reports import load_class_report, load_student_report
from app.models import ClassMember, User
from app.report_cache import (
    class_report_cache_key,
    get_report,
    set_report,
    student_report_cache_key,
)

router = APIRouter(prefix="/api/reports", tags=["reports"])


async def _teacher_can_view_class(
    db: AsyncSession,
    teacher_id: int,
    class_id: int,
) -> bool:
    result = await db.execute(
        select(ClassMember.id).where(
            ClassMember.class_id == class_id,
            ClassMember.user_id == teacher_id,
            ClassMember.role.in_(["head_teacher", "teacher"]),
        )
    )
    return result.scalar_one_or_none() is not None


async def _teacher_can_view_student(
    db: AsyncSession,
    teacher_id: int,
    student_id: int,
) -> bool:
    teacher_classes = await db.execute(
        select(ClassMember.class_id).where(
            ClassMember.user_id == teacher_id,
            ClassMember.role.in_(["head_teacher", "teacher"]),
        )
    )
    class_ids = [row[0] for row in teacher_classes]
    if not class_ids:
        return False
    student_class = await db.execute(
        select(ClassMember.id).where(
            ClassMember.user_id == student_id,
            ClassMember.class_id.in_(class_ids),
            ClassMember.role == "student",
        )
    )
    return student_class.scalar_one_or_none() is not None


def _with_cache_metadata(report: dict, hit: bool) -> dict:
    return {**report, "cache": {"hit": hit}}


@router.get("/students/{student_id}")
async def get_student_report(
    student_id: int,
    subject_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == "student":
        if user.id != student_id:
            raise HTTPException(status_code=403, detail="只能查看自己的学情报告")
    elif user.role == "teacher":
        if not await _teacher_can_view_student(db, user.id, student_id):
            raise HTTPException(status_code=403, detail="无权查看该学生的学情报告")
    else:
        raise HTTPException(status_code=403, detail="权限不足")

    key = student_report_cache_key(student_id, subject_id)
    cached = await get_report(key)
    if cached is not None:
        return _with_cache_metadata(cached, True)

    report = await load_student_report(db, student_id, subject_id)
    if report is None:
        raise HTTPException(status_code=404, detail="学生不存在")
    await set_report(key, report)
    return _with_cache_metadata(report, False)


@router.get("/classes/{class_id}")
async def get_class_report(
    class_id: int,
    subject_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "teacher" or not await _teacher_can_view_class(
        db, user.id, class_id
    ):
        raise HTTPException(status_code=403, detail="无权查看该班级的学情报告")

    key = class_report_cache_key(class_id, subject_id)
    cached = await get_report(key)
    if cached is not None:
        return _with_cache_metadata(cached, True)

    report = await load_class_report(db, class_id, subject_id)
    if report is None:
        raise HTTPException(status_code=404, detail="班级不存在")
    await set_report(key, report)
    return _with_cache_metadata(report, False)
