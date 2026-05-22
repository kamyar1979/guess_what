# 🔮 guess-what

An elegant, zero-boilerplate, dynamic SQL interceptor for Python. `guess-what` translates semantic method calls into structured SQL queries at runtime, executing them automatically against any standard DB-API 2.0 database connection (synchronous or asynchronous).

Stop writing repetitive boilerplate queries for simple CRUD operations. Just **guess** the method name, and let the library handle the database.

---

## ✨ Features

- **🚀 Dynamic Method Interception**: Translates arbitrary method calls like `db.get_users()` directly into SQL.
- **⚡ Async & Sync Support**: Works out of the box with synchronous connection wrappers (`Database`) and asynchronous ones (`AsyncDatabase`).
- **🎯 Intelligent Parsing**: Robust regex-based query builder supporting projection fields and multi-condition `WHERE` clauses.
- **🔌 Driver Agnostic**: Works with any standard Python DB-API 2.0 connection wrapper (e.g., SQLite, PostgreSQL, MySQL).

---

## 📦 Installation

Ensure you have [uv](https://github.com/astral-sh/uv) or `pip` installed:

```bash
uv pip install .
```

For development and running tests, install with development dependencies:

```bash
uv sync --group dev
```

---

## 🚀 Quick Start

### 1. Synchronous Usage

```python
import sqlite3
from guess import Database

# 1. Connect to your database
conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT, status TEXT)")

db = Database(conn)

# 2. Insert data dynamically (INSERT INTO users (name, email) VALUES (?, ?))
db.add_user_columns_name_and_email("Alice", "alice@example.com")
db.add_user_columns_name_and_email("Bob", "bob@example.com")

# 3. Retrieve all users (SELECT * FROM users)
users = db.get_users()
print(users)  # [(1, "Alice", "alice@example.com", None), (2, "Bob", ...)]

# 4. Query with specific columns and conditions (SELECT name, email FROM users WHERE id = ?)
user_info = db.get_user_columns_name_and_email_by_id(1)
print(user_info)  # ("Alice", "alice@example.com")

# 5. Update data (UPDATE users SET status = ? WHERE id = ?)
db.set_user_columns_status_by_id("active", 1)
```

### 2. Asynchronous Usage

```python
import asyncio
from guess import AsyncDatabase

async def main():
    # Pass an asynchronous DB connection/pool to AsyncDatabase
    async_conn = ... 
    db = Database(async_conn, is_async=True)

    # All calls are automatically awaited
    users = await db.get_users()
    await db.set_user_columns_status_by_id("inactive", 2)

asyncio.run(main())
```

OR:

```python
import asyncio
from guess import AsyncDatabase

async def main():
    # Pass an asynchronous DB connection/pool to AsyncDatabase
    async_conn = ... 
    db = Database(async_conn)

    # All calls are automatically awaited
    users = await db.async_get_users()
    await db.set_user_columns_status_by_id("inactive", 2)

asyncio.run(main())
```

## 🛠️ Method Naming Conventions

`guess-what` parses the method names you call using regular expressions to map them to SQL queries. The syntax is composed of:

`[clause]_[table]_columns_[fields]_by_[conditions]`

*   **`[clause]`**: Supported clauses are:
    *   **SELECT**: `get`, `select`
    *   **UPDATE**: `set`, `edit`, `update`
    *   **INSERT**: `add`, `insert`
    *   **DELETE**: `delete`, `remove`
*   **`[table]`**: Singular form of the database table (automatically pluralized at runtime using inflection). E.g., `user` -> `users`.
*   **`[fields]`** *(optional)*: Underscore-separated column list joined with `_and_`. E.g., `name_and_email` -> `name, email`.
*   **`[conditions]`** *(optional)*: Underscore-separated filter columns joined with `_and_`. E.g., `status_and_role` -> `WHERE status = %s AND role = %s`.

### Examples:
*   `get_users` ➡️ `SELECT * FROM users`
*   `get_user_by_id` ➡️ `SELECT * FROM users WHERE id = %s`
*   `get_user_columns_name_and_email_by_id` ➡️ `SELECT name,email FROM users WHERE id = %s`
*   `set_user_columns_status_by_id` ➡️ `UPDATE users SET status = %s WHERE id = %s`
*   `delete_user_by_id` ➡️ `DELETE FROM users WHERE id = %s`

---

## 🧪 Running Tests

To run the comprehensive test suite:

```bash
PYTHONPATH=src uv run pytest
```
