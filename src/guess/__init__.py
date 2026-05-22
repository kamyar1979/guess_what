from __future__ import annotations

from typing import Any, Sequence, Optional

from .parser import *


class Interceptor:
    def __init__(self, func_name: str, db: Database) -> None:
        self._func_name = func_name
        self.db = db

    def __call__(self, *args):
        if s := create_query(self._func_name):
            return self.db.execute(s, params=args)
        return None


class Database:
    def __init__(self, connection):
        """
        Accepts ANY DB-API 2.0 connection object.
        Example: sqlite3.connect(...), psycopg2.connect(...), mysql.connector.connect(...)
        """
        self.conn = connection

    def execute(
            self,
            query: str,
            params: Optional[Sequence[Any]] = None,
    ):
        """
        Generic DB-API query executor.
        - query: SQL string with placeholders (driver-specific style)
        - params: parameters for single execution
        - fetch: whether to return rows
        - many: whether to use executemany()
        - batch: iterable of parameter sequences for executemany()
        """
        cur = self.conn.cursor()
        try:
            cur.execute(query, params or ())

            if query.startswith("SELECT"):
                result = cur.fetchall()
                if len(result) == 1:
                    return result[0]
                else:
                    return result

            self.conn.commit()
        finally:
            cur.close()

    def __getattr__(self, name: str) -> Any:
        database = Database(self.conn)
        return Interceptor(name, database)


class AsyncDatabase(Database):

    async def execute(
            self,
            query: str,
            params: Optional[Sequence[Any]] = None
    ):
        """
        Generic async query executor.
        - query: SQL string with placeholders (driver-specific)
        - params: parameters for single execution
        - fetch: return rows
        - many: use executemany()
        - batch: iterable of parameter sequences
        """
        async with self.conn.cursor() as cur:
            result = await cur.execute(query, params or ())

            if query.startswith("SELECT"):
                result = await cur.fetchall()
                if len(result) == 1:
                    return result[0]
                else:
                    return result
            else:
                return result

    def __getattr__(self, name: str) -> Any:
        database = AsyncDatabase(self.conn)
        return Interceptor(name, database)
