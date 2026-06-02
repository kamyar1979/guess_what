import sqlite3
from dataclasses import dataclass

from guess import Database

@dataclass
class User:
    name: str
    email: str
    status: str


@dataclass
class UserContact:
    name: str
    email: str


@dataclass
class ExternalUser:
    user_id: int
    name: str


def test_sqlite_database_dynamic_methods_end_to_end():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """
    )

    db = Database(conn)

    db.add_user_columns_name_and_email_and_status(
        "Alice",
        "alice@example.com",
        "pending",
    )
    db.add_user_columns_name_and_email_and_status(
        "Bob",
        "bob@example.com",
        "active",
    )

    assert db.get_users_columns_name_and_email() == [
        ("Alice", "alice@example.com"),
        ("Bob", "bob@example.com"),
    ]

    assert db.get_user_columns_name_and_status_by_email("alice@example.com") == (
        "Alice",
        "pending",
    )
    assert db.get_user_columns_name_and_status(email="alice@example.com") == (
        "Alice",
        "pending",
    )

    db.set_user_columns_status_by_email("active", "alice@example.com")
    db.set_user_columns_status_by_email(email="bob@example.com", status="pending")

    assert db.get_users_columns_name_by_status("active") == [
        ("Alice",),
    ]
    assert db.get_user_columns_name_by_status(status="pending") == ("Bob",)

    db.delete_user(email="bob@example.com")

    assert db.get_users_columns_name_and_status() == [("Alice", "active")]
    assert db.get_user_by_email("bob@example.com") is None


def test_sqlite_database_semantic_verb_aliases_end_to_end():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """
    )

    db = Database(conn)

    db.create_user_columns_name_and_email_and_status(
        "Alice",
        "alice@example.com",
        "pending",
    )

    assert db.fetch_user_by_email("alice@example.com") == (
        1,
        "Alice",
        "alice@example.com",
        "pending",
    )

    db.change_user_columns_status_by_email("active", "alice@example.com")

    assert db.fetch_user_columns_status_by_email("alice@example.com") == ("active",)

    db.modify_user_columns_status_by_email("inactive", "alice@example.com")

    assert db.fetch_user_columns_status_by_email("alice@example.com") == ("inactive",)

    db.omit_user_by_email("alice@example.com")

    assert db.fetch_user_by_email("alice@example.com") is None

    db.create_user_columns_name_and_email_and_status(
        "Bob",
        "bob@example.com",
        "pending",
    )

    db.drop_user_by_email("bob@example.com")

    assert db.fetch_user_by_email("bob@example.com") is None


def test_sqlite_database_dataclass_insert_select_and_update():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """
    )

    db = Database(conn)

    db.add_user[User](User("Alice", "alice@example.com", "pending"))
    db.add_user[User](user=User("Bob", "bob@example.com", "active"))
    db.add_user(User("Cara", "cara@example.com", "archived"))

    assert db.get_user_by_name[User]("Alice") == User(
        "Alice",
        "alice@example.com",
        "pending",
    )
    assert db.get_users[User]() == [
        User("Alice", "alice@example.com", "pending"),
        User("Bob", "bob@example.com", "active"),
        User("Cara", "cara@example.com", "archived"),
    ]

    db.set_user_columns_status_by_name[User](
        User("Alice", "alice@example.com", "active"),
        "Alice",
    )
    db.set_user_columns_status_by_name[User](
        user=User("Bob", "bob@example.com", "pending"),
        name="Bob",
    )
    db.edit_user_columns_status_by_name(
        User("Cara", "cara@example.com", "active"),
        "Cara",
    )

    assert db.get_user_by_name[dict]("Alice") == {
        "id": 1,
        "name": "Alice",
        "email": "alice@example.com",
        "status": "active",
    }
    assert db.get_user_by_name[dict]("Bob") == {
        "id": 2,
        "name": "Bob",
        "email": "bob@example.com",
        "status": "pending",
    }
    assert db.get_user_by_name[dict]("Cara") == {
        "id": 3,
        "name": "Cara",
        "email": "cara@example.com",
        "status": "active",
    }


def test_sqlite_database_insert_without_columns_uses_positional_values():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE users (
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """
    )

    db = Database(conn)

    db.add_user("Alice", "alice@example.com", "active")

    assert db.get_user_by_email("alice@example.com") == (
        "Alice",
        "alice@example.com",
        "active",
    )


