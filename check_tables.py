import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://postgres:dev_password@localhost:5432/interview_practice')
    tables = await conn.fetch("""
        SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
    """)
    print('Tables in interview_practice:')
    for t in tables:
        print(f'  - {t["tablename"]}')
    
    # Check alembic_version
    ver = await conn.fetchval('SELECT version_num FROM alembic_version;')
    print(f'\nAlembic version: {ver}')
    
    await conn.close()

asyncio.run(main())
