"""FastAPI application entry point."""

from fastapi import FastAPI

from app.core.config import settings
from app.core.logging import setup_logging


def create_app() -> FastAPI:
    setup_logging(debug=settings.DEBUG)

    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
    )

    # Register routes — import routers to trigger side-effect of router registration
    from app.api.v1 import register_routes  # noqa: F401

    register_routes(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
