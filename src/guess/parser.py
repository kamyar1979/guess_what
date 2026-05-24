import re
from typing import Optional

import inflection

from guess.model import Clause, clause_mapping, Query, DigestedQuery

clause_handlers = {}


def register_clause(clause: Clause):
    def decorate(func):
        clause_handlers[clause] = func
        return func

    return decorate


PATTERN = rf"^(?P<async>async_)?(?P<clause>{'|'.join(clause_mapping.keys())})_(?P<table>\w+?)(?:_columns_(?P<fields>(?:(?!_by_)\w)+))?(?:_by_(?P<conditions>\w+?))?$"


def parse_func_name(func_name: str) -> Optional[Query]:
    if m := re.match(PATTERN, func_name):
        return Query(clause_mapping[m.group("clause")],
                     inflection.pluralize(m.group("table")),
                     m.group("fields").split('_and_') if m.group("fields") else None,
                     m.group("conditions").split('_and_') if m.group("conditions") else None,
                     inflection.pluralize(m.group("table")) == m.group("table"),
                     m.group("async") == "async_"
                     )
    return None


@register_clause(Clause.SELECT)
def create_select_query(parts: Query) -> str:
    conditions = f" WHERE {' AND '.join(f'{f} = %s' for f in parts.conditions)}" if parts.conditions else ""
    fields_str = ",".join(parts.fields) if parts.fields else "*"
    return f"SELECT {fields_str} FROM {parts.table}{conditions}"


@register_clause(Clause.UPDATE)
def create_update_query(parts: Query) -> str:
    if not parts.fields:
        raise ValueError("UPDATE queries require columns")

    conditions = f" WHERE {' AND '.join(f'{f} = %s' for f in parts.conditions)}" if parts.conditions else ""
    set_clause = ",".join(f"{f} = %s" for f in (parts.fields or []))
    return f"UPDATE {parts.table} SET {set_clause}{conditions}"


@register_clause(Clause.INSERT)
def create_insert_query(parts: Query) -> str:
    if not parts.fields:
        raise ValueError("INSERT queries require columns")

    if parts.fields:
        fields = f"( {','.join(parts.fields)} )"
    else:
        fields = ""

    return f"INSERT INTO {parts.table} {fields} VALUES ({','.join('%s' for _ in parts.fields or [])})"


@register_clause(Clause.DELETE)
def create_delete_query(parts: Query) -> str:
    conditions = f" WHERE {' AND '.join(f'{f} = %s' for f in parts.conditions)}" if parts.conditions else ""
    return f"DELETE FROM {parts.table}{conditions}"


def create_query(func_name: str) -> Optional[DigestedQuery]:
    if q := parse_func_name(func_name):
        return DigestedQuery(clause_handlers[q.clause](q), q.is_list_result, q.is_async_func)
    return None
