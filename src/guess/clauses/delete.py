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


delete_query_cache = LRUCache(maxsize=1024)
delete_argument_names_cache = LRUCache(maxsize=1024)


def create_delete_query_cache_key(raw_query: RawQuery) -> tuple[Any, ...]:
    return (
        raw_query.clause,
        raw_query.target,
        tuple(raw_query.conditions) if raw_query.conditions is not None else None,
        raw_query.is_list_result,
        raw_query.is_async_func,
        raw_query.is_when_condition,
        tuple(get_named_argument_cache_shape(name, value) for name, value in (raw_query.kwargs or {}).items()),
        len(raw_query.args or ()),
    )


@cached(cache=delete_argument_names_cache, key=lambda raw_query: create_delete_query_cache_key(raw_query))
def get_delete_argument_names(raw_query: RawQuery) -> tuple[str, ...]:
    return get_conditions(raw_query)


@cached(cache=delete_query_cache, key=lambda raw_query: create_delete_query_cache_key(raw_query))
def create_delete_query_shape(raw_query: RawQuery) -> DigestedQuery:
    conditions = create_condition_clause(raw_query)
    query_text = f"DELETE FROM {raw_query.target}{conditions}"
    return DigestedQuery(query_text, None, raw_query.is_list_result, raw_query.is_async_func)


def prepare_delete_arguments(raw_query: RawQuery) -> tuple[Any, ...]:
    if raw_query.is_when_condition:
        return prepare_named_condition_arguments(raw_query)
    return prepare_kwargs(raw_query, get_delete_argument_names(raw_query), reject_duplicates=True)


def create_delete_query(raw_query: RawQuery) -> DigestedQuery:
    query_shape = create_delete_query_shape(raw_query)
    return DigestedQuery(
        query_shape.text,
        prepare_delete_arguments(raw_query),
        query_shape.is_list,
        query_shape.is_async,
    )
