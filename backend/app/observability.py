import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    multiprocess,
)

from app.audit_service import AuditEvent, persist_audit_event
from app.security import (
    audit_client_id,
    client_identity,
    request_id_from_header,
)


HTTP_REQUESTS = Counter(
    "ai_homework_http_requests_total",
    "Total HTTP requests handled by the backend.",
    ("method", "route", "status"),
)
HTTP_REQUEST_DURATION = Histogram(
    "ai_homework_http_request_duration_seconds",
    "Backend HTTP request duration in seconds.",
    ("method", "route"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
GRADING_TASKS = Counter(
    "ai_homework_grading_tasks_total",
    "Total grading task attempts.",
    ("subject", "status"),
)
GRADING_DURATION = Histogram(
    "ai_homework_grading_duration_seconds",
    "Grading task attempt duration in seconds.",
    ("subject",),
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300),
)
GRADING_RETRIES = Counter(
    "ai_homework_grading_retries_total",
    "Total grading task retries.",
    ("subject",),
)

router = APIRouter(tags=["observability"])
request_logger = logging.getLogger("app.requests")
audit_logger = logging.getLogger("app.audit")


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str):
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": self.service,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in (
            "request_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "task_id",
            "submission_id",
            "subject",
            "task_status",
            "event",
            "action",
            "outcome",
            "actor_id",
            "client_id",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(service: str) -> None:
    root = logging.getLogger()
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    root.setLevel(getattr(logging, level, logging.INFO))

    for handler in root.handlers:
        if getattr(handler, "_ai_homework_json", False):
            handler.setFormatter(JsonFormatter(service))
            return

    handler = logging.StreamHandler(sys.stdout)
    handler._ai_homework_json = True
    handler.setFormatter(JsonFormatter(service))
    root.addHandler(handler)


def _metrics_registry():
    if os.getenv("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return registry
    return REGISTRY


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", None) or "unmatched"


def _audit_http_request(
    request: Request, status_code: int, request_id: str
) -> AuditEvent | None:
    event = None
    action = None
    if status_code == 429:
        event, action = "security.rate_limit", "request"
    elif request.url.path == "/api/auth/login":
        event, action = "authentication", "login"
    elif status_code in (401, 403):
        event, action = "authorization", "access"
    elif request.method in ("POST", "PUT", "PATCH", "DELETE"):
        event, action = "data_change", request.method.lower()

    if event is None:
        return None

    if status_code < 400:
        outcome = "success"
    elif status_code in (401, 403, 429):
        outcome = "denied"
    else:
        outcome = "failure"

    resource_type, resource_id = _audit_resource(request.url.path)
    action = _audit_action(request, action, resource_type)
    audit_event = AuditEvent(
        request_id=request_id,
        user_id=getattr(request.state, "actor_id", None),
        action=action,
        resource_type=resource_type,
        resource_id=getattr(
            request.state,
            "audit_resource_id",
            resource_id,
        ),
        old_value=getattr(request.state, "audit_old_value", None),
        new_value=getattr(request.state, "audit_new_value", None),
        ip_address=client_identity(request),
        user_agent=(request.headers.get("User-Agent") or "")[:500] or None,
        outcome=outcome,
        method=request.method,
        path=request.url.path[:500],
        status_code=status_code,
    )

    audit_logger.info(
        "security_audit",
        extra={
            "request_id": request_id,
            "event": event,
            "action": audit_event.action,
            "outcome": outcome,
            "actor_id": getattr(request.state, "actor_id", None),
            "client_id": audit_client_id(request),
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
        },
    )
    return audit_event


def _audit_resource(path: str) -> tuple[str, int | None]:
    parts = [part for part in path.split("/") if part]
    if parts and parts[0] == "api":
        parts = parts[1:]
    collection = parts[0] if parts else "endpoint"
    resource_types = {
        "auth": "user",
        "classes": "class",
        "assignments": "assignment",
        "submissions": "submission",
        "grading-batches": "grading_batch",
        "knowledge": "knowledge",
        "reports": "report",
    }
    resource_type = resource_types.get(collection, collection or "endpoint")
    resource_id = next(
        (int(part) for part in parts[1:] if part.isdigit()),
        None,
    )
    if collection == "submissions" and len(parts) > 1 and parts[1] == "images":
        resource_type = "submission_image"
    return resource_type[:50], resource_id


def _audit_action(request: Request, fallback: str, resource_type: str) -> str:
    path = request.url.path
    if path == "/api/auth/login":
        return "user.login"
    if path.endswith("/grade"):
        return "submission.grade"
    if path.endswith("/students"):
        return "class.student.add"
    if path.endswith("/images"):
        return "submission_image.upload"
    if fallback == "access":
        return f"{resource_type}.access"
    if fallback == "request":
        return f"{resource_type}.rate_limit"
    verbs = {
        "POST": "create",
        "PUT": "replace",
        "PATCH": "update",
        "DELETE": "delete",
    }
    return f"{resource_type}.{verbs.get(request.method, fallback)}"[:50]


async def observe_http_request(request: Request, call_next):
    request_id = request_id_from_header(request.headers.get("X-Request-ID"))
    request.state.request_id = request_id
    started_at = time.perf_counter()
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        raise
    finally:
        duration = time.perf_counter() - started_at
        route = _route_template(request)
        HTTP_REQUESTS.labels(
            method=request.method,
            route=route,
            status=str(status_code),
        ).inc()
        HTTP_REQUEST_DURATION.labels(method=request.method, route=route).observe(duration)
        request_logger.info(
            "http_request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": round(duration * 1000, 2),
            },
        )
        audit_event = _audit_http_request(request, status_code, request_id)
        if audit_event is not None:
            await persist_audit_event(audit_event)

    response.headers["X-Request-ID"] = request_id
    return response


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(
        content=generate_latest(_metrics_registry()),
        media_type=CONTENT_TYPE_LATEST,
    )
