"""API-level dependency placeholders — auth, session wiring, etc."""

from app.infra.db.session import DbSession

__all__ = ["DbSession"]
