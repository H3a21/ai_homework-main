from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control import require_teacher_student_access
from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import (
    KnowledgePoint,
    KnowledgeRelation,
    StudentKnowledgeMastery,
    Subject,
    User,
)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class CreateKnowledgePointRequest(BaseModel):
    subject_id: int
    name: str = Field(..., min_length=1, max_length=100)
    parent_id: Optional[int] = None


class CreateKnowledgeRelationRequest(BaseModel):
    prerequisite_id: int
    target_id: int
    relation_type: str = Field(default="prerequisite", pattern="^prerequisite$")
    strength: float = Field(default=1.0, ge=0.1, le=1.0)


def _point_payload(point: KnowledgePoint) -> dict:
    return {
        "id": point.id,
        "subject_id": point.subject_id,
        "name": point.name,
        "parent_id": point.parent_id,
    }


@router.get("/graph")
async def get_knowledge_graph(
    subject_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(KnowledgePoint).order_by(KnowledgePoint.subject_id, KnowledgePoint.id)
    if subject_id:
        query = query.where(KnowledgePoint.subject_id == subject_id)
    points = (await db.execute(query)).scalars().all()
    point_ids = [point.id for point in points]

    relations = []
    if point_ids:
        relation_result = await db.execute(
            select(KnowledgeRelation).where(
                KnowledgeRelation.prerequisite_id.in_(point_ids),
                KnowledgeRelation.target_id.in_(point_ids),
            ).order_by(KnowledgeRelation.id)
        )
        relations = relation_result.scalars().all()

    return {
        "subject_id": subject_id,
        "points": [_point_payload(point) for point in points],
        "relations": [
            {
                "id": relation.id,
                "prerequisite_id": relation.prerequisite_id,
                "target_id": relation.target_id,
                "relation_type": relation.relation_type,
                "strength": float(relation.strength),
            }
            for relation in relations
        ],
    }


@router.post("/points", status_code=201)
async def create_knowledge_point(
    body: CreateKnowledgePointRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("teacher")),
):
    subject = (
        await db.execute(select(Subject).where(Subject.id == body.subject_id))
    ).scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="学科不存在")

    if body.parent_id:
        parent = (
            await db.execute(
                select(KnowledgePoint).where(KnowledgePoint.id == body.parent_id)
            )
        ).scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail="父知识点不存在")
        if parent.subject_id != body.subject_id:
            raise HTTPException(status_code=400, detail="父知识点必须属于同一学科")

    duplicate = (
        await db.execute(
            select(KnowledgePoint).where(
                KnowledgePoint.subject_id == body.subject_id,
                KnowledgePoint.name == body.name.strip(),
            )
        )
    ).scalar_one_or_none()
    if duplicate:
        raise HTTPException(status_code=409, detail="知识点名称已存在")

    point = KnowledgePoint(
        subject_id=body.subject_id,
        name=body.name.strip(),
        parent_id=body.parent_id,
    )
    db.add(point)
    await db.commit()
    await db.refresh(point)
    return _point_payload(point)


@router.post("/relations", status_code=201)
async def create_knowledge_relation(
    body: CreateKnowledgeRelationRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("teacher")),
):
    if body.prerequisite_id == body.target_id:
        raise HTTPException(status_code=400, detail="知识点不能依赖自身")

    point_result = await db.execute(
        select(KnowledgePoint).where(
            KnowledgePoint.id.in_([body.prerequisite_id, body.target_id])
        )
    )
    points = point_result.scalars().all()
    points_by_id = {point.id: point for point in points}
    if len(points_by_id) != 2:
        raise HTTPException(status_code=404, detail="知识点不存在")
    if points_by_id[body.prerequisite_id].subject_id != points_by_id[body.target_id].subject_id:
        raise HTTPException(status_code=400, detail="关系两端必须属于同一学科")

    duplicate = (
        await db.execute(
            select(KnowledgeRelation).where(
                KnowledgeRelation.prerequisite_id == body.prerequisite_id,
                KnowledgeRelation.target_id == body.target_id,
                KnowledgeRelation.relation_type == body.relation_type,
            )
        )
    ).scalar_one_or_none()
    if duplicate:
        raise HTTPException(status_code=409, detail="知识点关系已存在")

    relation = KnowledgeRelation(
        prerequisite_id=body.prerequisite_id,
        target_id=body.target_id,
        relation_type=body.relation_type,
        strength=body.strength,
    )
    db.add(relation)
    await db.commit()
    await db.refresh(relation)
    return {
        "id": relation.id,
        "prerequisite_id": relation.prerequisite_id,
        "target_id": relation.target_id,
        "relation_type": relation.relation_type,
        "strength": float(relation.strength),
    }


@router.get("/mastery/{student_id}")
async def get_student_mastery(
    student_id: int,
    subject_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == "teacher":
        await require_teacher_student_access(db, user.id, student_id)
    elif user.role != "student" or user.id != student_id:
        raise HTTPException(status_code=403, detail="只能查看自己的掌握度")

    student = (
        await db.execute(select(User).where(User.id == student_id, User.role == "student"))
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    query = (
        select(StudentKnowledgeMastery, KnowledgePoint, Subject)
        .join(KnowledgePoint, KnowledgePoint.id == StudentKnowledgeMastery.knowledge_point_id)
        .join(Subject, Subject.id == KnowledgePoint.subject_id)
        .where(StudentKnowledgeMastery.student_id == student_id)
        .order_by(KnowledgePoint.subject_id, KnowledgePoint.id)
    )
    if subject_id:
        query = query.where(KnowledgePoint.subject_id == subject_id)

    rows = (await db.execute(query)).all()
    items = []
    for mastery, point, subject in rows:
        attempt_count = int(mastery.attempt_count or 0)
        success_sum = float(mastery.success_sum or 0.0)
        items.append({
            "knowledge_point_id": point.id,
            "knowledge_point_name": point.name,
            "subject_id": subject.id,
            "subject_name": subject.name,
            "mastery_level": float(mastery.mastery_level or 0.0),
            "ability_theta": float(mastery.ability_theta or 0.0),
            "attempt_count": attempt_count,
            "success_sum": success_sum,
            "average_score_ratio": round(success_sum / attempt_count, 3)
            if attempt_count else 0.0,
            "is_weak": float(mastery.mastery_level or 0.0) < 0.6,
        })

    return {
        "student_id": student_id,
        "student_name": student.display_name,
        "subject_id": subject_id,
        "items": items,
    }
