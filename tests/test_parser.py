from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

import pytest
from guess.model import Clause, DigestedQuery, RawQuery
from guess.parser import (
    parse_function_to_query,
    parse_function_name,
    create_query,
    create_delete_query_shape,
    create_select_query_shape,
    delete_argument_names_cache,
    delete_query_cache,
    get_conditions,
    parse_named_arguments_to_where_clause,
    prepare_kwargs,
    regex,
    select_argument_names_cache,
    select_query_cache,
)


@dataclass
class User:
    name: str
    email: str
    status: str


@dataclass
class ExternalUser:
    user_id: int
    name: str


class PydanticLikeUser:
    model_fields = {"name": None, "email": None, "status": None}

    def __init__(self, name: str, email: str, status: str):
        self.name = name
        self.email = email
        self.status = status


class Status(StrEnum):
    ACTIVE = "active"


def test_conditions_are_returned_as_ordered_tuple():
    explicit = RawQuery(Clause.SELECT, "users", conditions=["name", "status"])
    update = RawQuery(Clause.UPDATE, "users", conditions=["id", "status"])
    inferred = RawQuery(Clause.SELECT, "users", kwargs={"status": "pending", "role": "admin"})

    assert get_conditions(explicit) == ("name", "status")
    assert get_conditions(update) == ("id", "status")
    assert get_conditions(inferred) == ("status", "role")
    assert isinstance(get_conditions(explicit), tuple)


def test_prepare_kwargs_accepts_ordered_tuple_names():
    query = RawQuery(Clause.SELECT, "users", kwargs={"status": "pending", "name": "Alice"})

    assert prepare_kwargs(query, ("name", "status")) == ("Alice", "pending")


def test_parse_function_name_is_cached_without_call_values():
    parse_function_name.cache_clear()

    parsed = parse_function_name("get_user_by_id")
    cached = parse_function_name("get_user_by_id")
    first = parse_function_to_query("get_user_by_id", None, 1)
    second = parse_function_to_query("get_user_by_id", None, 2)

    assert parsed is cached
    assert first is not None
    assert second is not None
    assert first.args == (1,)
    assert second.args == (2,)
    assert first.conditions == ["id"]
    assert second.conditions == ["id"]


def test_select_query_shape_is_cached_without_argument_values():
    create_select_query_shape.cache_clear()

    first = create_query("get_users_when", None, age_less_than=30)
    second = create_query("get_users_when", None, age_less_than=40)
    third = create_query("get_users_when", None, age_greater_than=40)

    assert first == DigestedQuery("SELECT * FROM users WHERE age < %s", (30,), True, False)
    assert second == DigestedQuery("SELECT * FROM users WHERE age < %s", (40,), True, False)
    assert third == DigestedQuery("SELECT * FROM users WHERE age > %s", (40,), True, False)
    assert len(select_query_cache) == 2


def test_select_argument_names_are_cached_without_argument_values():
    select_argument_names_cache.clear()

    first = create_query("get_user_by_id", None, 1)
    second = create_query("get_user_by_id", None, 2)

    assert first == DigestedQuery("SELECT * FROM users WHERE id = %s", (1,), False, False)
    assert second == DigestedQuery("SELECT * FROM users WHERE id = %s", (2,), False, False)
    assert len(select_argument_names_cache) == 1


def test_delete_query_shape_is_cached_without_argument_values():
    create_delete_query_shape.cache_clear()

    first = create_query("delete_users_when", None, age_less_than=30)
    second = create_query("delete_users_when", None, age_less_than=40)
    third = create_query("delete_users_when", None, age_greater_than=40)

    assert first == DigestedQuery("DELETE FROM users WHERE age < %s", (30,), True, False)
    assert second == DigestedQuery("DELETE FROM users WHERE age < %s", (40,), True, False)
    assert third == DigestedQuery("DELETE FROM users WHERE age > %s", (40,), True, False)
    assert len(delete_query_cache) == 2


def test_delete_argument_names_are_cached_without_argument_values():
    delete_argument_names_cache.clear()

    first = create_query("delete_user_by_id", None, 1)
    second = create_query("delete_user_by_id", None, 2)

    assert first == DigestedQuery("DELETE FROM users WHERE id = %s", (1,), False, False)
    assert second == DigestedQuery("DELETE FROM users WHERE id = %s", (2,), False, False)
    assert len(delete_argument_names_cache) == 1


