from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import RegisterRequest, LoginRequest, RefreshRequest, TokenResponse, UserResponse
from app.dependencies import get_current_user

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter(prefix="/api/auth", tags=["auth"])


def _hash_with_pepper(password: str) -> str:
    return password + settings.JWT_PEPPER


def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(_hash_with_pepper(plain), hashed)


def _hash_password(plain: str) -> str:
    return pwd_context.hash(_hash_with_pepper(plain))


def _create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    request: Request,
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == body.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户名已存在")

    user = User(
        username=body.username,
        password_hash=_hash_password(body.password),
        display_name=body.display_name,
        role=body.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    request.state.actor_id = user.id

    token_data = {"sub": str(user.id), "role": user.role}
    return TokenResponse(
        access_token=_create_access_token(token_data),
        refresh_token=_create_refresh_token(token_data),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if not user or not _verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    request.state.actor_id = user.id
    token_data = {"sub": str(user.id), "role": user.role}
    return TokenResponse(
        access_token=_create_access_token(token_data),
        refresh_token=_create_refresh_token(token_data),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, body: RefreshRequest):
    try:
        payload = jwt.decode(
            body.refresh_token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="无效的刷新令牌")
        request.state.actor_id = int(payload["sub"])
        token_data = {"sub": payload["sub"], "role": payload.get("role", "student")}
        return TokenResponse(
            access_token=_create_access_token(token_data),
            refresh_token=_create_refresh_token(token_data),
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="刷新令牌已过期或无效")


@router.get("/me", response_model=UserResponse)
async def get_current_user_route(user: User = Depends(get_current_user)):
    return UserResponse(
        id=user.id, username=user.username, display_name=user.display_name, role=user.role
    )
