from dataclasses import dataclass

import pytest
from guess.model import Clause, DigestedQuery, RawQuery
from guess.parser import parse_func_name, create_query


@dataclass
class User:
    name: str
    email: str
    status: str


def test_parse_func_name_select():
    # Simple select
    q = parse_func_name("get_user_by_id")
    assert q is not None
    assert q.clause == Clause.SELECT
    assert q.target == "users"
    assert q.fields is None
    assert q.conditions == ["id"]

    # Select columns with single condition
    q = parse_func_name("get_user_columns_name_and_email_by_id")
    assert q is not None
    assert q.clause == Clause.SELECT
    assert q.target == "users"
    assert q.fields == ["name", "email"]
    assert q.conditions == ["id"]

    # Select with multiple conditions
    q = parse_func_name("select_user_columns_name_by_status_and_role")
    assert q is not None
    assert q.clause == Clause.SELECT
    assert q.target == "users"
    assert q.fields == ["name"]
    assert q.conditions == ["status", "role"]


def test_parse_func_name_update():
    # Simple update with columns and conditions
    q = parse_func_name("set_user_columns_status_by_id")
    assert q is not None
    assert q.clause == Clause.UPDATE
    assert q.target == "users"
    assert q.fields == ["status"]
    assert q.conditions == ["id"]

    # Edit/update variant
    q = parse_func_name("edit_post_columns_title_and_body_by_author_id")
    assert q is not None
    assert q.clause == Clause.UPDATE
    assert q.target == "posts"
    assert q.fields == ["title", "body"]
    assert q.conditions == ["author_id"]


def test_parse_func_name_insert():
    # Simple insert
    q = parse_func_name("add_user_columns_name_and_email")
    assert q is not None
    assert q.clause == Clause.INSERT
    assert q.target == "users"
    assert q.fields == ["name", "email"]
    assert q.conditions is None


def test_parse_func_name_delete():
    # Simple delete
    q = parse_func_name("delete_user_by_id")
    assert q is not None
    assert q.clause == Clause.DELETE
    assert q.target == "users"
    assert q.fields is None
    assert q.conditions == ["id"]

    # Remove variant
    q = parse_func_name("remove_post_by_author_id_and_category")
    assert q is not None
    assert q.clause == Clause.DELETE
    assert q.target == "posts"
    assert q.fields is None
    assert q.conditions == ["author_id", "category"]


def test_parse_func_name_call():
    q = parse_func_name("call_refresh_cache")
    assert q is not None
    assert q.clause == Clause.CALL
    assert q.target == "refresh_cache"
    assert q.is_list_result is False


def test_parse_func_name_invalid():
    # Not matching the pattern
    assert parse_func_name("invalid_func_name") is None
    assert parse_func_name("get_") is None
    assert parse_func_name("delete_") is None

    # Valid name matches but with empty columns/conditions (expected by current design)
    q = parse_func_name("set_user")
    assert q is not None
    assert q.clause == Clause.UPDATE
    assert q.target == "users"
    assert q.fields is None
    assert q.conditions is None


def test_create_query_select():
    # Select all
    assert create_query("get_users") == DigestedQuery("SELECT * FROM users", (), True, False)
    # Select with conditions
    assert create_query("get_user_by_id") == DigestedQuery("SELECT * FROM users WHERE id = %s", (), False, False)
    # Select columns with conditions
    assert create_query("get_user_columns_name_and_email_by_id") == DigestedQuery(
        "SELECT name,email FROM users WHERE id = %s",
        (),
        False,
        False,
    )


def test_create_query_update():
    assert create_query("set_user_columns_status_by_id") == DigestedQuery(
        "UPDATE users SET status = %s WHERE id = %s",
        (),
        False,
        False,
    )
    assert create_query("edit_post_columns_title_and_body_by_author_id") == DigestedQuery(
        "UPDATE posts SET title = %s,body = %s WHERE author_id = %s",
        (),
        False,
        False,
    )


def test_create_query_insert():
    assert create_query("add_user_columns_name_and_email") == DigestedQuery(
        "INSERT INTO users ( name,email ) VALUES (%s,%s)",
        (),
        False,
        False,
    )
    assert create_query("add_user", None, "Alice", "alice@example.com", "active") == DigestedQuery(
        "INSERT INTO users VALUES (%s,%s,%s)",
        ("Alice", "alice@example.com", "active"),
        False,
        False,
    )


def test_create_query_delete():
    assert create_query("delete_user_by_id") == DigestedQuery("DELETE FROM users WHERE id = %s", (), False, False)
    assert create_query("remove_users") == DigestedQuery("DELETE FROM users", (), True, False)


def test_create_query_call():
    assert create_query("call_refresh_cache", None, "users", 10) == DigestedQuery(
        "refresh_cache(%s,%s)",
        ("users", 10),
        False,
        False,
    )


def test_create_query_insert_uses_dataclass_fields():
    user = User("Alice", "alice@example.com", "active")

    assert create_query("add_user", User, user) == DigestedQuery(
        "INSERT INTO users ( name,email,status ) VALUES (%s,%s,%s)",
        ("Alice", "alice@example.com", "active"),
        False,
        False,
    )


def test_create_query_insert_uses_dict_keys():
    user = {"name": "Alice", "email": "alice@example.com", "status": "active"}

    assert create_query("add_user", dict, user) == DigestedQuery(
        "INSERT INTO users ( name,email,status ) VALUES (%s,%s,%s)",
        ("Alice", "alice@example.com", "active"),
        False,
        False,
    )


def test_create_query_update_uses_dataclass_values_for_selected_columns():
    user = User("Alice", "alice@example.com", "inactive")

    assert create_query("set_user_columns_status_by_name", User, user, "Alice") == DigestedQuery(
        "UPDATE users SET status = %s WHERE name = %s",
        ("inactive", "Alice"),
        False,
        False,
    )


def test_create_query_update_uses_dict_values_for_selected_columns():
    user = {"name": "Alice", "email": "alice@example.com", "status": "inactive"}

    assert create_query("set_user_columns_status_by_name", dict, user, "Alice") == DigestedQuery(
        "UPDATE users SET status = %s WHERE name = %s",
        ("inactive", "Alice"),
        False,
        False,
    )


def test_create_query_update_requires_columns():
    with pytest.raises(ValueError, match="UPDATE queries require columns"):
        create_query("set_user")


def test_create_query_insert_requires_columns():
    with pytest.raises(ValueError, match="INSERT queries require columns or values"):
        create_query("add_user")
