from typing import Any

from guess.clauses.arguments import prepare_kwargs, prepare_model_or_positional_arguments
from guess.clauses.conditions import (
    create_condition_clause,
    get_conditions,
    parse_named_arguments_to_where_clause,
    prepare_named_arguments_values,
)
from guess.model import DigestedQuery, RawQuery
from guess.values import get_model_type_from_value, split_model_kwargs


def get_update_named_condition_arguments(raw_query: RawQuery) -> dict[str, Any]:
    kwargs = dict(raw_query.kwargs or {})
    obj, result_type, remaining_kwargs = split_model_kwargs(raw_query)
    positional_result_type = None

    if obj is None and raw_query.args:
        positional_result_type = raw_query.result_type or get_model_type_from_value(raw_query.args[0])

    uses_values_object = obj is not None or positional_result_type is not None
    if uses_values_object:
        condition_arguments = remaining_kwargs
    else:
        field_names = set(raw_query.fields or [])
        condition_arguments = {name: value for name, value in kwargs.items() if name not in field_names}

    if not condition_arguments:
        raise ValueError("Empty when clause requires named condition arguments")
    return condition_arguments


def prepare_update_when_arguments(raw_query: RawQuery) -> tuple[Any, ...]:
    if not raw_query.kwargs:
        raise ValueError("Empty when clause requires named condition arguments")

    obj, result_type, remaining_kwargs = split_model_kwargs(raw_query)
    condition_arguments = get_update_named_condition_arguments(raw_query)

    if obj is not None:
        if raw_query.args:
            raise ValueError("You can not provide typed values both positionally and by keyword.")
        field_args = prepare_model_or_positional_arguments(RawQuery(
            raw_query.clause,
            raw_query.target,
            raw_query.fields,
            None,
            raw_query.is_list_result,
            raw_query.is_async_func,
            (obj,),
            None,
            result_type,
        ))
    elif raw_query.args:
        if len(raw_query.args) > 1:
            raise ValueError("When clauses support only one positional values object.")
        result_type = raw_query.result_type or get_model_type_from_value(raw_query.args[0])
        if not result_type:
            raise ValueError("When clauses require named field values or a typed values object.")
        field_args = prepare_model_or_positional_arguments(RawQuery(
            raw_query.clause,
            raw_query.target,
            raw_query.fields,
            None,
            raw_query.is_list_result,
            raw_query.is_async_func,
            raw_query.args,
            None,
            result_type,
        ))
    else:
        field_names = tuple(raw_query.fields or ())
        missing = [name for name in field_names if name not in remaining_kwargs]
        if missing:
            raise ValueError(f"Missing keyword arguments: {','.join(missing)}")
        field_args = tuple(remaining_kwargs[name] for name in field_names)

    return field_args + prepare_named_arguments_values(condition_arguments)


def create_update_condition_clause(raw_query: RawQuery) -> str:
    if raw_query.is_when_condition:
        return parse_named_arguments_to_where_clause(get_update_named_condition_arguments(raw_query))
    return create_condition_clause(raw_query)


def prepare_update_arguments(raw_query: RawQuery) -> tuple[Any, ...]:
    if raw_query.is_when_condition:
        return prepare_update_when_arguments(raw_query)

    if raw_query.kwargs:
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

        obj_args = prepare_model_or_positional_arguments(RawQuery(
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

    return prepare_model_or_positional_arguments(raw_query)


def create_update_query(raw_query: RawQuery) -> DigestedQuery:
    if not raw_query.fields:
        raise ValueError("UPDATE queries require columns")

    conditions = create_update_condition_clause(raw_query)
    set_clause = ",".join(f"{field} = %s" for field in (raw_query.fields or []))
    query_text = f"UPDATE {raw_query.target} SET {set_clause}{conditions}"
    return DigestedQuery(query_text, prepare_update_arguments(raw_query), raw_query.is_list_result, raw_query.is_async_func)
