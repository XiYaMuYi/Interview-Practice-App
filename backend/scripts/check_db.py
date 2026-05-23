#!/usr/bin/env python
"""Database inspection script — record counts, recent errors, migration status, and size.

Usage:
    python scripts/check_db.py
"""

import asyncio
import sys
from pathlib import Path

# Add backend root to path so app.* imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.infra.db.session import engine


TABLES = [
    "questions",
    "tags",
    "question_tags",
    "knowledge_nodes",
    "question_knowledge_nodes",
    "study_records",
    "chat_histories",
    "files",
    "question_embeddings",
    "prompt_versions",
    "learning_profiles",
    "resumes",
    "resume_experiences",
    "llm_call_logs",
    "tasks",
]


async def check_record_counts() -> None:
    print("=== Record Counts ===")
    async with engine.connect() as conn:
        for table in TABLES:
            try:
                result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                print(f"  {table:30s} {count:>8,}")
            except Exception as e:
                print(f"  {table:30s} ERROR: {e}")
    print()


async def check_recent_errors() -> None:
    print("=== Failed Tasks (last 24h) ===")
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT COUNT(*) FROM tasks
            WHERE status = 'failed'
            AND created_at > NOW() - INTERVAL '24 hours'
        """))
        count = result.scalar()
        print(f"  Failed tasks in last 24h: {count}")

        if count > 0:
            detail = await conn.execute(text("""
                SELECT id, task_type, error_message, created_at
                FROM tasks
                WHERE status = 'failed'
                AND created_at > NOW() - INTERVAL '24 hours'
                ORDER BY created_at DESC
                LIMIT 5
            """))
            for row in detail.fetchall():
                print(f"    {row[0]} | {row[1]} | {row[2]} | {row[3]}")
    print()


async def check_migration_version() -> None:
    print("=== Migration Status ===")
    async with engine.connect() as conn:
        try:
            result = await conn.execute(text("""
                SELECT version_num FROM alembic_version
            """))
            row = result.first()
            if row:
                print(f"  Current migration: {row[0]}")
            else:
                print("  alembic_version table is empty — no migrations applied")
        except Exception as e:
            print(f"  Could not read alembic_version: {e}")
    print()


async def check_db_size() -> None:
    print("=== Database Size ===")
    async with engine.connect() as conn:
        try:
            result = await conn.execute(text("""
                SELECT pg_size_pretty(pg_database_size(current_database()))
            """))
            size = result.scalar()
            print(f"  Total database size: {size}")
        except Exception as e:
            print(f"  Could not determine database size: {e}")

        try:
            result = await conn.execute(text("""
                SELECT table_name,
                       pg_size_pretty(pg_total_relation_size(table_schema || '.' || table_name)) AS size
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY pg_total_relation_size(table_schema || '.' || table_name) DESC
                LIMIT 10
            """))
            rows = result.fetchall()
            if rows:
                print("  Largest tables:")
                for row in rows:
                    print(f"    {row[0]:30s} {row[1]}")
        except Exception as e:
            print(f"  Could not determine table sizes: {e}")
    print()


async def main() -> None:
    await check_record_counts()
    await check_recent_errors()
    await check_migration_version()
    await check_db_size()


if __name__ == "__main__":
    asyncio.run(main())
