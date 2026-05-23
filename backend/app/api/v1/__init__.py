"""v1 API router aggregation."""

from fastapi import APIRouter, FastAPI

from app.api.v1.routes import (
    ai_routes,
    auth_routes,
    chat_routes,
    exam_routes,
    health_routes,
    import_routes,
    metrics_routes,
    prompt_routes,
    question_routes,
    resume_routes,
    study_routes,
    task_events,
)

v1_router = APIRouter(prefix="/api/v1")


def register_routes(app: FastAPI) -> None:
    v1_router.include_router(auth_routes.router, prefix="/auth", tags=["auth"])
    v1_router.include_router(import_routes.router, prefix="/import", tags=["import"])
    v1_router.include_router(question_routes.router, prefix="/questions", tags=["questions"])
    v1_router.include_router(study_routes.router, prefix="/study", tags=["study"])
    v1_router.include_router(chat_routes.router, prefix="/chat", tags=["chat"])
    v1_router.include_router(ai_routes.router, prefix="/ai", tags=["ai"])
    v1_router.include_router(resume_routes.router, prefix="/resumes", tags=["resumes"])
    v1_router.include_router(task_events.router, prefix="/tasks", tags=["tasks"])
    v1_router.include_router(prompt_routes.router, prefix="/prompts", tags=["prompts"])
    v1_router.include_router(metrics_routes.router)
    v1_router.include_router(exam_routes.router, prefix="/exams", tags=["exams"])

    app.include_router(v1_router)
