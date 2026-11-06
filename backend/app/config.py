import os


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    try:
        return int(value) if value else default
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    try:
        return float(value) if value else default
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "mysql+aiomysql://root:root123@localhost:3306/ai_homework",
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://:redis123@localhost:6379/0")
    RABBITMQ_URL: str = os.getenv(
        "RABBITMQ_URL", "amqp://grader:grader_pass@localhost:5672//"
    )
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "ai-homework-submissions")
    MINIO_SECURE: bool = _env_bool("MINIO_SECURE")
    MAX_UPLOAD_IMAGE_BYTES: int = _env_int(
        "MAX_UPLOAD_IMAGE_BYTES", 10 * 1024 * 1024
    )
    MAX_SUBMISSION_IMAGES: int = _env_int("MAX_SUBMISSION_IMAGES", 10)
    GRADER_VERSION: str = os.getenv("GRADER_VERSION", "1.0.0")
    OCR_SERVICE_URL: str = os.getenv("OCR_SERVICE_URL", "http://localhost:5001")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    LLM_TIMEOUT_SECONDS: float = _env_float("LLM_TIMEOUT_SECONDS", 8.0)
    LLM_MAX_COMPLETION_TOKENS: int = _env_int("LLM_MAX_COMPLETION_TOKENS", 240)
    LLM_MAX_OUTPUT_CHARS: int = _env_int("LLM_MAX_OUTPUT_CHARS", 500)
    LLM_TOKEN_PARAMETER: str = os.getenv(
        "LLM_TOKEN_PARAMETER", "max_completion_tokens"
    )
    REPORT_CACHE_TTL_SECONDS: int = _env_int("REPORT_CACHE_TTL_SECONDS", 300)
    LOGIN_RATE_LIMIT_PER_MINUTE: int = _env_int("LOGIN_RATE_LIMIT_PER_MINUTE", 5)
    API_RATE_LIMIT_PER_MINUTE: int = _env_int("API_RATE_LIMIT_PER_MINUTE", 60)
    TRUST_PROXY_HEADERS: bool = _env_bool("TRUST_PROXY_HEADERS")
    CORS_ALLOWED_ORIGINS: list[str] = _env_list(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:8080,http://127.0.0.1:4173",
    )
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
    JWT_PEPPER: str = os.getenv("JWT_PEPPER", "dev-pepper")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7


settings = Settings()
