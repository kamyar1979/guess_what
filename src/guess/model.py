from dataclasses import dataclass
from enum import StrEnum
from typing import Optional, Any


class Clause(StrEnum):
    SELECT = 'SELECT'
    UPDATE = 'UPDATE'
    INSERT = 'INSERT'
    DELETE = 'DELETE'
    CALL = 'CALL'


@dataclass
class RawQuery:
    clause: Clause
    target: str
    fields: Optional[list[str]] = None
    conditions: Optional[list[str]] = None
    is_list_result: bool = False
    is_async_func: bool = False
    args: Optional[tuple[Any,...]] = None
    result_type: Optional[type] = None

@dataclass
class DigestedQuery:
    text: str
    args: Optional[tuple[Any,...]] = None
    is_list: bool = False
    is_async: bool = False


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
    "call": Clause.CALL,
}
