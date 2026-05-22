import sqlite3

from guess import Database


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

    db.set_user_columns_status_by_email("active", "alice@example.com")

    assert db.get_users_columns_name_by_status("active") == [
        ("Alice",),
        ("Bob",),
    ]

    db.delete_user_by_email("bob@example.com")

    assert db.get_users_columns_name_and_status() == [("Alice", "active")]
    assert db.get_user_by_email("bob@example.com") is None
