"""Vector store infrastructure — pgvector backed similarity search."""

from app.infra.vectorstore.pgvector_store import PGVectorStore, VectorStoreError

__all__ = ["PGVectorStore", "VectorStoreError"]
