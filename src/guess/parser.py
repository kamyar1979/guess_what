import re
from dataclasses import is_dataclass, fields
from typing import Optional, Any

import inflection

from guess.model import Clause, clause_mapping, RawQuery, DigestedQuery

clause_handlers = {}
PRIMARY_KEY_PATTERN = r"^(id|{entity}_id)$"


def register_clause(clause: Clause):
    def decorate(func):
        clause_handlers[clause] = func
        return func

    return decorate


FUNC_NAME_PATTERN = rf"""
^
(?P<async>async_)?
(?P<clause>{'|'.join(clause_mapping.keys())})
_
(?P<target>\w+?)

(?:_columns_(?P<fields>(?:(?!_by_)\w)+))?
(?:_by_(?P<conditions>\w+?))?
$
"""

regex = re.compile(FUNC_NAME_PATTERN, re.VERBOSE)


def get_field_names(model) -> list[str]:
    if model == dict:
        raise TypeError("dict field names must come from a value")

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

    raise TypeError(f"Unsupported type: {cls.__name__}")


def get_value(obj: Any, field_name: str) -> Any:
    if isinstance(obj, dict):
        return obj[field_name]
    return getattr(obj, field_name)


def split_model_kwargs(raw_query: RawQuery) -> tuple[Any | None, type | None, dict[str, Any]]:
    kwargs = dict(raw_query.kwargs or {})
    name = inflection.singularize(raw_query.target)
    if name in kwargs:
        obj = kwargs.pop(name)
        result_type = raw_query.result_type or (dict if isinstance(obj, dict) else type(obj))
        return obj, result_type, kwargs
    return None, raw_query.result_type, kwargs


def prepare_kwargs(raw_query: RawQuery, names: tuple[str, ...], *, reject_duplicates: bool = False) -> tuple[Any, ...]:
    if raw_query.args and raw_query.kwargs:
        raise ValueError("You can not use positional and named arguments at the same time here!")

    if not raw_query.kwargs:
        return raw_query.args or ()

    if reject_duplicates:
        duplicate_names = set(raw_query.fields or []) & set(raw_query.conditions or [])
        if duplicate_names:
            raise ValueError(f"Keyword arguments are ambiguous for duplicate names: {','.join(sorted(duplicate_names))}")

    if not names:
        raise ValueError("Keyword arguments require fields or conditions")

    missing = [k for k in names if k not in raw_query.kwargs]
    if missing:
        raise ValueError(f"Missing keyword arguments: {','.join(missing)}")

    unknown = [k for k in raw_query.kwargs if k not in names]
    if unknown:
        raise ValueError(f"Unknown keyword arguments: {','.join(unknown)}")

    return tuple(raw_query.kwargs[k] for k in names)


def get_pk_field(raw_query: RawQuery) -> str | None:
    if not raw_query.result_type or raw_query.result_type == dict:
        return "id"

    entity = inflection.singularize(raw_query.target)
    field_names = get_field_names(raw_query.result_type)
    pk_pattern = re.compile(PRIMARY_KEY_PATTERN.format(entity=re.escape(entity)))

    for field_name in field_names:
        if pk_pattern.match(field_name):
            return field_name
    return None


def get_primary_key_condition(raw_query: RawQuery) -> tuple[str, ...]:
    if (
        raw_query.clause != Clause.SELECT
        or raw_query.is_list_result
        or raw_query.kwargs
        or raw_query.conditions
        or len(raw_query.args or ()) != 1
    ):
        return ()

    pk_field = get_pk_field(raw_query)
    if not pk_field:
        raise ValueError("Could not infer primary key field for single-argument SELECT")
    return (pk_field,)


def get_conditions(raw_query: RawQuery) -> tuple[str, ...]:
    if raw_query.conditions:
        return tuple(raw_query.conditions)
    if raw_query.clause in (Clause.SELECT, Clause.DELETE) and raw_query.kwargs:
        return tuple(raw_query.kwargs.keys())
    return get_primary_key_condition(raw_query)


def parse_function_to_query(func_name: str, result_type: Optional[type] = None, *args, **kwargs) -> Optional[RawQuery]:
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
                        kwargs,
                        result_type
                        )
    return None


