import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://postgres:dev_password@localhost:5432/postgres')
    dbs = await conn.fetch('SELECT datname FROM pg_database WHERE datistemplate = false;')
    print('Databases on localhost:5432:')
    for db in dbs:
        print(f'  - {db["datname"]}')
    await conn.close()

asyncio.run(main())
