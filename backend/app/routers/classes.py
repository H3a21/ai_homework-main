import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control import require_class_access, require_class_teacher
from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import Class, ClassMember, User

router = APIRouter(prefix="/api/classes", tags=["classes"])


class CreateClassRequest(BaseModel):
    name: str
    grade: str = ""


class AddStudentRequest(BaseModel):
    student_id: int


@router.get("")
async def list_classes(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == "teacher":
        result = await db.execute(
            select(Class).join(ClassMember, ClassMember.class_id == Class.id).where(
                ClassMember.user_id == user.id,
                ClassMember.role.in_(["head_teacher", "teacher"]),
            )
        )
        classes = result.scalars().all()
    else:
        result = await db.execute(
            select(Class).join(ClassMember, ClassMember.class_id == Class.id).where(
                ClassMember.user_id == user.id,
                ClassMember.role == "student",
            )
        )
        classes = result.scalars().all()

    return [
        {
            "id": c.id,
            "name": c.name,
            "grade": c.grade,
            "invite_code": c.invite_code,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in classes
    ]


@router.get("/{class_id}")
async def get_class(
    class_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Class).where(Class.id == class_id)
    )
    cls = result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")

    await require_class_access(db, user, class_id)

    members_result = await db.execute(
        select(User, ClassMember.role)
        .join(ClassMember, ClassMember.user_id == User.id)
        .where(ClassMember.class_id == class_id)
    )
    members = []
    for u, role in members_result:
        members.append({
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "role": u.role,
            "class_role": role,
        })

    return {
        "id": cls.id,
        "name": cls.name,
        "grade": cls.grade,
        "invite_code": cls.invite_code,
        "created_at": cls.created_at.isoformat() if cls.created_at else None,
        "members": members,
    }


@router.post("")
async def create_class(
    body: CreateClassRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("teacher")),
):
    cls = Class(
        name=body.name,
        grade=body.grade,
        invite_code=uuid.uuid4().hex[:8].upper(),
    )
    db.add(cls)
    await db.commit()
    await db.refresh(cls)

    member = ClassMember(
        class_id=cls.id,
        user_id=user.id,
        role="head_teacher",
    )
    db.add(member)
    await db.commit()

    return {"id": cls.id, "name": cls.name, "grade": cls.grade, "invite_code": cls.invite_code}


@router.post("/{class_id}/students")
async def add_student(
    class_id: int,
    body: AddStudentRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("teacher")),
):
    result = await db.execute(select(Class).where(Class.id == class_id))
    cls = result.scalar_one_or_none()
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")

    await require_class_teacher(db, user.id, class_id)

    result = await db.execute(select(User).where(User.id == body.student_id, User.role == "student"))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    existing = await db.execute(
        select(ClassMember).where(
            ClassMember.class_id == class_id,
            ClassMember.user_id == body.student_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="学生已在班级中")

    member = ClassMember(class_id=class_id, user_id=body.student_id, role="student")
    db.add(member)
    await db.commit()

    return {"message": "添加成功"}
