from typing import Any

from cachetools import LRUCache, cached

from guess.clauses.arguments import prepare_kwargs
from guess.clauses.conditions import (
    create_condition_clause,
    get_conditions,
    get_named_argument_cache_shape,
    prepare_named_condition_arguments,
)
from guess.model import DigestedQuery, RawQuery
from guess.clauses.select_options import (
    create_select_order_clause,
    create_select_pagination_clause,
    get_select_condition_query,
    get_select_option_cache_shape,
    get_select_options,
    prepare_select_pagination_arguments,
)


select_query_cache = LRUCache(maxsize=1024)
select_argument_names_cache = LRUCache(maxsize=1024)


def create_select_query_cache_key(raw_query: RawQuery) -> tuple[Any, ...]:
    return (
        raw_query.clause,
        raw_query.target,
        tuple(raw_query.fields or ()),
        tuple(raw_query.conditions) if raw_query.conditions is not None else None,
        tuple(raw_query.joins) if raw_query.joins is not None else None,
        raw_query.is_list_result,
        raw_query.is_async_func,
        raw_query.is_when_condition,
        raw_query.is_count,
        raw_query.result_type,
        get_select_option_cache_shape(raw_query),
        tuple(get_named_argument_cache_shape(name, value) for name, value in (raw_query.kwargs or {}).items()),
        len(raw_query.args or ()),
    )


@cached(cache=select_argument_names_cache, key=lambda raw_query: create_select_query_cache_key(raw_query))
def get_select_argument_names(raw_query: RawQuery) -> tuple[str, ...]:
    return get_conditions(raw_query)


@cached(cache=select_query_cache, key=lambda raw_query: create_select_query_cache_key(raw_query))
def create_select_query_shape(raw_query: RawQuery) -> DigestedQuery:
    if raw_query.joins:
        raise ValueError("JOIN queries are not supported yet")
    if raw_query.is_count and raw_query.fields:
        raise ValueError("COUNT queries do not support selected columns")
    if raw_query.is_count and get_select_options(raw_query):
        raise ValueError("COUNT queries do not support sorting or pagination")

    condition_query = get_select_condition_query(raw_query)
    conditions = create_condition_clause(condition_query)
    fields_str = "COUNT(*)" if raw_query.is_count else ",".join(raw_query.fields) if raw_query.fields else "*"
    order = create_select_order_clause(raw_query)
    pagination = create_select_pagination_clause(raw_query)
    query_text = f"SELECT {fields_str} FROM {raw_query.target}{conditions}{order}{pagination}"
    return DigestedQuery(query_text, None, raw_query.is_list_result, raw_query.is_async_func)


def prepare_select_arguments(raw_query: RawQuery) -> tuple[Any, ...]:
    condition_query = get_select_condition_query(raw_query)
    if condition_query.is_when_condition:
        condition_args = prepare_named_condition_arguments(condition_query)
    else:
        condition_args = prepare_kwargs(condition_query, get_select_argument_names(condition_query), reject_duplicates=True)
    return condition_args + prepare_select_pagination_arguments(raw_query)


def create_select_query(raw_query: RawQuery) -> DigestedQuery:
    query_shape = create_select_query_shape(raw_query)
    return DigestedQuery(
        query_shape.text,
        prepare_select_arguments(raw_query),
        query_shape.is_list,
        query_shape.is_async,
    )
