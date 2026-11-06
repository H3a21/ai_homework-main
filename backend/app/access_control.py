from collections.abc import Sequence

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, ClassMember, Submission, User


TEACHER_CLASS_ROLES = ("head_teacher", "teacher")


async def require_class_member(
    db: AsyncSession,
    user_id: int,
    class_id: int,
    roles: Sequence[str],
) -> None:
    membership = await db.execute(
        select(ClassMember.id).where(
            ClassMember.class_id == class_id,
            ClassMember.user_id == user_id,
            ClassMember.role.in_(roles),
        )
    )
    if membership.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="无权访问该班级")


async def require_class_access(
    db: AsyncSession,
    user: User,
    class_id: int,
) -> None:
    if user.role == "teacher":
        roles = TEACHER_CLASS_ROLES
    elif user.role == "student":
        roles = ("student",)
    else:
        raise HTTPException(status_code=403, detail="权限不足")
    await require_class_member(db, user.id, class_id, roles)


async def require_class_teacher(
    db: AsyncSession,
    teacher_id: int,
    class_id: int,
) -> None:
    await require_class_member(db, teacher_id, class_id, TEACHER_CLASS_ROLES)


async def require_assignment_access(
    db: AsyncSession,
    user: User,
    assignment: Assignment,
) -> None:
    await require_class_access(db, user, assignment.class_id)


async def require_submission_access(
    db: AsyncSession,
    user: User,
    submission: Submission,
    assignment: Assignment,
) -> None:
    if user.role == "student":
        if submission.student_id != user.id:
            raise HTTPException(status_code=403, detail="无权访问该提交记录")
        return
    if user.role == "teacher":
        await require_class_teacher(db, user.id, assignment.class_id)
        return
    raise HTTPException(status_code=403, detail="权限不足")


async def require_teacher_student_access(
    db: AsyncSession,
    teacher_id: int,
    student_id: int,
) -> None:
    managed_class_ids = select(ClassMember.class_id).where(
        ClassMember.user_id == teacher_id,
        ClassMember.role.in_(TEACHER_CLASS_ROLES),
    )
    shared_class = await db.execute(
        select(ClassMember.id).where(
            ClassMember.user_id == student_id,
            ClassMember.role == "student",
            ClassMember.class_id.in_(managed_class_ids),
        )
    )
    if shared_class.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="无权访问该学生数据")
