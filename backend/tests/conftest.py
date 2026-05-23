"""Shared test fixtures.

API integration tests use the Docker PostgreSQL (same DB as dev).
Schema tests (test_schemas.py) don't need a DB at all.

Each test gets a fresh engine to avoid event-loop / connection pool issues.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.core.config import settings
from app.infra.db.session import get_db


def _make_test_engine():
    """Create a fresh async engine + sessionmaker for a single test."""
    eng = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=False,  # avoid ping-on-checkout after event loop swap
        pool_size=5,
        max_overflow=0,
    )
    sess = async_sessionmaker(eng, class_=SQLModelAsyncSession, expire_on_commit=False)
    return eng, sess


@pytest.fixture
async def db_session() -> AsyncGenerator[SQLModelAsyncSession, None]:
    """Provide a fresh DB session with its own engine, rolled back after test."""
    eng, TestSession = _make_test_engine()
    async with TestSession() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await eng.dispose()


@pytest.fixture
async def app(db_session: SQLModelAsyncSession):
    """Create a FastAPI test app with the test DB session overridden."""
    from fastapi import FastAPI, Depends
    from app.api.v1 import register_routes
    from app.api.v1.routes import health_routes

    app = FastAPI(
        title="Test App",
        debug=True,
        redirect_slashes=False,
    )

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    app.include_router(health_routes.router)
    register_routes(app)

    yield app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """HTTPX async test client."""
    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Helper: create a question in the test DB ──

from app.domain.models import Question


async def create_question(
    db_session: SQLModelAsyncSession,
    *,
    title: str = "Test Question",
    content: str = "What is Python?",
    source_type: str = "manual",
    **extra: Any,
):
    """Create a Question record in the test DB and return it."""
    q = Question(title=title, content=content, source_type=source_type, **extra)
    db_session.add(q)
    await db_session.flush()
    return q
