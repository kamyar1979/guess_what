from dataclasses import fields, is_dataclass
from typing import Any

import inflection

from guess.model import RawQuery


def get_field_names(model) -> list[str]:
    if model == dict:
        raise TypeError("dict field names must come from a value")

    cls = model if isinstance(model, type) else type(model)

    if is_dataclass(cls):
        return [f.name for f in fields(cls)]

    if hasattr(cls, "model_fields"):
        return list(cls.model_fields.keys())

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
