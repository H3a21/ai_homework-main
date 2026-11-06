import asyncio
import logging

from sqlalchemy import select

from app.auth import _hash_password
from app.database import AsyncSession
from app.models import Class, ClassMember, Subject, User

logger = logging.getLogger(__name__)

DEMO_USERS = [
    {
        "username": "math_teacher",
        "password": "demo123",
        "display_name": "张老师",
        "role": "teacher",
    },
    {
        "username": "chinese_teacher",
        "password": "demo123",
        "display_name": "李老师",
        "role": "teacher",
    },
    {
        "username": "english_teacher",
        "password": "demo123",
        "display_name": "王老师",
        "role": "teacher",
    },
    {
        "username": "student_a",
        "password": "demo123",
        "display_name": "学生A",
        "role": "student",
    },
]


async def _ensure_subjects(db: AsyncSession):
    existing = await db.execute(select(Subject))
    if existing.scalars().first():
        return
    subjects = [
        Subject(name="数学", description="数学学科"),
        Subject(name="语文", description="语文学科"),
        Subject(name="英语", description="英语学科"),
    ]
    db.add_all(subjects)
    await db.commit()
    logger.info("Seeded default subjects")


async def seed_demo_data():
    for attempt in range(10):
        try:
            async with AsyncSession() as db:
                result = await db.execute(
                    select(User).where(User.username == DEMO_USERS[0]["username"])
                )
                if result.scalar_one_or_none():
                    logger.info("Demo data already exists, skipping seed")
                    return

                await _ensure_subjects(db)

                users = []
                for u in DEMO_USERS:
                    user = User(
                        username=u["username"],
                        password_hash=_hash_password(u["password"]),
                        display_name=u["display_name"],
                        role=u["role"],
                    )
                    db.add(user)
                    users.append(user)
                await db.commit()
                for u in users:
                    await db.refresh(u)

                math_teacher = next(u for u in users if u.username == "math_teacher")
                chinese_teacher = next(u for u in users if u.username == "chinese_teacher")
                english_teacher = next(u for u in users if u.username == "english_teacher")
                student_a = next(u for u in users if u.username == "student_a")

                demo_class = Class(
                    name="六年级一班",
                    grade="六年级",
                    invite_code="DEMO2026",
                )
                db.add(demo_class)
                await db.commit()
                await db.refresh(demo_class)

                db.add_all([
                    ClassMember(class_id=demo_class.id, user_id=math_teacher.id, role="head_teacher"),
                    ClassMember(class_id=demo_class.id, user_id=chinese_teacher.id, role="teacher"),
                    ClassMember(class_id=demo_class.id, user_id=english_teacher.id, role="teacher"),
                    ClassMember(class_id=demo_class.id, user_id=student_a.id, role="student"),
                ])
                await db.commit()

                logger.info(
                    "Demo data seeded: math_teacher(demo123), chinese_teacher(demo123), "
                    "english_teacher(demo123), student_a(demo123), class=六年级一班"
                )
            return
        except Exception as e:
            logger.warning(
                "Seed attempt %d/10 failed: %s. Retrying in 3s...", attempt + 1, e
            )
            if attempt < 9:
                await asyncio.sleep(3)
            else:
                logger.error("Seed failed after 10 attempts", exc_info=True)
