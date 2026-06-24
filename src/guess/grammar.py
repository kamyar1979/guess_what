import re
from typing import Optional

from cachetools import LRUCache, cached
import inflection

from guess.model import Clause, Join, ParsedQuery, RawQuery, clause_mapping


parse_function_cache = LRUCache(maxsize=1024)

FUNC_NAME_PATTERN = rf"""
^
(?P<async>async_)?
(?P<clause>{'|'.join(clause_mapping.keys())})
_
(?P<target>(?:(?!_(?:count|columns|with|by|when)(?:_|$))\w)+)

(?P<count>_count)?
(?P<body>(?:(?!_(?:by|when)(?:_|$)).)*?)
(?:(?P<by>_by)(?:_(?P<conditions>\w+?))?|(?P<when>_when))?
$
"""

regex = re.compile(FUNC_NAME_PATTERN, re.VERBOSE)


def parse_columns_segment(segment: str) -> tuple[str, ...]:
    if not segment:
        return ()
    return tuple(segment.split("_and_"))


def parse_query_body(body: str) -> tuple[tuple[str, ...] | None, tuple[Join, ...] | None]:
    if not body:
        return None, None

    parts = body.split("_with_")
    fields = None
    root_segment = parts[0]

    if root_segment:
        if not root_segment.startswith("_columns_"):
            raise ValueError(f"Invalid query segment: {root_segment}")
        fields = parse_columns_segment(root_segment.removeprefix("_columns_"))

    joins = []
    for join_segment in parts[1:]:
        if not join_segment:
            raise ValueError("JOIN target is required after with")
        target, separator, columns = join_segment.partition("_columns_")
        if not target:
            raise ValueError("JOIN target is required after with")
        joins.append(Join(
            inflection.pluralize(target),
            parse_columns_segment(columns) if separator else None,
        ))

    return fields, tuple(joins) if joins else None


@cached(cache=parse_function_cache)
def parse_function_name(func_name: str) -> Optional[ParsedQuery]:
    if m := regex.match(func_name):
        clause = clause_mapping[m.group("clause")]
        try:
            fields, joins = parse_query_body(m.group("body"))
        except ValueError:
            return None
        if joins and clause != Clause.SELECT:
            return None
        is_count = m.group("count") is not None
        if is_count and clause != Clause.SELECT:
            return None
        target = m.group("target") if clause == Clause.CALL else inflection.pluralize(m.group("target"))
        return ParsedQuery(
            clause,
            target,
            fields,
            tuple(m.group("conditions").split('_and_')) if m.group("conditions") else (() if m.group("by") or m.group("when") else None),
            False if is_count else clause != Clause.CALL and inflection.pluralize(m.group("target")) == m.group("target"),
            m.group("async") == "async_",
            m.group("when") is not None,
            joins,
            is_count,
        )
    return None


def bind_parsed_query(parsed_query: ParsedQuery, result_type: Optional[type] = None, *args, **kwargs) -> RawQuery:
    return RawQuery(
        parsed_query.clause,
        parsed_query.target,
        parsed_query.fields,
        parsed_query.conditions,
        parsed_query.is_list_result,
        parsed_query.is_async_func,
        args,
        kwargs,
        result_type,
        parsed_query.is_when_condition,
        parsed_query.joins,
        parsed_query.is_count,
    )


def parse_function_to_query(func_name: str, result_type: Optional[type] = None, *args, **kwargs) -> Optional[RawQuery]:
    if parsed_query := parse_function_name(func_name):
        return bind_parsed_query(parsed_query, result_type, *args, **kwargs)
    return None