def test_sqlite_database_insert_with_kwargs():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE users (
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """
    )

    db = Database(conn)

    db.add_user_columns_name_and_email_and_status(
        status="pending",
        email="alice@example.com",
        name="Alice",
    )
    db.add_user(user={"name": "Bob", "email": "bob@example.com", "status": "active"})

    assert db.get_users_columns_name_and_status() == [
        ("Alice", "pending"),
        ("Bob", "active"),
    ]


def test_sqlite_database_select_infers_conditions_from_kwargs_without_by():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            status TEXT NOT NULL,
            role TEXT NOT NULL
        )
        """
    )

    db = Database(conn)

    db.add_user_columns_name_and_email_and_status_and_role(
        "Alice",
        "alice@example.com",
        "active",
        "admin",
    )
    db.add_user_columns_name_and_email_and_status_and_role(
        "Bob",
        "bob@example.com",
        "pending",
        "member",
    )

    assert db.get_user(name="Alice") == (
        1,
        "Alice",
        "alice@example.com",
        "active",
        "admin",
    )
    assert db.get_user(2) == (
        2,
        "Bob",
        "bob@example.com",
        "pending",
        "member",
    )
    assert db.get_user_columns_email_and_role(status="pending", name="Bob") == (
        "bob@example.com",
        "member",
    )


def test_sqlite_database_single_select_infers_entity_id_condition_from_model():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
        """
    )

    db = Database(conn)

    db.add_user_columns_user_id_and_name(10, "Alice")
    db.add_user_columns_user_id_and_name(20, "Bob")

    assert db.get_user[ExternalUser](20) == ExternalUser(20, "Bob")


def test_sqlite_database_delete_infers_conditions_from_kwargs_without_by():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            status TEXT NOT NULL,
            role TEXT NOT NULL
        )
        """
    )

    db = Database(conn)

    db.add_user_columns_name_and_email_and_status_and_role(
        "Alice",
        "alice@example.com",
        "active",
        "admin",
    )
    db.add_user_columns_name_and_email_and_status_and_role(
        "Bob",
        "bob@example.com",
        "pending",
        "member",
    )

    db.delete_user(status="pending", role="member")

    assert db.get_users_columns_name_and_status() == [("Alice", "active")]
    assert db.get_user_by_name("Bob") is None


def test_sqlite_database_dict_insert_select_and_update():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """
    )

    db = Database(conn)

    db.add_user[dict]({
        "name": "Alice",
        "email": "alice@example.com",
        "status": "pending",
    })
    db.add_user({
        "name": "Bob",
        "email": "bob@example.com",
        "status": "active",
    })

    assert db.get_user_by_name[dict]("Alice") == {
        "id": 1,
        "name": "Alice",
        "email": "alice@example.com",
        "status": "pending",
    }
    assert db.get_user_by_name[dict]("Bob") == {
        "id": 2,
        "name": "Bob",
        "email": "bob@example.com",
        "status": "active",
    }

    db.set_user_columns_status_by_name[dict](
        {"status": "active"},
        "Alice",
    )
    db.set_user_columns_status_by_name(
        {"status": "inactive"},
        "Bob",
    )
    db.set_user_columns_status_by_name[dict](
        {"status": "archived"},
        name="Alice",
    )

    assert db.get_users_columns_name_and_status[dict]() == [
        {"name": "Alice", "status": "archived"},
        {"name": "Bob", "status": "inactive"},
    ]


def test_sqlite_database_generic_dataclass_projection():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """
    )

    db = Database(conn)

    db.add_user[User](User("Alice", "alice@example.com", "active"))
    db.add_user[User](User("Bob", "bob@example.com", "pending"))

    assert db.get_user_columns_name_and_email_by_status[UserContact]("active") == UserContact(
        "Alice",
        "alice@example.com",
    )
    assert db.get_users_columns_name_and_email[UserContact]() == [
        UserContact("Alice", "alice@example.com"),
        UserContact("Bob", "bob@example.com"),
    ]


def test_sqlite_database_supports_multiple_conditions_and_direct_execute():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            status TEXT NOT NULL,
            role TEXT NOT NULL
        )
        """
    )

    db = Database(conn)

    db.execute(
        "INSERT INTO users (name, email, status, role) VALUES (?, ?, ?, ?)",
        ("Alice", "alice@example.com", "active", "admin"),
    )
    db.execute(
        "INSERT INTO users (name, email, status, role) VALUES (?, ?, ?, ?)",
        ("Bob", "bob@example.com", "active", "member"),
    )
    db.execute(
        "INSERT INTO users (name, email, status, role) VALUES (?, ?, ?, ?)",
        ("Cara", "cara@example.com", "inactive", "member"),
    )

    assert db.get_user_columns_name_and_email_by_status_and_role("active", "admin") == (
        "Alice",
        "alice@example.com",
    )
    assert db.get_user_columns_name_and_email_by_status_and_role(role="admin", status="active") == (
        "Alice",
        "alice@example.com",
    )
    assert db.get_user_columns_name_and_email(status="active", role="admin") == (
        "Alice",
        "alice@example.com",
    )
    assert db.get_users_columns_name_by_status_and_role("active", "member") == [("Bob",)]

    db.delete_user(status="inactive", role="member")

    assert db.get_users_columns_name_by_status_and_role("inactive", "member") == []


def test_sqlite_database_returns_empty_list_for_missing_rows():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL
        )
        """
    )

    db = Database(conn)

    assert db.get_users() == []
    assert db.get_user_by_email("nobody@example.com") is None
