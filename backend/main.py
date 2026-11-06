from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.auth import router as auth_router
from app.health import router as health_router
from app.routers.classes import router as classes_router
from app.routers.assignments import router as assignments_router
from app.routers.submissions import router as submissions_router
from app.routers.students import router as students_router
from app.routers.knowledge import router as knowledge_router
from app.routers.reports import router as reports_router
from app.routers.realtime import router as realtime_router
from app.routers.history import router as history_router
from app.routers.grading_batches import router as grading_batches_router
from app.observability import configure_logging, observe_http_request
from app.observability import router as observability_router
from app.security import enforce_rate_limits
from app.schema_migrations import ensure_profile_schema
from app.seed import seed_demo_data


configure_logging("backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_profile_schema()
    await seed_demo_data()
    yield


app = FastAPI(title="AI智能批改作业系统", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(enforce_rate_limits)
app.middleware("http")(observe_http_request)

app.include_router(observability_router)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(classes_router)
app.include_router(assignments_router)
app.include_router(submissions_router)
app.include_router(students_router)
app.include_router(knowledge_router)
app.include_router(reports_router)
app.include_router(realtime_router)
app.include_router(history_router)
app.include_router(grading_batches_router)
