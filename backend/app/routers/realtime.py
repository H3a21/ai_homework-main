import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control import require_class_teacher, require_submission_access
from app.config import settings
from app.database import get_db
from app.dependencies import decode_access_token
from app.models import Assignment, GradingBatch, Submission, User
from app.submission_events import subscribe_batch_events, subscribe_submission_events


router = APIRouter(prefix="/api/ws", tags=["realtime"])
logger = logging.getLogger(__name__)


def _snapshot(submission: Submission) -> dict:
    return {
        "type": "submission.snapshot",
        "submission_id": submission.id,
        "status": submission.status,
    }


def _batch_snapshot(batch: GradingBatch) -> dict:
    finished = batch.completed_submissions + batch.failed_submissions
    return {
        "type": "grading_batch.snapshot",
        "batch_id": batch.id,
        "status": batch.status,
        "total_submissions": batch.total_submissions,
        "completed_submissions": batch.completed_submissions,
        "failed_submissions": batch.failed_submissions,
        "finished_submissions": finished,
        "progress_percent": round(finished * 100 / batch.total_submissions, 1)
        if batch.total_submissions
        else 100.0,
    }


async def _authenticate(websocket: WebSocket, db: AsyncSession) -> User:
    try:
        message = await asyncio.wait_for(websocket.receive_json(), timeout=5)
    except (TimeoutError, ValueError, WebSocketDisconnect) as exc:
        raise HTTPException(status_code=401, detail="WebSocket 认证失败") from exc

    if (
        not isinstance(message, dict)
        or message.get("type") != "auth"
        or not isinstance(message.get("token"), str)
    ):
        raise HTTPException(status_code=401, detail="WebSocket 认证消息无效")

    user_id = decode_access_token(message["token"])
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


@router.websocket("/submissions/{submission_id}")
async def submission_updates(
    websocket: WebSocket,
    submission_id: int,
    db: AsyncSession = Depends(get_db),
):
    origin = websocket.headers.get("origin")
    if origin and origin not in settings.CORS_ALLOWED_ORIGINS:
        await websocket.close(code=4403)
        return

    await websocket.accept()
    try:
        user = await _authenticate(websocket, db)
    except HTTPException:
        await websocket.close(code=4401)
        return

    submission = (
        await db.execute(select(Submission).where(Submission.id == submission_id))
    ).scalar_one_or_none()
    if not submission:
        await db.rollback()
        await websocket.close(code=4404)
        return

    assignment = (
        await db.execute(
            select(Assignment).where(Assignment.id == submission.assignment_id)
        )
    ).scalar_one_or_none()
    if not assignment:
        await db.rollback()
        await websocket.close(code=4404)
        return

    try:
        await require_submission_access(db, user, submission, assignment)
    except HTTPException:
        await db.rollback()
        await websocket.close(code=4403)
        return

    if submission.status == "completed":
        snapshot = _snapshot(submission)
        await db.rollback()
        await websocket.send_json(snapshot)
        await websocket.close(code=1000)
        return

    try:
        async with subscribe_submission_events(submission_id) as pubsub:
            current = (
                await db.execute(
                    select(Submission).where(Submission.id == submission_id)
                )
            ).scalar_one_or_none()
            if not current:
                await db.rollback()
                await websocket.close(code=4404)
                return
            snapshot = _snapshot(current)
            await db.rollback()
            await websocket.send_json(snapshot)
            if snapshot["status"] == "completed":
                await websocket.close(code=1000)
                return

            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=15,
                )
                if message and message.get("type") == "message":
                    try:
                        payload = json.loads(message["data"])
                    except (KeyError, TypeError, json.JSONDecodeError):
                        continue
                    await websocket.send_json(payload)
                else:
                    await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception(
            "submission_websocket_failed",
            extra={"submission_id": submission_id},
        )
        try:
            await websocket.send_json(
                {"type": "error", "code": "realtime_unavailable"}
            )
            await websocket.close(code=1013)
        except (RuntimeError, WebSocketDisconnect):
            pass


@router.websocket("/batches/{batch_id}")
async def grading_batch_updates(
    websocket: WebSocket,
    batch_id: int,
    db: AsyncSession = Depends(get_db),
):
    origin = websocket.headers.get("origin")
    if origin and origin not in settings.CORS_ALLOWED_ORIGINS:
        await websocket.close(code=4403)
        return

    await websocket.accept()
    try:
        user = await _authenticate(websocket, db)
    except HTTPException:
        await websocket.close(code=4401)
        return
    if user.role != "teacher":
        await websocket.close(code=4403)
        return

    batch = (
        await db.execute(select(GradingBatch).where(GradingBatch.id == batch_id))
    ).scalar_one_or_none()
    if not batch:
        await db.rollback()
        await websocket.close(code=4404)
        return
    assignment = (
        await db.execute(
            select(Assignment).where(Assignment.id == batch.assignment_id)
        )
    ).scalar_one_or_none()
    if not assignment:
        await db.rollback()
        await websocket.close(code=4404)
        return
    try:
        await require_class_teacher(db, user.id, assignment.class_id)
    except HTTPException:
        await db.rollback()
        await websocket.close(code=4403)
        return

    if batch.status in ("completed", "failed"):
        snapshot = _batch_snapshot(batch)
        await db.rollback()
        await websocket.send_json(snapshot)
        await websocket.close(code=1000)
        return

    try:
        async with subscribe_batch_events(batch_id) as pubsub:
            current = (
                await db.execute(
                    select(GradingBatch).where(GradingBatch.id == batch_id)
                )
            ).scalar_one_or_none()
            if not current:
                await db.rollback()
                await websocket.close(code=4404)
                return
            snapshot = _batch_snapshot(current)
            await db.rollback()
            await websocket.send_json(snapshot)
            if snapshot["status"] in ("completed", "failed"):
                await websocket.close(code=1000)
                return

            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=15,
                )
                if message and message.get("type") == "message":
                    try:
                        payload = json.loads(message["data"])
                    except (KeyError, TypeError, json.JSONDecodeError):
                        continue
                    await websocket.send_json(payload)
                    if payload.get("status") in ("completed", "failed"):
                        await websocket.close(code=1000)
                        return
                else:
                    await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception(
            "grading_batch_websocket_failed",
            extra={"batch_id": batch_id},
        )
        try:
            await websocket.send_json(
                {"type": "error", "code": "realtime_unavailable"}
            )
            await websocket.close(code=1013)
        except (RuntimeError, WebSocketDisconnect):
            pass
