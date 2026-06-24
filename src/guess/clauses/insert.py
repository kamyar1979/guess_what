from typing import Any

from guess.clauses.arguments import prepare_kwargs, prepare_model_or_positional_arguments
from guess.model import DigestedQuery, RawQuery
from guess.values import get_field_names, get_model_type_from_value, split_model_kwargs


def prepare_insert_arguments(raw_query: RawQuery) -> tuple[Any, ...]:
    if raw_query.kwargs:
        obj, result_type, remaining_kwargs = split_model_kwargs(raw_query)
        if obj is not None:
            if remaining_kwargs:
                raise ValueError(f"Unknown keyword arguments: {','.join(remaining_kwargs)}")
            return prepare_model_or_positional_arguments(RawQuery(
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

    return prepare_model_or_positional_arguments(raw_query)


def create_insert_query(raw_query: RawQuery) -> DigestedQuery:
    insert_fields = raw_query.fields
    model_obj, model_type, remaining_kwargs = split_model_kwargs(raw_query)
    result_type = raw_query.result_type
    if not result_type and len(raw_query.args or ()) == 1:
        result_type = get_model_type_from_value(raw_query.args[0])

    if not insert_fields and result_type:
        if result_type == dict:
            insert_fields = list((model_obj or raw_query.args[0]).keys())
        else:
            insert_fields = get_field_names(result_type)
    if not insert_fields and model_obj is not None:
        if model_type == dict:
            insert_fields = list(model_obj.keys())
        else:
            insert_fields = get_field_names(model_type)
    if not insert_fields and raw_query.kwargs:
        insert_fields = list(remaining_kwargs.keys())

    args = prepare_insert_arguments(raw_query)
    if not insert_fields and not args:
        raise ValueError("INSERT queries require columns or values")

    columns = f"( {','.join(insert_fields)} ) " if insert_fields else ""
    value_count = len(insert_fields) if insert_fields else len(args)
    query_text = f"INSERT INTO {raw_query.target} {columns}VALUES ({','.join('%s' for _ in range(value_count))})"
    return DigestedQuery(query_text, args, raw_query.is_list_result, raw_query.is_async_func)
