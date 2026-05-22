import re
from typing import Optional

import inflection

from guess.model import Clause, clause_mapping, Query

clause_handlers = {}

def register_clause(clause: Clause):
    def decorate(func):
        clause_handlers[clause] = func
        return func

    return decorate


PATTERN = rf"^(?P<clause>{'|'.join(clause_mapping.keys())})_(?P<table>\w+?)(?:_columns_(?P<fields>[^by]+(?:_and_\w+)*))?(?:(?:_by)_(?P<conditions>\w+)?(?:_and_\w+)*)?$"


def parse_func_name(func_name: str) -> Optional[Query]:
    if m := re.match(PATTERN, func_name):
        return Query(clause_mapping[m.group("clause")],
                     inflection.pluralize(m.group("table")),
                     m.group("fields").split('_and_') if m.group("fields") else None,
                     m.group("conditions").split('_and_') if m.group("conditions") else None,
                     )
    return None


@register_clause(Clause.SELECT)
def create_select_query(parts: Query) -> str:
    if parts.conditions:
        conditions = f"WHERE {" AND ".join(f"{f} = %s" for f in parts.conditions)}"
    else:
        conditions = ""

    return f"SELECT {','.join(parts.fields or ["*"]) or '*'} FROM {parts.table} {conditions}"


@register_clause(Clause.UPDATE)
def create_update_query(parts: Query) -> str:
    if parts.conditions:
        conditions = f"WHERE {" AND ".join(f"{f} = %s" for f in parts.conditions)}"
    else:
        conditions = ""

    return f"UPDATE {parts.table} SET {','.join(f"{f} = %s" for f in parts.fields or [])} {conditions}"


@register_clause(Clause.INSERT)
def create_insert_query(parts: Query) -> str:
    if parts.fields:
        fields = f"( {','.join(parts.fields)} )"
    else:
        fields = ""

    return f"INSERT INTO {parts.table} {fields} VALUES ({','.join('%s' for _ in parts.fields or [])})"


@register_clause(Clause.DELETE)
def create_delete_query(parts: Query) -> str:
    if parts.conditions:
        conditions = f"WHERE {" AND ".join(f"{f} = %s" for f in parts.conditions)}"
    else:
        conditions = ""

    return f"DELETE FROM {parts.table} {conditions}"


def create_query(func_name: str) -> Optional[str]:
    if q := parse_func_name(func_name):
        return clause_handlers[q.clause](q)
    return None
