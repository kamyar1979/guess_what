from dataclasses import dataclass
from enum import StrEnum
from typing import Optional, Any


class Clause(StrEnum):
    SELECT = 'SELECT'
    UPDATE = 'UPDATE'
    INSERT = 'INSERT'
    DELETE = 'DELETE'
    CALL = 'CALL'


class Operator(StrEnum):
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    LIKE = "like"
    NOT_LIKE = "not_like"


@dataclass
class RawQuery:
    clause: Clause
    target: str
    fields: Optional[list[str]] = None
    conditions: Optional[list[str]] = None
    is_list_result: bool = False
    is_async_func: bool = False
    args: Optional[tuple[Any,...]] = None
    kwargs: Optional[dict[str, Any]] = None
    result_type: Optional[type] = None
    is_when_condition: bool = False

@dataclass
class DigestedQuery:
    text: str
    args: Optional[tuple[Any,...]] = None
    is_list: bool = False
    is_async: bool = False


clause_mapping = {
    "get": Clause.SELECT,
    "fetch": Clause.SELECT,
    "set": Clause.UPDATE,
    "edit": Clause.UPDATE,
    "change": Clause.UPDATE,
    "modify": Clause.UPDATE,
    "add": Clause.INSERT,
    "create": Clause.INSERT,
    "select": Clause.SELECT,
    "update": Clause.UPDATE,
    "insert": Clause.INSERT,
    "delete": Clause.DELETE,
    "remove": Clause.DELETE,
    "omit": Clause.DELETE,
    "drop": Clause.DELETE,
    "call": Clause.CALL,
    "invoke": Clause.CALL,
}
