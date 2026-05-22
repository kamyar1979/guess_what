import pytest
from guess.model import Clause, Query
from guess.parser import parse_func_name, create_query


def test_parse_func_name_select():
    # Simple select
    q = parse_func_name("get_user_by_id")
    assert q is not None
    assert q.clause == Clause.SELECT
    assert q.table == "users"
    assert q.fields is None
    assert q.conditions == ["id"]

    # Select columns with single condition
    q = parse_func_name("get_user_columns_name_and_email_by_id")
    assert q is not None
    assert q.clause == Clause.SELECT
    assert q.table == "users"
    assert q.fields == ["name", "email"]
    assert q.conditions == ["id"]

    # Select with multiple conditions
    q = parse_func_name("select_user_columns_name_by_status_and_role")
    assert q is not None
    assert q.clause == Clause.SELECT
    assert q.table == "users"
    assert q.fields == ["name"]
    assert q.conditions == ["status", "role"]


def test_parse_func_name_update():
    # Simple update with columns and conditions
    q = parse_func_name("set_user_columns_status_by_id")
    assert q is not None
    assert q.clause == Clause.UPDATE
    assert q.table == "users"
    assert q.fields == ["status"]
    assert q.conditions == ["id"]

    # Edit/update variant
    q = parse_func_name("edit_post_columns_title_and_body_by_author_id")
    assert q is not None
    assert q.clause == Clause.UPDATE
    assert q.table == "posts"
    assert q.fields == ["title", "body"]
    assert q.conditions == ["author_id"]


def test_parse_func_name_insert():
    # Simple insert
    q = parse_func_name("add_user_columns_name_and_email")
    assert q is not None
    assert q.clause == Clause.INSERT
    assert q.table == "users"
    assert q.fields == ["name", "email"]
    assert q.conditions is None


def test_parse_func_name_delete():
    # Simple delete
    q = parse_func_name("delete_user_by_id")
    assert q is not None
    assert q.clause == Clause.DELETE
    assert q.table == "users"
    assert q.fields is None
    assert q.conditions == ["id"]

    # Remove variant
    q = parse_func_name("remove_post_by_author_id_and_category")
    assert q is not None
    assert q.clause == Clause.DELETE
    assert q.table == "posts"
    assert q.fields is None
    assert q.conditions == ["author_id", "category"]


def test_parse_func_name_invalid():
    # Not matching the pattern
    assert parse_func_name("invalid_func_name") is None
    assert parse_func_name("get_") is None
    assert parse_func_name("delete_") is None

    # Valid name matches but with empty columns/conditions (expected by current design)
    q = parse_func_name("set_user")
    assert q is not None
    assert q.clause == Clause.UPDATE
    assert q.table == "users"
    assert q.fields is None
    assert q.conditions is None


def test_create_query_select():
    # Select all
    assert create_query("get_users") == "SELECT * FROM users"
    # Select with conditions
    assert create_query("get_user_by_id") == "SELECT * FROM users WHERE id = %s"
    # Select columns with conditions
    assert create_query("get_user_columns_name_and_email_by_id") == "SELECT name,email FROM users WHERE id = %s"


def test_create_query_update():
    assert create_query("set_user_columns_status_by_id") == "UPDATE users SET status = %s WHERE id = %s"
    assert create_query("edit_post_columns_title_and_body_by_author_id") == "UPDATE posts SET title = %s,body = %s WHERE author_id = %s"


def test_create_query_insert():
    assert create_query("add_user_columns_name_and_email") == "INSERT INTO users ( name,email ) VALUES (%s,%s)"


def test_create_query_delete():
    assert create_query("delete_user_by_id") == "DELETE FROM users WHERE id = %s"
    assert create_query("remove_users") == "DELETE FROM users"
