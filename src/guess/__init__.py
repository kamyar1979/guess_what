from __future__ import annotations

from typing import Any, Sequence

from .parser import *


class Interceptor:
    def __init__(self, func_name: str, db: Database) -> None:
        self._func_name = func_name
        self.db = db

    def __call__(self, *args):
        if s := create_query(self._func_name):
            return self.db.execute(s, params=args, func_name=self._func_name)
        return None


class Database:
    def __init__(self, connection):
        """
        Accepts ANY DB-API 2.0 connection object.
        Example: sqlite3.connect(...), psycopg2.connect(...), mysql.connector.connect(...)
        """
        self.conn = connection

    def _prepare_query(self, query: str) -> str:
        module_name = type(self.conn).__module__.split(".")[0]
        if module_name == "sqlite3":
            return query.replace("%s", "?")
        return query

    def _expects_many(self, func_name: Optional[str], query: str) -> bool:
        if not query.startswith("SELECT"):
            return False
        if not func_name:
            return True

        match = re.match(r"^(?:get|select)_(?P<table>\w+?)(?:_columns_|_by_|$)", func_name)
        if not match:
            return True
        return match.group("table").endswith("s")

    def execute(
            self,
            query: str,
            params: Optional[Sequence[Any]] = None,
            func_name: Optional[str] = None,
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
            cur.execute(self._prepare_query(query), params or ())

            if query.startswith("SELECT"):
                result = cur.fetchall()
                if self._expects_many(func_name, query):
                    return result
                return result[0] if result else None

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
            params: Optional[Sequence[Any]] = None,
            func_name: Optional[str] = None,
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
            result = await cur.execute(self._prepare_query(query), params or ())

            if query.startswith("SELECT"):
                rows = await cur.fetchall()
                if self._expects_many(func_name, query):
                    return rows
                return rows[0] if rows else None
            return result

    def __getattr__(self, name: str) -> Any:
        database = AsyncDatabase(self.conn)
        return Interceptor(name, database)
