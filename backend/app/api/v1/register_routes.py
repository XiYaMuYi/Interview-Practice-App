"""Register all v1 API routers."""

from fastapi import FastAPI

from app.api.v1.routes import (
    ai_routes,
    event_routes,
    health_routes,
    import_routes,
    question_routes,
    resume_routes,
    task_events,
)


def register_routes(app: FastAPI) -> None:
    app.include_router(ai_routes.router, prefix="/api/v1/ai", tags=["ai"])
    app.include_router(event_routes.router, prefix="/api/v1/events", tags=["events"])
    app.include_router(import_routes.router, prefix="/api/v1/import", tags=["import"])
    app.include_router(question_routes.router, prefix="/api/v1/questions", tags=["questions"])
    app.include_router(resume_routes.router, prefix="/api/v1/resumes", tags=["resumes"])
    app.include_router(task_events.router, prefix="/api/v1/tasks", tags=["tasks"])
