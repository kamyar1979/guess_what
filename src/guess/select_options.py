import re
from typing import Any

from guess.model import Clause, RawQuery


IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?$")
DESC_SORT_SUFFIXES = ("_desc", "_reverse")
SELECT_SORT_ARGUMENTS = ("order_by", "sort_by")
SELECT_ORDER_ARGUMENTS = set(SELECT_SORT_ARGUMENTS) | {
    f"{name}{suffix}"
    for name in SELECT_SORT_ARGUMENTS
    for suffix in DESC_SORT_SUFFIXES
}
SELECT_PAGINATION_ARGUMENTS = {"from", "from_", "to", "offset", "limit", "page", "page_size"}
SELECT_OPTION_ARGUMENTS = SELECT_ORDER_ARGUMENTS | SELECT_PAGINATION_ARGUMENTS


def get_select_option_names(raw_query: RawQuery) -> set[str]:
    if raw_query.clause != Clause.SELECT:
        return set()
    explicit_conditions = set(raw_query.conditions or ())
    return {
        name
        for name in raw_query.kwargs or {}
        if name in SELECT_OPTION_ARGUMENTS and name not in explicit_conditions
    }


def get_select_options(raw_query: RawQuery) -> dict[str, Any]:
    option_names = get_select_option_names(raw_query)
    return {
        name: value
        for name, value in (raw_query.kwargs or {}).items()
        if name in option_names
    }


def get_select_condition_kwargs(raw_query: RawQuery) -> dict[str, Any]:
    option_names = get_select_option_names(raw_query)
    return {
        name: value
        for name, value in (raw_query.kwargs or {}).items()
        if name not in option_names
    }


def get_select_condition_query(raw_query: RawQuery) -> RawQuery:
    return RawQuery(
        raw_query.clause,
        raw_query.target,
        raw_query.fields,
        raw_query.conditions,
        raw_query.is_list_result,
        raw_query.is_async_func,
        raw_query.args,
        get_select_condition_kwargs(raw_query),
        raw_query.result_type,
        raw_query.is_when_condition,
        raw_query.joins,
        raw_query.is_count,
    )


def validate_identifier(value: Any, argument_name: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER_PATTERN.match(value):
        raise ValueError(f"Invalid {argument_name}: {value}")
    return value


def get_select_order_fields(value: Any, argument_name: str) -> tuple[str, ...]:
    if isinstance(value, str):
        return (validate_identifier(value, argument_name),)
    if isinstance(value, tuple):
        if not value:
            raise ValueError(f"{argument_name} requires at least one field")
        return tuple(validate_identifier(field, argument_name) for field in value)
    raise ValueError(f"Invalid {argument_name}: {value}")


def get_select_order(raw_query: RawQuery) -> tuple[tuple[str, str], ...]:
    options = get_select_options(raw_query)
    order_parts = []
    for argument_name, value in options.items():
        if argument_name not in SELECT_ORDER_ARGUMENTS:
            continue
        direction = "DESC" if argument_name.endswith(DESC_SORT_SUFFIXES) else "ASC"
        order_parts.extend(
            (field_name, direction)
            for field_name in get_select_order_fields(value, argument_name)
        )
    return tuple(order_parts)


def get_int_option(options: dict[str, Any], name: str, *, minimum: int) -> int:
    value = options[name]
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer greater than or equal to {minimum}")
    return value


def get_select_range_start(options: dict[str, Any]) -> tuple[str, int] | None:
    has_from = "from" in options
    has_from_ = "from_" in options
    if has_from and has_from_:
        raise ValueError("Use only one of from or from_")
    if has_from:
        return "from", get_int_option(options, "from", minimum=0)
    if has_from_:
        return "from_", get_int_option(options, "from_", minimum=0)
    return None


def get_select_pagination(raw_query: RawQuery) -> tuple[int, int | None] | None:
    options = get_select_options(raw_query)
    range_start = get_select_range_start(options)
    uses_range = range_start is not None or "to" in options
    uses_offset = "offset" in options or "limit" in options
    uses_page = "page" in options or "page_size" in options
    if sum((uses_range, uses_offset, uses_page)) > 1:
        raise ValueError("Use only one pagination style")

    if uses_range:
        if range_start is None or "to" not in options:
            raise ValueError("from/from_ pagination requires to")
        _, start = range_start
        stop = get_int_option(options, "to", minimum=0)
        if stop <= start:
            raise ValueError("to must be greater than from")
        return stop - start, start

    if uses_offset:
        if "limit" not in options:
            raise ValueError("offset pagination requires limit")
        limit = get_int_option(options, "limit", minimum=0)
        offset = get_int_option(options, "offset", minimum=0) if "offset" in options else None
        return limit, offset

    if uses_page:
        if "page" not in options or "page_size" not in options:
            raise ValueError("page pagination requires page and page_size")
        page = get_int_option(options, "page", minimum=1)
        page_size = get_int_option(options, "page_size", minimum=1)
        return page_size, (page - 1) * page_size

    return None


def create_select_order_clause(raw_query: RawQuery) -> str:
    order = get_select_order(raw_query)
    if not order:
        return ""
    return f" ORDER BY {','.join(f'{field_name} {direction}' for field_name, direction in order)}"


def create_select_pagination_clause(raw_query: RawQuery) -> str:
    pagination = get_select_pagination(raw_query)
    if not pagination:
        return ""
    _, offset = pagination
    return " LIMIT %s" if offset is None else " LIMIT %s OFFSET %s"


def prepare_select_pagination_arguments(raw_query: RawQuery) -> tuple[Any, ...]:
    pagination = get_select_pagination(raw_query)
    if not pagination:
        return ()
    limit, offset = pagination
    return (limit,) if offset is None else (limit, offset)


def get_select_option_cache_shape(raw_query: RawQuery) -> tuple[Any, ...]:
    order = get_select_order(raw_query)
    pagination = get_select_pagination(raw_query)
    return (
        order,
        pagination is not None,
        pagination[1] is not None if pagination else False,
    )
