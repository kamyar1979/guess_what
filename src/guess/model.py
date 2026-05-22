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