def prepare_arguments(raw_query: RawQuery) -> tuple[Any, ...]:
    if raw_query.clause == Clause.SELECT:
        return prepare_kwargs(raw_query, get_conditions(raw_query), reject_duplicates=True)

    if raw_query.clause == Clause.DELETE:
        return prepare_kwargs(raw_query, get_conditions(raw_query), reject_duplicates=True)

    if raw_query.clause == Clause.UPDATE and raw_query.kwargs:
        obj, result_type, remaining_kwargs = split_model_kwargs(raw_query)
        condition_names = get_conditions(raw_query)
        if not result_type:
            names = tuple(raw_query.fields or ()) + condition_names
            return prepare_kwargs(raw_query, names, reject_duplicates=True)

        if obj is None and len(raw_query.args or []) > 1:
            raise ValueError("When using named arguments with typed values, the values object can be the only positional argument.")
        if obj is not None and raw_query.args:
            raise ValueError("You can not provide typed values both positionally and by keyword.")

        duplicate_names = set(raw_query.fields or []) & set(condition_names)
        if duplicate_names:
            raise ValueError(f"Keyword arguments are ambiguous for duplicate names: {','.join(sorted(duplicate_names))}")

        obj_args = prepare_arguments(RawQuery(
            raw_query.clause,
            raw_query.target,
            raw_query.fields,
            None,
            raw_query.is_list_result,
            raw_query.is_async_func,
            (obj,) if obj is not None else raw_query.args,
            None,
            result_type,
        ))
        condition_args = prepare_kwargs(RawQuery(
            raw_query.clause,
            raw_query.target,
            None,
            raw_query.conditions,
            raw_query.is_list_result,
            raw_query.is_async_func,
            None,
            remaining_kwargs,
            None,
        ), condition_names)
        return obj_args + condition_args

    if raw_query.clause == Clause.INSERT and raw_query.kwargs:
        obj, result_type, remaining_kwargs = split_model_kwargs(raw_query)
        if obj is not None:
            if remaining_kwargs:
                raise ValueError(f"Unknown keyword arguments: {','.join(remaining_kwargs)}")
            return prepare_arguments(RawQuery(
                raw_query.clause,
                raw_query.target,
                raw_query.fields,
                raw_query.conditions,
                raw_query.is_list_result,
                raw_query.is_async_func,
                (obj,),
                None,
                result_type,
            ))
        if raw_query.result_type:
            raise ValueError("Keyword arguments are not supported with typed insert values")
        names = tuple(raw_query.fields) if raw_query.fields else tuple(raw_query.kwargs.keys())
        return prepare_kwargs(raw_query, names)

    if raw_query.result_type:
        obj = raw_query.args[0]
        if raw_query.fields:
            args = [get_value(obj, k) for k in raw_query.fields]
        elif raw_query.result_type == dict:
            args = list(obj.values())
        else:
            args = [get_value(obj, k) for k in get_field_names(raw_query.result_type)]
        condition_names = get_conditions(raw_query)
        if raw_query.clause == Clause.UPDATE and condition_names:
            args += raw_query.args[-len(condition_names):]
        return tuple(args)
    else:
        return raw_query.args or ()


@register_clause(Clause.SELECT)
def create_select_query(raw_query: RawQuery) -> DigestedQuery:
    condition_fields = get_conditions(raw_query)
    conditions = f" WHERE {' AND '.join(f'{f} = %s' for f in condition_fields)}" if condition_fields else ""
    fields_str = ",".join(raw_query.fields) if raw_query.fields else "*"
    query_text = f"SELECT {fields_str} FROM {raw_query.target}{conditions}"
    return DigestedQuery(query_text, prepare_arguments(raw_query), raw_query.is_list_result, raw_query.is_async_func)


@register_clause(Clause.UPDATE)
def create_update_query(raw_query: RawQuery) -> DigestedQuery:
    if not raw_query.fields:
        raise ValueError("UPDATE queries require columns")

    condition_fields = get_conditions(raw_query)
    conditions = f" WHERE {' AND '.join(f'{f} = %s' for f in condition_fields)}" if condition_fields else ""
    set_clause = ",".join(f"{f} = %s" for f in (raw_query.fields or []))
    query_text = f"UPDATE {raw_query.target} SET {set_clause}{conditions}"
    return DigestedQuery(query_text, prepare_arguments(raw_query), raw_query.is_list_result, raw_query.is_async_func)


@register_clause(Clause.INSERT)
def create_insert_query(raw_query: RawQuery) -> DigestedQuery:
    insert_fields = raw_query.fields
    model_obj, model_type, remaining_kwargs = split_model_kwargs(raw_query)
    if not insert_fields and raw_query.result_type:
        if raw_query.result_type == dict:
            insert_fields = list((model_obj or raw_query.args[0]).keys())
        else:
            insert_fields = get_field_names(raw_query.result_type)
    if not insert_fields and model_obj is not None:
        if model_type == dict:
            insert_fields = list(model_obj.keys())
        else:
            insert_fields = get_field_names(model_type)
    if not insert_fields and raw_query.kwargs:
        insert_fields = list(remaining_kwargs.keys())

    args = prepare_arguments(raw_query)
    if not insert_fields and not args:
        raise ValueError("INSERT queries require columns or values")

    columns = f"( {','.join(insert_fields)} ) " if insert_fields else ""
    value_count = len(insert_fields) if insert_fields else len(args)
    query_text = f"INSERT INTO {raw_query.target} {columns}VALUES ({','.join('%s' for _ in range(value_count))})"
    return DigestedQuery(query_text, args, raw_query.is_list_result, raw_query.is_async_func)


@register_clause(Clause.DELETE)
def create_delete_query(raw_query: RawQuery) -> DigestedQuery:
    condition_fields = get_conditions(raw_query)
    conditions = f" WHERE {' AND '.join(f'{f} = %s' for f in condition_fields)}" if condition_fields else ""
    query_text = f"DELETE FROM {raw_query.target}{conditions}"
    return DigestedQuery(query_text, prepare_arguments(raw_query), raw_query.is_list_result, raw_query.is_async_func)


@register_clause(Clause.CALL)
def create_call_query(raw_query: RawQuery) -> DigestedQuery:
    query_text = f"{raw_query.target}({','.join('%s' for _ in raw_query.args or [])})"
    return DigestedQuery(query_text, raw_query.args, raw_query.is_list_result, raw_query.is_async_func)


def create_query(func_name: str, result_type: Optional[type] = None, *args, **kwargs) -> Optional[DigestedQuery]:
    if q := parse_function_to_query(func_name, result_type, *args, **kwargs):
        return clause_handlers[q.clause](q)
    return None