def test_parse_func_name_select():
    # Simple select
    q = parse_function_to_query("get_user_by_id")
    assert q is not None
    assert q.clause == Clause.SELECT
    assert q.target == "users"
    assert q.fields is None
    assert q.conditions == ["id"]

    # Select columns with single condition
    q = parse_function_to_query("get_user_columns_name_and_email_by_id")
    assert q is not None
    assert q.clause == Clause.SELECT
    assert q.target == "users"
    assert q.fields == ["name", "email"]
    assert q.conditions == ["id"]

    # Select with multiple conditions
    q = parse_function_to_query("select_user_columns_name_by_status_and_role")
    assert q is not None
    assert q.clause == Clause.SELECT
    assert q.target == "users"
    assert q.fields == ["name"]
    assert q.conditions == ["status", "role"]

    # Explicit by-clause with conditions inferred from kwargs at call time
    q = parse_function_to_query("get_users_by")
    assert q is not None
    assert q.clause == Clause.SELECT
    assert q.target == "users"
    assert q.fields is None
    assert q.conditions == []

    # Explicit when-clause for richer conditions in later parsing steps
    m = regex.match("get_users_when")
    assert m is not None
    assert m.group("when") == "_when"
    assert m.group("by") is None

    q = parse_function_to_query("get_user_columns_name_when")
    assert q is not None
    assert q.clause == Clause.SELECT
    assert q.target == "users"
    assert q.fields == ["name"]
    assert q.conditions == []
    assert q.is_when_condition is True

    assert parse_function_to_query("get_user_columns_name_when_age_less_than") is None


def test_parse_named_arguments_to_where_clause():
    assert parse_named_arguments_to_where_clause({}) == ""
    assert parse_named_arguments_to_where_clause({"status": "active"}) == " WHERE status = %s"
    assert parse_named_arguments_to_where_clause({
        "age_less_than": 30,
        "created_at_greater_than_or_equal": "2026-01-01",
        "name_like": "Ali%",
        "status_not_equal": "deleted",
    }) == (
        " WHERE age < %s AND created_at >= %s AND name LIKE %s AND status <> %s"
    )


def test_parse_func_name_semantic_aliases():
    q = parse_function_to_query("fetch_user_by_id")
    assert q is not None
    assert q.clause == Clause.SELECT
    assert q.target == "users"
    assert q.conditions == ["id"]

    q = parse_function_to_query("change_user_columns_status_by_id")
    assert q is not None
    assert q.clause == Clause.UPDATE
    assert q.target == "users"
    assert q.fields == ["status"]
    assert q.conditions == ["id"]

    q = parse_function_to_query("modify_user_columns_status_by_id")
    assert q is not None
    assert q.clause == Clause.UPDATE
    assert q.target == "users"
    assert q.fields == ["status"]
    assert q.conditions == ["id"]

    q = parse_function_to_query("create_user_columns_name_and_email")
    assert q is not None
    assert q.clause == Clause.INSERT
    assert q.target == "users"
    assert q.fields == ["name", "email"]

    q = parse_function_to_query("omit_user_by_id")
    assert q is not None
    assert q.clause == Clause.DELETE
    assert q.target == "users"
    assert q.conditions == ["id"]

    q = parse_function_to_query("drop_user_by_id")
    assert q is not None
    assert q.clause == Clause.DELETE
    assert q.target == "users"
    assert q.conditions == ["id"]

    q = parse_function_to_query("invoke_refresh_cache")
    assert q is not None
    assert q.clause == Clause.CALL
    assert q.target == "refresh_cache"


def test_parse_func_name_update():
    # Simple update with columns and conditions
    q = parse_function_to_query("set_user_columns_status_by_id")
    assert q is not None
    assert q.clause == Clause.UPDATE
    assert q.target == "users"
    assert q.fields == ["status"]
    assert q.conditions == ["id"]

    # Edit/update variant
    q = parse_function_to_query("edit_post_columns_title_and_body_by_author_id")
    assert q is not None
    assert q.clause == Clause.UPDATE
    assert q.target == "posts"
    assert q.fields == ["title", "body"]
    assert q.conditions == ["author_id"]


