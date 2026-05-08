"""v1 API router aggregation."""

from fastapi import APIRouter, FastAPI

from app.api.v1.routes import (
    ai_routes,
    auth_routes,
    chat_routes,
    import_routes,
    question_routes,
    study_routes,
)

v1_router = APIRouter(prefix="/api/v1")


def register_routes(app: FastAPI) -> None:
    v1_router.include_router(auth_routes.router, prefix="/auth", tags=["auth"])
    v1_router.include_router(import_routes.router, prefix="/import", tags=["import"])
    v1_router.include_router(question_routes.router, prefix="/questions", tags=["questions"])
    v1_router.include_router(study_routes.router, prefix="/study", tags=["study"])
    v1_router.include_router(chat_routes.router, prefix="/chat", tags=["chat"])
    v1_router.include_router(ai_routes.router, prefix="/ai", tags=["ai"])

    app.include_router(v1_router)
