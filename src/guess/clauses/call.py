from typing import Any

from guess.model import DigestedQuery, RawQuery


def prepare_call_arguments(raw_query: RawQuery) -> tuple[Any, ...]:
    if raw_query.args and raw_query.kwargs:
        raise ValueError("You can not use positional and named arguments at the same time here!")
    if raw_query.kwargs:
        return tuple(raw_query.kwargs.values())
    return raw_query.args or ()


def create_call_query(raw_query: RawQuery) -> DigestedQuery:
    args = prepare_call_arguments(raw_query)
    if raw_query.kwargs:
        placeholders = (f"{name} => %s" for name in raw_query.kwargs)
    else:
        placeholders = ("%s" for _ in args)
    query_text = f"{raw_query.target}({','.join(placeholders)})"
    return DigestedQuery(query_text, args, raw_query.is_list_result, raw_query.is_async_func)