def test_parse_func_name_insert():
    # Simple insert
    q = parse_function_to_query("add_user_columns_name_and_email")
    assert q is not None
    assert q.clause == Clause.INSERT
    assert q.target == "users"
    assert q.fields == ["name", "email"]
    assert q.conditions is None


def test_parse_func_name_delete():
    # Simple delete
    q = parse_function_to_query("delete_user_by_id")
    assert q is not None
    assert q.clause == Clause.DELETE
    assert q.target == "users"
    assert q.fields is None
    assert q.conditions == ["id"]

    # Remove variant
    q = parse_function_to_query("remove_post_by_author_id_and_category")
    assert q is not None
    assert q.clause == Clause.DELETE
    assert q.target == "posts"
    assert q.fields is None
    assert q.conditions == ["author_id", "category"]

    # Explicit by-clause with conditions inferred from kwargs at call time
    q = parse_function_to_query("delete_users_by")
    assert q is not None
    assert q.clause == Clause.DELETE
    assert q.target == "users"
    assert q.fields is None
    assert q.conditions == []


def test_parse_func_name_call():
    q = parse_function_to_query("call_refresh_cache")
    assert q is not None
    assert q.clause == Clause.CALL
    assert q.target == "refresh_cache"
    assert q.is_list_result is False


def test_parse_func_name_invalid():
    # Not matching the pattern
    assert parse_function_to_query("invalid_func_name") is None
    assert parse_function_to_query("get_") is None
    assert parse_function_to_query("delete_") is None

    # Valid name matches but with empty columns/conditions (expected by current design)
    q = parse_function_to_query("set_user")
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
    assert create_query("get_user_by_name_and_status", None, status="pending", name="test") == DigestedQuery(
        "SELECT * FROM users WHERE name = %s AND status = %s",
        ("test", "pending"),
        False,
        False,
    )
    assert create_query("get_user", None, id=123) == DigestedQuery(
        "SELECT * FROM users WHERE id = %s",
        (123,),
        False,
        False,
    )
    assert create_query("get_user", None, 123) == DigestedQuery(
        "SELECT * FROM users WHERE id = %s",
        (123,),
        False,
        False,
    )
    assert create_query("get_user", ExternalUser, 123) == DigestedQuery(
        "SELECT * FROM users WHERE user_id = %s",
        (123,),
        False,
        False,
    )
    assert create_query("get_user_columns_name_and_email", None, status="pending", role="admin") == DigestedQuery(
        "SELECT name,email FROM users WHERE status = %s AND role = %s",
        ("pending", "admin"),
        False,
        False,
    )
    assert create_query("fetch_user_by_id") == DigestedQuery(
        "SELECT * FROM users WHERE id = %s",
        (),
        False,
        False,
    )


def test_create_query_select_rejects_mixed_positional_and_keyword_args():
    with pytest.raises(ValueError, match="positional and named arguments"):
        create_query("get_user_by_name_and_status", None, "test", status="pending")


def test_create_query_select_rejects_missing_keyword_args():
    with pytest.raises(ValueError, match="Missing keyword arguments: status"):
        create_query("get_user_by_name_and_status", None, name="test")


def test_create_query_select_rejects_unknown_keyword_args():
    with pytest.raises(ValueError, match="Unknown keyword arguments: role"):
        create_query("get_user_by_name", None, name="test", role="admin")


def test_create_query_select_infers_conditions_from_kwargs_without_by():
    assert create_query("get_users", None, status="pending") == DigestedQuery(
        "SELECT * FROM users WHERE status = %s",
        ("pending",),
        True,
        False,
    )


def test_create_query_select_infers_conditions_from_kwargs_with_empty_by():
    assert create_query("get_users_by", None, email="alice@example.com", name="Alice") == DigestedQuery(
        "SELECT * FROM users WHERE email = %s AND name = %s",
        ("alice@example.com", "Alice"),
        True,
        False,
    )
    assert create_query("get_user_by", None, id=123) == DigestedQuery(
        "SELECT * FROM users WHERE id = %s",
        (123,),
        False,
        False,
    )
    assert create_query("get_user_by_name_and_email", None, email="alice@example.com", name="Alice") == DigestedQuery(
        "SELECT * FROM users WHERE name = %s AND email = %s",
        ("Alice", "alice@example.com"),
        False,
        False,
    )


