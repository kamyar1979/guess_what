import re
from typing import Any

import inflection

from guess.model import Clause, Operator, RawQuery
from guess.values import get_field_names


PRIMARY_KEY_PATTERN = r"^(id|{entity}_id)$"
operator_mapping = {
    Operator.EQUAL: "=",
    Operator.NOT_EQUAL: "<>",
    Operator.GREATER_THAN: ">",
    Operator.GREATER_THAN_OR_EQUAL: ">=",
    Operator.LESS_THAN: "<",
    Operator.LESS_THAN_OR_EQUAL: "<=",
    Operator.LIKE: "LIKE",
    Operator.NOT_LIKE: "NOT LIKE",
    Operator.IN: "IN",
}


def parse_named_argument_to_condition(name: str) -> tuple[str, Operator]:
    for operator in sorted(Operator, key=lambda item: len(item.value), reverse=True):
        suffix = f"_{operator.value}"
        if name.endswith(suffix):
            field_name = name[:-len(suffix)]
            if not field_name:
                raise ValueError(f"Missing field name for operator: {operator.value}")
            return field_name, operator
    return name, Operator.EQUAL


def get_in_values(name: str, value: Any) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"IN operator requires a non-empty list or tuple: {name}")
    if not value:
        raise ValueError(f"IN operator requires a non-empty list or tuple: {name}")
    return tuple(value)


def create_named_argument_condition(name: str, value: Any) -> str:
    field_name, operator = parse_named_argument_to_condition(name)
    if operator == Operator.IN:
        placeholders = ",".join("%s" for _ in get_in_values(name, value))
        return f"{field_name} IN ({placeholders})"
    return f"{field_name} {operator_mapping[operator]} %s"


def prepare_named_argument_values(name: str, value: Any) -> tuple[Any, ...]:
    _, operator = parse_named_argument_to_condition(name)
    if operator == Operator.IN:
        return get_in_values(name, value)
    return (value,)


def prepare_named_arguments_values(named_arguments: dict[str, Any]) -> tuple[Any, ...]:
    values = []
    for name, value in named_arguments.items():
        values.extend(prepare_named_argument_values(name, value))
    return tuple(values)


def parse_named_arguments_to_where_clause(named_arguments: dict[str, Any]) -> str:
    if not named_arguments:
        return ""

    conditions = []
    for name, value in named_arguments.items():
        conditions.append(create_named_argument_condition(name, value))
    return f" WHERE {' AND '.join(conditions)}"


def prepare_named_condition_arguments(raw_query: RawQuery) -> tuple[Any, ...]:
    if raw_query.args and raw_query.kwargs:
        raise ValueError("You can not use positional and named arguments at the same time here!")
    if raw_query.args:
        raise ValueError("When clauses require named arguments")
    if not raw_query.kwargs:
        raise ValueError("Empty when clause requires named arguments")
    return prepare_named_arguments_values(raw_query.kwargs)


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
    if raw_query.conditions is not None and len(raw_query.conditions) > 0:
        return tuple(raw_query.conditions)
    if raw_query.clause in (Clause.SELECT, Clause.DELETE) and raw_query.kwargs:
        return tuple(raw_query.kwargs.keys())
    if raw_query.clause in (Clause.SELECT, Clause.DELETE) and raw_query.conditions == ():
        raise ValueError("Empty by clause requires keyword arguments")
    return get_primary_key_condition(raw_query)


def create_condition_clause(raw_query: RawQuery) -> str:
    if raw_query.is_when_condition:
        return parse_named_arguments_to_where_clause(raw_query.kwargs or {})

    condition_fields = get_conditions(raw_query)
    return f" WHERE {' AND '.join(f'{field} = %s' for field in condition_fields)}" if condition_fields else ""


def get_named_argument_cache_shape(name: str, value: Any) -> tuple[str, int | None]:
    if parse_named_argument_to_condition(name)[1] != Operator.IN:
        return name, None
    if not isinstance(value, (list, tuple)):
        return name, None
    return name, len(value)
