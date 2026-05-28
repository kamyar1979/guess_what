import re
from dataclasses import is_dataclass, fields
from typing import Optional, Any

import inflection

from guess.model import Clause, clause_mapping, RawQuery, DigestedQuery

clause_handlers = {}


def register_clause(clause: Clause):
    def decorate(func):
        clause_handlers[clause] = func
        return func

    return decorate


pattern = rf"""
^
(?P<async>async_)?
(?P<clause>{'|'.join(clause_mapping.keys())})
_
(?P<target>\w+?)

(?:_columns_(?P<fields>(?:(?!_by_)\w)+))?
(?:_by_(?P<conditions>\w+?))?
$
"""

regex = re.compile(pattern, re.VERBOSE)


def get_field_names(model) -> list[str]:
    # Accept both class and instance
    cls = model if isinstance(model, type) else type(model)

    # dataclass
    if is_dataclass(cls):
        return [f.name for f in fields(cls)]

    # Pydantic v2
    if hasattr(cls, "model_fields"):
        return list(cls.model_fields.keys())

    # Pydantic v1
    if hasattr(cls, "__fields__"):
        return list(cls.__fields__.keys())

    raise TypeError(f"Unsupported type: {cls}")


def parse_func_name(func_name: str, result_type: Optional[type] = None, *args) -> Optional[RawQuery]:
    if m := regex.match(func_name):
        clause = clause_mapping[m.group("clause")]
        target = m.group("target") if clause == Clause.CALL else inflection.pluralize(m.group("target"))
        return RawQuery(clause,
                        target,
                        m.group("fields").split('_and_') if m.group("fields") else None,
                        m.group("conditions").split('_and_') if m.group("conditions") else None,
                        clause != Clause.CALL and inflection.pluralize(m.group("target")) == m.group("target"),
                        m.group("async") == "async_",
                        args,
                        result_type
                        )
    return None


def prepare_arguments(raw_query: RawQuery) -> tuple[Any, ...]:
    if raw_query.result_type:
        obj = raw_query.args[0]
        if raw_query.fields:
            args = [getattr(obj, k) for k in raw_query.fields]
        else:
            args = [getattr(obj, k) for k in get_field_names(raw_query.result_type)]
        if raw_query.clause == Clause.UPDATE and raw_query.conditions:
            args += raw_query.args[-len(raw_query.conditions):]
        return tuple(args)
    else:
        return raw_query.args or ()


@register_clause(Clause.SELECT)
def create_select_query(raw_query: RawQuery) -> DigestedQuery:
    conditions = f" WHERE {' AND '.join(f'{f} = %s' for f in raw_query.conditions)}" if raw_query.conditions else ""
    fields_str = ",".join(raw_query.fields) if raw_query.fields else "*"
    query_text = f"SELECT {fields_str} FROM {raw_query.target}{conditions}"
    return DigestedQuery(query_text, raw_query.args, raw_query.is_list_result, raw_query.is_async_func)


@register_clause(Clause.UPDATE)
def create_update_query(raw_query: RawQuery) -> DigestedQuery:
    if not raw_query.fields:
        raise ValueError("UPDATE queries require columns")

    conditions = f" WHERE {' AND '.join(f'{f} = %s' for f in raw_query.conditions)}" if raw_query.conditions else ""
    set_clause = ",".join(f"{f} = %s" for f in (raw_query.fields or []))
    query_text = f"UPDATE {raw_query.target} SET {set_clause}{conditions}"
    return DigestedQuery(query_text, prepare_arguments(raw_query), raw_query.is_list_result, raw_query.is_async_func)


@register_clause(Clause.INSERT)
def create_insert_query(raw_query: RawQuery) -> DigestedQuery:
    insert_fields = raw_query.fields
    if not insert_fields and raw_query.result_type:
        insert_fields = get_field_names(raw_query.result_type)

    args = prepare_arguments(raw_query)
    if not insert_fields and not args:
        raise ValueError("INSERT queries require columns or values")

    columns = f"( {','.join(insert_fields)} ) " if insert_fields else ""
    value_count = len(insert_fields) if insert_fields else len(args)
    query_text = f"INSERT INTO {raw_query.target} {columns}VALUES ({','.join('%s' for _ in range(value_count))})"
    return DigestedQuery(query_text, args, raw_query.is_list_result, raw_query.is_async_func)


@register_clause(Clause.DELETE)
def create_delete_query(raw_query: RawQuery) -> DigestedQuery:
    conditions = f" WHERE {' AND '.join(f'{f} = %s' for f in raw_query.conditions)}" if raw_query.conditions else ""
    query_text = f"DELETE FROM {raw_query.target}{conditions}"
    return DigestedQuery(query_text, raw_query.args, raw_query.is_list_result, raw_query.is_async_func)


@register_clause(Clause.CALL)
def create_call_query(raw_query: RawQuery) -> DigestedQuery:
    query_text = f"{raw_query.target}({','.join('%s' for _ in raw_query.args or [])})"
    return DigestedQuery(query_text, raw_query.args, raw_query.is_list_result, raw_query.is_async_func)


def create_query(func_name: str, result_type: Optional[type] = None, *args) -> Optional[DigestedQuery]:
    if q := parse_func_name(func_name, result_type, *args):
        return clause_handlers[q.clause](q)
    return None