def test_create_query_select_uses_when_operator_conditions():
    assert create_query(
        "get_users_when",
        None,
        age_less_than=30,
        created_at_greater_than_or_equal="2026-01-01",
        name_like="Ali%",
        status="active",
    ) == DigestedQuery(
        "SELECT * FROM users WHERE age < %s AND created_at >= %s AND name LIKE %s AND status = %s",
        (30, "2026-01-01", "Ali%", "active"),
        True,
        False,
    )
    assert create_query("get_user_columns_name_when", None, status_not_equal="deleted") == DigestedQuery(
        "SELECT name FROM users WHERE status <> %s",
        ("deleted",),
        False,
        False,
    )


def test_create_query_select_rejects_empty_by_without_kwargs():
    with pytest.raises(ValueError, match="Empty by clause requires keyword arguments"):
        create_query("get_users_by")

    with pytest.raises(ValueError, match="Empty by clause requires keyword arguments"):
        create_query("get_user_by", None, 123)


def test_create_query_select_rejects_when_without_named_arguments():
    with pytest.raises(ValueError, match="Empty when clause requires named arguments"):
        create_query("get_users_when")

    with pytest.raises(ValueError, match="When clauses require named arguments"):
        create_query("get_user_when", None, 123)


def test_create_query_select_rejects_ambiguous_duplicate_names_with_kwargs():
    with pytest.raises(ValueError, match="Keyword arguments are ambiguous for duplicate names: name"):
        create_query("get_user_columns_name_by_name", None, name="test")


