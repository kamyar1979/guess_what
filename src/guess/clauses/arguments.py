from typing import Any

from guess.clauses.conditions import get_conditions
from guess.model import Clause, RawQuery
from guess.values import get_field_names, get_model_type_from_value, get_value


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


def prepare_model_or_positional_arguments(raw_query: RawQuery) -> tuple[Any, ...]:
    if (
        raw_query.clause in (Clause.INSERT, Clause.UPDATE)
        and not raw_query.result_type
        and raw_query.args
        and (raw_query.clause == Clause.UPDATE or len(raw_query.args) == 1)
    ):
        if result_type := get_model_type_from_value(raw_query.args[0]):
            return prepare_model_or_positional_arguments(RawQuery(
                raw_query.clause,
                raw_query.target,
                raw_query.fields,
                raw_query.conditions,
                raw_query.is_list_result,
                raw_query.is_async_func,
                raw_query.args,
                raw_query.kwargs,
                result_type,
            ))

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
    return raw_query.args or ()
