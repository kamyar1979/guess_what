import re
from dataclasses import is_dataclass, fields
from typing import Optional, Any
from cachetools import cached, LRUCache
import inflection

from guess.model import Clause, Operator, ParsedQuery, clause_mapping, RawQuery, DigestedQuery

clause_handlers = {}
argument_handlers = {}
parse_function_cache = LRUCache(maxsize=1024)
select_query_cache = LRUCache(maxsize=1024)
select_argument_names_cache = LRUCache(maxsize=1024)
delete_query_cache = LRUCache(maxsize=1024)
delete_argument_names_cache = LRUCache(maxsize=1024)
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
}


def register_clause(clause: Clause):
    def decorate(func):
        clause_handlers[clause] = func
        return func

    return decorate


def register_argument_handler(clause: Clause):
    def decorate(func):
        argument_handlers[clause] = func
        return func

    return decorate


FUNC_NAME_PATTERN = rf"""
^
(?P<async>async_)?
(?P<clause>{'|'.join(clause_mapping.keys())})
_
(?P<target>(?:(?!_(?:columns|by|when)(?:_|$))\w)+?)

(?:_columns_(?P<fields>(?:(?!_(?:by|when)(?:_|$))\w)+))?
(?:(?P<by>_by)(?:_(?P<conditions>\w+?))?|(?P<when>_when))?
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


def get_model_type_from_value(obj: Any) -> type | None:
    if isinstance(obj, dict):
        return dict
    cls = type(obj)
    if is_dataclass(cls) or hasattr(cls, "model_fields") or hasattr(cls, "__fields__"):
        return cls
    return None


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


def parse_named_argument_to_condition(name: str) -> tuple[str, Operator]:
    for operator in sorted(Operator, key=lambda item: len(item.value), reverse=True):
        suffix = f"_{operator.value}"
        if name.endswith(suffix):
            field_name = name[:-len(suffix)]
            if not field_name:
                raise ValueError(f"Missing field name for operator: {operator.value}")
            return field_name, operator
    return name, Operator.EQUAL


def parse_named_arguments_to_where_clause(named_arguments: dict[str, Any]) -> str:
    if not named_arguments:
        return ""

    conditions = []
    for name in named_arguments:
        field_name, operator = parse_named_argument_to_condition(name)
        conditions.append(f"{field_name} {operator_mapping[operator]} %s")
    return f" WHERE {' AND '.join(conditions)}"


def prepare_named_condition_arguments(raw_query: RawQuery) -> tuple[Any, ...]:
    if raw_query.args and raw_query.kwargs:
        raise ValueError("You can not use positional and named arguments at the same time here!")
    if raw_query.args:
        raise ValueError("When clauses require named arguments")
    if not raw_query.kwargs:
        raise ValueError("Empty when clause requires named arguments")
    return tuple(raw_query.kwargs.values())


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
        field_args = prepare_arguments(RawQuery(
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
        field_args = prepare_arguments(RawQuery(
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

    return field_args + tuple(condition_arguments.values())


def create_condition_clause(raw_query: RawQuery) -> str:
    if raw_query.is_when_condition:
        return parse_named_arguments_to_where_clause(raw_query.kwargs or {})

    condition_fields = get_conditions(raw_query)
    return f" WHERE {' AND '.join(f'{field} = %s' for field in condition_fields)}" if condition_fields else ""


def create_update_condition_clause(raw_query: RawQuery) -> str:
    if raw_query.is_when_condition:
        return parse_named_arguments_to_where_clause(get_update_named_condition_arguments(raw_query))
    return create_condition_clause(raw_query)


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
    if raw_query.clause in (Clause.SELECT, Clause.DELETE) and raw_query.conditions == []:
        raise ValueError("Empty by clause requires keyword arguments")
    return get_primary_key_condition(raw_query)


@cached(cache=parse_function_cache)
def parse_function_name(func_name: str) -> Optional[ParsedQuery]:
    if m := regex.match(func_name):
        clause = clause_mapping[m.group("clause")]
        target = m.group("target") if clause == Clause.CALL else inflection.pluralize(m.group("target"))
        return ParsedQuery(
            clause,
            target,
            tuple(m.group("fields").split('_and_')) if m.group("fields") else None,
            tuple(m.group("conditions").split('_and_')) if m.group("conditions") else (() if m.group("by") or m.group("when") else None),
            clause != Clause.CALL and inflection.pluralize(m.group("target")) == m.group("target"),
            m.group("async") == "async_",
            m.group("when") is not None,
        )
    return None


def bind_parsed_query(parsed_query: ParsedQuery, result_type: Optional[type] = None, *args, **kwargs) -> RawQuery:
    return RawQuery(
        parsed_query.clause,
        parsed_query.target,
        list(parsed_query.fields) if parsed_query.fields is not None else None,
        list(parsed_query.conditions) if parsed_query.conditions is not None else None,
        parsed_query.is_list_result,
        parsed_query.is_async_func,
        args,
        kwargs,
        result_type,
        parsed_query.is_when_condition,
    )


def parse_function_to_query(func_name: str, result_type: Optional[type] = None, *args, **kwargs) -> Optional[RawQuery]:
    if parsed_query := parse_function_name(func_name):
        return bind_parsed_query(parsed_query, result_type, *args, **kwargs)
    return None


def create_select_query_cache_key(raw_query: RawQuery) -> tuple[Any, ...]:
    return (
        raw_query.clause,
        raw_query.target,
        tuple(raw_query.fields or ()),
        tuple(raw_query.conditions) if raw_query.conditions is not None else None,
        raw_query.is_list_result,
        raw_query.is_async_func,
        raw_query.is_when_condition,
        raw_query.result_type,
        tuple((raw_query.kwargs or {}).keys()),
        len(raw_query.args or ()),
    )


def create_delete_query_cache_key(raw_query: RawQuery) -> tuple[Any, ...]:
    return (
        raw_query.clause,
        raw_query.target,
        tuple(raw_query.conditions) if raw_query.conditions is not None else None,
        raw_query.is_list_result,
        raw_query.is_async_func,
        raw_query.is_when_condition,
        tuple((raw_query.kwargs or {}).keys()),
        len(raw_query.args or ()),
    )


@cached(cache=select_argument_names_cache, key=lambda raw_query: create_select_query_cache_key(raw_query))
def get_select_argument_names(raw_query: RawQuery) -> tuple[str, ...]:
    return get_conditions(raw_query)


@cached(cache=delete_argument_names_cache, key=lambda raw_query: create_delete_query_cache_key(raw_query))
def get_delete_argument_names(raw_query: RawQuery) -> tuple[str, ...]:
    return get_conditions(raw_query)


@cached(cache=select_query_cache, key=lambda raw_query: create_select_query_cache_key(raw_query))
def create_select_query_shape(raw_query: RawQuery) -> DigestedQuery:
    conditions = create_condition_clause(raw_query)
    fields_str = ",".join(raw_query.fields) if raw_query.fields else "*"
    query_text = f"SELECT {fields_str} FROM {raw_query.target}{conditions}"
    return DigestedQuery(query_text, None, raw_query.is_list_result, raw_query.is_async_func)


@cached(cache=delete_query_cache, key=lambda raw_query: create_delete_query_cache_key(raw_query))
def create_delete_query_shape(raw_query: RawQuery) -> DigestedQuery:
    conditions = create_condition_clause(raw_query)
    query_text = f"DELETE FROM {raw_query.target}{conditions}"
    return DigestedQuery(query_text, None, raw_query.is_list_result, raw_query.is_async_func)


@register_argument_handler(Clause.SELECT)
def prepare_select_arguments(raw_query: RawQuery) -> tuple[Any, ...]:
    if raw_query.is_when_condition:
        return prepare_named_condition_arguments(raw_query)
    return prepare_kwargs(raw_query, get_select_argument_names(raw_query), reject_duplicates=True)


@register_argument_handler(Clause.DELETE)
def prepare_delete_arguments(raw_query: RawQuery) -> tuple[Any, ...]:
    if raw_query.is_when_condition:
        return prepare_named_condition_arguments(raw_query)
    return prepare_kwargs(raw_query, get_delete_argument_names(raw_query), reject_duplicates=True)


@register_argument_handler(Clause.UPDATE)
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

    return prepare_model_or_positional_arguments(raw_query)


@register_argument_handler(Clause.INSERT)
def prepare_insert_arguments(raw_query: RawQuery) -> tuple[Any, ...]:
    if raw_query.kwargs:
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

    return prepare_model_or_positional_arguments(raw_query)


@register_argument_handler(Clause.CALL)
def prepare_call_arguments(raw_query: RawQuery) -> tuple[Any, ...]:
    if raw_query.args and raw_query.kwargs:
        raise ValueError("You can not use positional and named arguments at the same time here!")
    if raw_query.kwargs:
        return tuple(raw_query.kwargs.values())
    return raw_query.args or ()


def prepare_model_or_positional_arguments(raw_query: RawQuery) -> tuple[Any, ...]:
    if (
        raw_query.clause in (Clause.INSERT, Clause.UPDATE)
        and not raw_query.result_type
        and raw_query.args
        and (raw_query.clause == Clause.UPDATE or len(raw_query.args) == 1)
    ):
        if result_type := get_model_type_from_value(raw_query.args[0]):
            return prepare_arguments(RawQuery(
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
    else:
        return raw_query.args or ()


def prepare_arguments(raw_query: RawQuery) -> tuple[Any, ...]:
    return argument_handlers[raw_query.clause](raw_query)


@register_clause(Clause.SELECT)
def create_select_query(raw_query: RawQuery) -> DigestedQuery:
    query_shape = create_select_query_shape(raw_query)
    return DigestedQuery(query_shape.text, prepare_arguments(raw_query), query_shape.is_list, query_shape.is_async)


@register_clause(Clause.UPDATE)
def create_update_query(raw_query: RawQuery) -> DigestedQuery:
    if not raw_query.fields:
        raise ValueError("UPDATE queries require columns")

    conditions = create_update_condition_clause(raw_query)
    set_clause = ",".join(f"{f} = %s" for f in (raw_query.fields or []))
    query_text = f"UPDATE {raw_query.target} SET {set_clause}{conditions}"
    return DigestedQuery(query_text, prepare_arguments(raw_query), raw_query.is_list_result, raw_query.is_async_func)


@register_clause(Clause.INSERT)
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

    args = prepare_arguments(raw_query)
    if not insert_fields and not args:
        raise ValueError("INSERT queries require columns or values")

    columns = f"( {','.join(insert_fields)} ) " if insert_fields else ""
    value_count = len(insert_fields) if insert_fields else len(args)
    query_text = f"INSERT INTO {raw_query.target} {columns}VALUES ({','.join('%s' for _ in range(value_count))})"
    return DigestedQuery(query_text, args, raw_query.is_list_result, raw_query.is_async_func)


@register_clause(Clause.DELETE)
def create_delete_query(raw_query: RawQuery) -> DigestedQuery:
    query_shape = create_delete_query_shape(raw_query)
    return DigestedQuery(query_shape.text, prepare_arguments(raw_query), query_shape.is_list, query_shape.is_async)


@register_clause(Clause.CALL)
def create_call_query(raw_query: RawQuery) -> DigestedQuery:
    args = prepare_arguments(raw_query)
    if raw_query.kwargs:
        placeholders = (f"{name} => %s" for name in raw_query.kwargs)
    else:
        placeholders = ("%s" for _ in args)
    query_text = f"{raw_query.target}({','.join(placeholders)})"
    return DigestedQuery(query_text, args, raw_query.is_list_result, raw_query.is_async_func)


def create_query(func_name: str, result_type: Optional[type] = None, *args, **kwargs) -> Optional[DigestedQuery]:
    if q := parse_function_to_query(func_name, result_type, *args, **kwargs):
        return clause_handlers[q.clause](q)
    return None
