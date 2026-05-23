"""Soft-delete test data from database."""
import asyncio
import asyncpg
from datetime import datetime


async def main():
    conn = await asyncpg.connect(
        host='localhost',
        user='postgres',
        password='dev_password',
        database='interview_practice',
    )

    now = datetime.utcnow()

    # 1. Soft delete questions (have deleted_at)
    result = await conn.execute(
        "UPDATE questions SET deleted_at = $1, updated_at = $1 WHERE deleted_at IS NULL",
        now,
    )
    print(f"Questions soft-deleted: {result}")

    # 2. Soft delete resumes (have deleted_at)
    result = await conn.execute(
        "UPDATE resumes SET deleted_at = $1, updated_at = $1 WHERE deleted_at IS NULL",
        now,
    )
    print(f"Resumes soft-deleted: {result}")

    # 3. Physical delete study_records (no deleted_at)
    result = await conn.execute("DELETE FROM study_records")
    print(f"Study records physical-deleted: {result}")

    # 4. Physical delete question_tags + tags (no deleted_at)
    result = await conn.execute("DELETE FROM question_tags")
    print(f"Question tags physical-deleted: {result}")
    result = await conn.execute("DELETE FROM tags")
    print(f"Tags physical-deleted: {result}")

    # 5. Verify
    print()
    print("=== After cleanup ===")
    tables = [
        "questions",
        "tags",
        "question_tags",
        "study_records",
        "resumes",
        "resume_experiences",
    ]
    for t in tables:
        count = await conn.fetchval("SELECT count(*) FROM " + t)
        print(f"{t}: {count}")

    await conn.close()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
