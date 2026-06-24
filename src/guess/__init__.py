from __future__ import annotations

import inspect
from typing import Any, Sequence

from .parser import create_query
from .values import get_field_names


class Interceptor:
    def __init__(self, func_name: str, db: Database) -> None:
        self._func_name = func_name.lower()
        self.db = db
        self.result_type = None

    def __getitem__(self, item):
        self.result_type = item
        return self

    def __call__(self, *args, **kwargs):
        if query := create_query(self._func_name, self.result_type, *args, **kwargs):
            return self.db.execute(query.text, params=query.args, is_list=query.is_list,
                                   is_async=query.is_async or self.db.is_async, result_type=self.result_type)
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

    @staticmethod
    def prepare_result(result: list[dict | tuple],
                       result_type: Optional[type],
                       columns: list[str],
                       is_list: bool):
        rows = [
            dict(zip(columns, row))
            for row in result
        ]

        if is_list:
            if result_type is None:
                return result
            elif result_type == dict:
                return rows
            else:
                field_names = get_field_names(result_type)
                return [
                    result_type(**dict((k, v) for k, v in row.items() if k in field_names))
                    for row in rows
                ]
        if result_type is None:
            return result[0] if result else None
        if not rows:
            return None
        if result_type == dict:
            return rows[0]
        else:
            field_names = get_field_names(result_type)
            return result_type(**dict((k, v) for k, v in rows[0].items() if k in field_names))

    def execute(
            self,
            query: str,
            params: Optional[Sequence[Any]] = None,
            is_list: bool = False,
            is_async: bool = False,
            result_type: Optional[type] = None,
    ):
        if is_async or self.is_async:
            return self.execute_async(query, params, is_list, result_type)

        cur = self.conn.cursor()
        try:
            cur.execute(self._prepare_query(query), params or ())

            if query.startswith("SELECT"):
                columns = [col[0] for col in cur.description]

                result = cur.fetchall()
                if query.startswith("SELECT COUNT("):
                    return result[0][0] if result else 0
                return self.prepare_result(result, result_type, columns, is_list)

            self.conn.commit()
        finally:
            cur.close()

    async def execute_async(
            self,
            query: str,
            params: Optional[Sequence[Any]] = None,
            is_list: bool = False,
            result_type: Optional[type] = None,
    ):
        async with self.conn.cursor() as cur:
            execute_result = await cur.execute(self._prepare_query(query), params or ())

            if query.startswith("SELECT"):
                columns = [col[0] for col in cur.description]

                result = await cur.fetchall()
                if query.startswith("SELECT COUNT("):
                    return result[0][0] if result else 0
                return self.prepare_result(result, result_type, columns, is_list)

            await self._commit_async()
            return execute_result

    async def _commit_async(self) -> None:
        commit = getattr(self.conn, "commit", None)
        if commit is None:
            return

        result = commit()
        if inspect.isawaitable(result):
            await result
