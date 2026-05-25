"""Register all v1 API routers."""

from fastapi import FastAPI

from app.api.middleware import AuditMiddleware
from app.api.v1.routes import (
    admin_routes,
    ai_routes,
    auth_routes,
    chat_routes,
    event_routes,
    exam_routes,
    import_routes,
    question_routes,
    resume_routes,
    study_routes,
    task_events,
)


def register_routes(app: FastAPI) -> None:
    app.include_router(admin_routes.router, prefix="/api/v1/admin", tags=["admin"])
    app.include_router(ai_routes.router, prefix="/api/v1/ai", tags=["ai"])
    app.include_router(auth_routes.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(chat_routes.router, prefix="/api/v1/chat", tags=["chat"])
    app.include_router(event_routes.router, prefix="/api/v1/events", tags=["events"])
    app.include_router(exam_routes.router, prefix="/api/v1/exams", tags=["exams"])
    app.include_router(import_routes.router, prefix="/api/v1/import", tags=["import"])
    app.include_router(question_routes.router, prefix="/api/v1/questions", tags=["questions"])
    app.include_router(resume_routes.router, prefix="/api/v1/resumes", tags=["resumes"])
    app.include_router(study_routes.router, prefix="/api/v1/study", tags=["study"])
    app.include_router(task_events.router, prefix="/api/v1/tasks", tags=["tasks"])
    app.add_middleware(AuditMiddleware)
