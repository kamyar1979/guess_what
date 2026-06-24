from typing import Any, Optional

from guess.clauses.call import create_call_query, prepare_call_arguments
from guess.clauses.delete import create_delete_query, prepare_delete_arguments
from guess.clauses.insert import create_insert_query, prepare_insert_arguments
from guess.clauses.select import create_select_query, prepare_select_arguments
from guess.clauses.update import create_update_query, prepare_update_arguments
from guess.grammar import parse_function_to_query
from guess.model import Clause, DigestedQuery, RawQuery


CLAUSE_HANDLERS = {
    Clause.SELECT: create_select_query,
    Clause.UPDATE: create_update_query,
    Clause.INSERT: create_insert_query,
    Clause.DELETE: create_delete_query,
    Clause.CALL: create_call_query,
}

ARGUMENT_HANDLERS = {
    Clause.SELECT: prepare_select_arguments,
    Clause.UPDATE: prepare_update_arguments,
    Clause.INSERT: prepare_insert_arguments,
    Clause.DELETE: prepare_delete_arguments,
    Clause.CALL: prepare_call_arguments,
}


def prepare_arguments(raw_query: RawQuery) -> tuple[Any, ...]:
    return ARGUMENT_HANDLERS[raw_query.clause](raw_query)


def create_query(func_name: str, result_type: Optional[type] = None, *args, **kwargs) -> Optional[DigestedQuery]:
    if raw_query := parse_function_to_query(func_name, result_type, *args, **kwargs):
        return CLAUSE_HANDLERS[raw_query.clause](raw_query)
    return None
