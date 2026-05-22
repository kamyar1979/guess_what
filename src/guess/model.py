from dataclasses import dataclass
from enum import StrEnum
from typing import Optional


class Clause(StrEnum):
    SELECT = 'SELECT'
    UPDATE = 'UPDATE'
    INSERT = 'INSERT'
    DELETE = 'DELETE'


@dataclass
class Query:
    clause: Clause
    table: str
    fields: Optional[list[str]] = None
    conditions: Optional[list[str]] = None
    is_list_result: bool = False
    is_async_func: bool = False

@dataclass
class DigestedQuery:
    text: str
    is_list: bool
    is_async: bool


clause_mapping = {
    "get": Clause.SELECT,
    "set": Clause.UPDATE,
    "edit": Clause.UPDATE,
    "add": Clause.INSERT,
    "select": Clause.SELECT,
    "update": Clause.UPDATE,
    "insert": Clause.INSERT,
    "delete": Clause.DELETE,
    "remove": Clause.DELETE,
}
