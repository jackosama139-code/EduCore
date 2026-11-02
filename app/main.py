import logging

from fastapi import FastAPI
from sqlalchemy import text

from app.api.routes import assignments, attendance, auth, courses, dashboard, students, users
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.db.session import engine

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("educore")


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.PROJECT_NAME} - College ERP & LMS",
        version="1.0.0",
        description="Role-based College ERP / LMS backend (admin, faculty, student). "
                    "Click **Authorize** and log in with email + password to try protected endpoints.",
    )
    register_exception_handlers(app)

    for r in (auth.router, users.router, students.router, courses.router,
              attendance.router, assignments.router, dashboard.router):
        app.include_router(r, prefix=settings.API_PREFIX)

    # Optional module: imported ONLY when enabled, so the core never depends on it.
    if settings.AI_ENABLED:
        from app.ai.router import router as assistant_router
        app.include_router(assistant_router, prefix=settings.API_PREFIX)
        log.info("AI learning assistant enabled (LLM key configured: %s)", bool(settings.ANTHROPIC_API_KEY))

    @app.get("/health", tags=["System"])
    def health():
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}

    return app


app = create_app()
