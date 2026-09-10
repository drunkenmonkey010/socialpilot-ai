import asyncio
import asyncpg

from app.core.config import settings


async def main():
    database_url = settings.database_url.replace("+asyncpg", "")

    conn = await asyncpg.connect(database_url)

    rows = await conn.fetch(
        """
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'publications'
        ORDER BY indexname
        """
    )

    for row in rows:
        print(row["indexname"])
        print(row["indexdef"])
        print()

    await conn.close()


asyncio.run(main())
