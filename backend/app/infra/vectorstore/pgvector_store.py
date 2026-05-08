"""pgvector store — vector similarity search backed by PostgreSQL."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class VectorStoreError(Exception):
    pass


class PGVectorStore:
    """Thin wrapper around pgvector for similarity search on question_embeddings.

    Uses raw SQL to avoid ORM complexity of querying vector columns.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.dimension = settings.EMBEDDING_DIMENSION

    async def upsert(self, question_id: UUID, embedding: list[float], model_name: str = "default") -> None:
        """Insert or update an embedding for a question."""
        if len(embedding) != self.dimension:
            raise VectorStoreError(
                f"Embedding dimension mismatch: expected {self.dimension}, got {len(embedding)}"
            )

        vec_str = f"[{','.join(str(v) for v in embedding)}]"

        # Upsert: insert new or update existing
        await self.session.execute(
            text("""
                INSERT INTO question_embeddings (question_id, embedding, model_name, dimension)
                VALUES (:qid, :embedding::vector, :model, :dim)
                ON CONFLICT (question_id)
                DO UPDATE SET embedding = :embedding::vector,
                              model_name = :model,
                              dimension = :dim
            """),
            {
                "qid": str(question_id),
                "embedding": vec_str,
                "model": model_name,
                "dim": self.dimension,
            },
        )

    async def search_similar(
        self,
        query_embedding: list[float],
        *,
        limit: int = 10,
        threshold: float = 0.0,
        question_ids: list[UUID] | None = None,
    ) -> list[dict]:
        """Find questions most similar to the query embedding via cosine similarity.

        Returns list of dicts: {question_id, score}.
        """
        if len(query_embedding) != self.dimension:
            raise VectorStoreError(
                f"Embedding dimension mismatch: expected {self.dimension}, got {len(query_embedding)}"
            )

        vec_str = f"[{','.join(str(v) for v in query_embedding)}]"

        where_clause = ""
        if question_ids:
            ids_str = ",".join(f"'{str(qid)}'" for qid in question_ids)
            where_clause = f"AND question_id IN ({ids_str})"

        sql = f"""
            SELECT question_id,
                   1 - (embedding <=> :query_vec::vector) AS score
            FROM question_embeddings
            WHERE 1 - (embedding <=> :query_vec::vector) > :threshold
            {where_clause}
            ORDER BY score DESC
            LIMIT :limit
        """

        result = await self.session.execute(
            text(sql),
            {
                "query_vec": vec_str,
                "threshold": threshold,
                "limit": limit,
            },
        )
        rows = result.fetchall()
        return [{"question_id": row[0], "score": float(row[1])} for row in rows]

    async def delete(self, question_id: UUID) -> None:
        """Remove all embeddings for a question."""
        await self.session.execute(
            text("DELETE FROM question_embeddings WHERE question_id = :qid"),
            {"qid": str(question_id)},
        )
