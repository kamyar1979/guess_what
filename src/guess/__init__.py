from __future__ import annotations

from typing import Any, Sequence

from .parser import *


class Interceptor:
    def __init__(self, func_name: str, db: Database) -> None:
        self._func_name = func_name.lower()
        self.db = db

    def __call__(self, *args):
        if query := create_query(self._func_name):
            return self.db.execute(query.text, params=args, is_list=query.is_list,
                                   is_async=query.is_async or self.db.is_async)
        return None


class Database:
    def __init__(self, connection, is_async: bool = False):
        """
        Accepts ANY DB-API 2.0 connection object.
        Example: sqlite3.connect(...), psycopg2.connect(...), mysql.connector.connect(...)
        """
        self.conn = connection
        self.is_async = is_async

    def _prepare_query(self, query: str) -> str:
        module_name = type(self.conn).__module__.split(".")[0]
        if module_name == "sqlite3":
            return query.replace("%s", "?")
        return query

    def __getattr__(self, name: str) -> Any:
        database = Database(self.conn, is_async=self.is_async)
        return Interceptor(name, database)

    def execute(
            self,
            query: str,
            params: Optional[Sequence[Any]] = None,
            is_list: bool = False,
            is_async: bool = False,
    ):
        if is_async or self.is_async:
            return self.execute_async(query, params, is_list)

        cur = self.conn.cursor()
        try:
            cur.execute(self._prepare_query(query), params or ())

            if query.startswith("SELECT"):
                result = cur.fetchall()
                if is_list:
                    return result
                return result[0] if result else None

            self.conn.commit()
        finally:
            cur.close()

    async def execute_async(
            self,
            query: str,
            params: Optional[Sequence[Any]] = None,
            is_list: bool = False,
    ):
        async with self.conn.cursor() as cur:
            result = await cur.execute(self._prepare_query(query), params or ())

            if query.startswith("SELECT"):
                rows = await cur.fetchall()
                if is_list:
                    return rows
                return rows[0] if rows else None
            return result
