from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User

router = APIRouter(prefix="/api/students", tags=["students"])


@router.get("")
async def list_students(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(User).where(User.role == "student").order_by(User.display_name)
    )
    students = result.scalars().all()
    return [
        {
            "id": s.id,
            "username": s.username,
            "display_name": s.display_name,
        }
        for s in students
    ]