def test_create_query_select_rejects_primary_key_shorthand_without_pk_field():
    with pytest.raises(ValueError, match="Could not infer primary key field"):
        create_query("get_user", User, 123)


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
    assert create_query("change_user_columns_status_by_id") == DigestedQuery(
        "UPDATE users SET status = %s WHERE id = %s",
        (),
        False,
        False,
    )
    assert create_query("modify_user_columns_status_by_id") == DigestedQuery(
        "UPDATE users SET status = %s WHERE id = %s",
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
    assert create_query("add_user_columns_name_and_email", None, email="alice@example.com", name="Alice") == DigestedQuery(
        "INSERT INTO users ( name,email ) VALUES (%s,%s)",
        ("Alice", "alice@example.com"),
        False,
        False,
    )
    assert create_query("add_user", None, name="Alice", email="alice@example.com", status="active") == DigestedQuery(
        "INSERT INTO users ( name,email,status ) VALUES (%s,%s,%s)",
        ("Alice", "alice@example.com", "active"),
        False,
        False,
    )
    assert create_query("create_user_columns_name_and_email") == DigestedQuery(
        "INSERT INTO users ( name,email ) VALUES (%s,%s)",
        (),
        False,
        False,
    )


def test_create_query_delete():
    assert create_query("delete_user_by_id") == DigestedQuery("DELETE FROM users WHERE id = %s", (), False, False)
    assert create_query("remove_users") == DigestedQuery("DELETE FROM users", (), True, False)
    assert create_query("omit_user_by_id") == DigestedQuery("DELETE FROM users WHERE id = %s", (), False, False)
    assert create_query("drop_user_by_id") == DigestedQuery("DELETE FROM users WHERE id = %s", (), False, False)
    assert create_query("delete_user_by_status_and_role", None, role="member", status="inactive") == DigestedQuery(
        "DELETE FROM users WHERE status = %s AND role = %s",
        ("inactive", "member"),
        False,
        False,
    )
    assert create_query("delete_user", None, id=123) == DigestedQuery(
        "DELETE FROM users WHERE id = %s",
        (123,),
        False,
        False,
    )
    assert create_query("delete_users_by", None, status="inactive", role="member") == DigestedQuery(
        "DELETE FROM users WHERE status = %s AND role = %s",
        ("inactive", "member"),
        True,
        False,
    )
    assert create_query("delete_users_when", None, created_at_less_than="2026-01-01") == DigestedQuery(
        "DELETE FROM users WHERE created_at < %s",
        ("2026-01-01",),
        True,
        False,
    )


def test_create_query_delete_rejects_missing_keyword_args():
    with pytest.raises(ValueError, match="Missing keyword arguments: role"):
        create_query("delete_user_by_status_and_role", None, status="inactive")


def test_create_query_delete_rejects_unknown_keyword_args():
    with pytest.raises(ValueError, match="Unknown keyword arguments: name"):
        create_query("delete_user_by_status", None, status="inactive", name="Alice")


def test_create_query_delete_rejects_empty_by_without_kwargs():
    with pytest.raises(ValueError, match="Empty by clause requires keyword arguments"):
        create_query("delete_users_by")


def test_create_query_delete_rejects_when_without_named_arguments():
    with pytest.raises(ValueError, match="Empty when clause requires named arguments"):
        create_query("delete_users_when")

    with pytest.raises(ValueError, match="When clauses require named arguments"):
        create_query("delete_user_when", None, 123)


def test_create_query_call():
    assert create_query("call_refresh_cache", None, "users", 10) == DigestedQuery(
        "refresh_cache(%s,%s)",
        ("users", 10),
        False,
        False,
    )
    assert create_query("call_refresh_cache", None, table="users", limit=10) == DigestedQuery(
        "refresh_cache(table => %s,limit => %s)",
        ("users", 10),
        False,
        False,
    )
    assert create_query("invoke_refresh_cache", None, "users", 10) == DigestedQuery(
        "refresh_cache(%s,%s)",
        ("users", 10),
        False,
        False,
    )


def test_create_query_call_rejects_mixed_positional_and_keyword_args():
    with pytest.raises(ValueError, match="positional and named arguments"):
        create_query("call_refresh_cache", None, "users", limit=10)


def test_create_query_insert_uses_dataclass_fields():
    user = User("Alice", "alice@example.com", "active")

    assert create_query("add_user", User, user) == DigestedQuery(
        "INSERT INTO users ( name,email,status ) VALUES (%s,%s,%s)",
        ("Alice", "alice@example.com", "active"),
        False,
        False,
    )
    assert create_query("add_user", None, user) == DigestedQuery(
        "INSERT INTO users ( name,email,status ) VALUES (%s,%s,%s)",
        ("Alice", "alice@example.com", "active"),
        False,
        False,
    )


def test_create_query_insert_uses_pydantic_like_fields_without_generic():
    user = PydanticLikeUser("Alice", "alice@example.com", "active")

    assert create_query("add_user", None, user) == DigestedQuery(
        "INSERT INTO users ( name,email,status ) VALUES (%s,%s,%s)",
        ("Alice", "alice@example.com", "active"),
        False,
        False,
    )


def test_create_query_insert_uses_dataclass_keyword_named_after_table():
    user = User("Alice", "alice@example.com", "active")

    assert create_query("add_user", User, user=user) == DigestedQuery(
        "INSERT INTO users ( name,email,status ) VALUES (%s,%s,%s)",
        ("Alice", "alice@example.com", "active"),
        False,
        False,
    )
    assert create_query("add_user", None, user=user) == DigestedQuery(
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
    assert create_query("add_user", None, user) == DigestedQuery(
        "INSERT INTO users ( name,email,status ) VALUES (%s,%s,%s)",
        ("Alice", "alice@example.com", "active"),
        False,
        False,
    )


def test_create_query_insert_uses_dict_keyword_named_after_table():
    user = {"name": "Alice", "email": "alice@example.com", "status": "active"}

    assert create_query("add_user", dict, user=user) == DigestedQuery(
        "INSERT INTO users ( name,email,status ) VALUES (%s,%s,%s)",
        ("Alice", "alice@example.com", "active"),
        False,
        False,
    )
    assert create_query("add_user", None, user=user) == DigestedQuery(
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
    assert create_query("set_user_columns_status_by_name", None, user, "Alice") == DigestedQuery(
        "UPDATE users SET status = %s WHERE name = %s",
        ("inactive", "Alice"),
        False,
        False,
    )


def test_create_query_update_uses_pydantic_like_values_without_generic():
    user = PydanticLikeUser("Alice", "alice@example.com", "inactive")

    assert create_query("edit_user_columns_status_by_name", None, user, "Alice") == DigestedQuery(
        "UPDATE users SET status = %s WHERE name = %s",
        ("inactive", "Alice"),
        False,
        False,
    )


def test_create_query_update_uses_kwargs_for_fields_and_conditions():
    assert create_query("set_user_columns_status_by_name", None, name="Alice", status="inactive") == DigestedQuery(
        "UPDATE users SET status = %s WHERE name = %s",
        ("inactive", "Alice"),
        False,
        False,
    )


def test_create_query_update_uses_when_operator_conditions():
    assert create_query("set_user_columns_status_when", None, status="inactive", age_less_than=30) == DigestedQuery(
        "UPDATE users SET status = %s WHERE age < %s",
        ("inactive", 30),
        False,
        False,
    )
    assert create_query(
        "set_user_columns_status_when",
        None,
        status="inactive",
        age_greater_than_or_equal=18,
        name_like="Ali%",
    ) == DigestedQuery(
        "UPDATE users SET status = %s WHERE age >= %s AND name LIKE %s",
        ("inactive", 18, "Ali%"),
        False,
        False,
    )


def test_create_query_update_uses_typed_value_and_kwargs_for_conditions():
    user = User("Alice", "alice@example.com", "inactive")

    assert create_query("set_user_columns_status_by_name", User, user, name="Alice") == DigestedQuery(
        "UPDATE users SET status = %s WHERE name = %s",
        ("inactive", "Alice"),
        False,
        False,
    )


def test_create_query_update_uses_typed_keyword_value_and_kwargs_for_conditions():
    user = User("Alice", "alice@example.com", "inactive")

    assert create_query("set_user_columns_status_by_name", User, user=user, name="Alice") == DigestedQuery(
        "UPDATE users SET status = %s WHERE name = %s",
        ("inactive", "Alice"),
        False,
        False,
    )


def test_create_query_update_uses_typed_value_and_when_operator_conditions():
    user = User("Alice", "alice@example.com", "inactive")

    assert create_query("set_user_columns_status_when", User, user, name_like="Ali%") == DigestedQuery(
        "UPDATE users SET status = %s WHERE name LIKE %s",
        ("inactive", "Ali%"),
        False,
        False,
    )
    assert create_query("set_user_columns_status_when", User, user=user, name_not_like="Ali%") == DigestedQuery(
        "UPDATE users SET status = %s WHERE name NOT LIKE %s",
        ("inactive", "Ali%"),
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
    assert create_query("set_user_columns_status_by_name", None, user, "Alice") == DigestedQuery(
        "UPDATE users SET status = %s WHERE name = %s",
        ("inactive", "Alice"),
        False,
        False,
    )


def test_create_query_update_uses_dict_values_and_when_operator_conditions():
    user = {"name": "Alice", "email": "alice@example.com", "status": "inactive"}

    assert create_query("set_user_columns_status_when", dict, user, email_like="alice@%") == DigestedQuery(
        "UPDATE users SET status = %s WHERE email LIKE %s",
        ("inactive", "alice@%"),
        False,
        False,
    )


def test_create_query_update_rejects_ambiguous_duplicate_names_with_kwargs():
    with pytest.raises(ValueError, match="Keyword arguments are ambiguous for duplicate names: name"):
        create_query("set_user_columns_name_by_name", None, name="Alice")


def test_create_query_update_rejects_when_without_named_conditions():
    with pytest.raises(ValueError, match="Empty when clause requires named condition arguments"):
        create_query("set_user_columns_status_when", None, status="inactive")

    with pytest.raises(ValueError, match="When clauses require named field values or a typed values object"):
        create_query("set_user_columns_status_when", None, "inactive", age_less_than=30)


def test_create_query_update_rejects_typed_kwargs_with_extra_positional_conditions():
    user = User("Alice", "alice@example.com", "inactive")

    with pytest.raises(ValueError, match="values object can be the only positional argument"):
        create_query("set_user_columns_status_by_name", User, user, "Alice", name="Alice")


def test_create_query_update_requires_columns():
    with pytest.raises(ValueError, match="UPDATE queries require columns"):
        create_query("set_user")


def test_create_query_insert_requires_columns():
    with pytest.raises(ValueError, match="INSERT queries require columns or values"):
        create_query("add_user")


def test_create_query_preserves_driver_specific_scalar_values():
    price = Decimal("19.99")
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    status = Status.ACTIVE

    assert create_query(
        "add_product_columns_price_and_owner_id_and_status",
        None,
        price,
        user_id,
        status,
    ) == DigestedQuery(
        "INSERT INTO products ( price,owner_id,status ) VALUES (%s,%s,%s)",
        (price, user_id, status),
        False,
        False,
    )
