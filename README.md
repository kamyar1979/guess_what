# 🔮 guess-what

An elegant, zero-boilerplate, dynamic SQL interceptor for Python. `guess-what` translates semantic method calls into structured SQL queries at runtime, executing them automatically against any standard DB-API 2.0 database connection (synchronous or asynchronous).

Stop writing repetitive boilerplate queries for simple CRUD operations. Just **guess** the method name, and let the library handle the database.

---

## ✨ Features

- **🚀 Dynamic Method Interception**: Translates arbitrary method calls like `db.get_users()` directly into SQL.
- **⚡ Async & Sync Support**: Use the same `Database` wrapper for sync and async connections.
- **🎯 Intelligent Parsing**: Robust regex-based query builder supporting projection fields and multi-condition `WHERE` clauses.
- **🧩 Typed Models**: Map rows and write values with `db.method[Model](...)` using Python dataclasses or Pydantic models.
- **📞 Call Clause**: Call stored procedures or database functions with `call_...` methods.
- **🔌 Driver Agnostic**: Works with any standard Python DB-API 2.0 connection wrapper (e.g., SQLite, PostgreSQL, MySQL).

---

## 📦 Installation

Install the package from PyPI:

```bash
pip install guess-what
```

For local development and running tests from source, install the development dependencies:

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

# You can also omit column names when you provide the full row values in table order.
# For this users table, prefer named columns because id is generated automatically.

# 3. Retrieve all users (SELECT * FROM users)
users = db.get_users()
print(users)  # [(1, "Alice", "alice@example.com", None), (2, "Bob", ...)]

# 4. Query with specific columns and conditions (SELECT name, email FROM users WHERE id = ?)
user_info = db.get_user_columns_name_and_email_by_id(1)
print(user_info)  # ("Alice", "alice@example.com")

# When using keyword arguments, SELECT and DELETE can infer conditions without `_by_`.
user_info = db.get_user_columns_name_and_email(email="alice@example.com")

# For single-row SELECTs, one positional value is treated as the primary key.
user = db.get_user(1)

# 5. Update data (UPDATE users SET status = ? WHERE id = ?)
db.set_user_columns_status_by_id("active", 1)

# DELETE FROM users WHERE email = ?
db.delete_user(email="bob@example.com")
```

### 2. Asynchronous Usage

```python
import asyncio
from guess import Database

async def main():
    # Mark the wrapper async when all dynamic calls should be awaitable.
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
from guess import Database

async def main():
    # Or keep the wrapper sync by default and opt in per method name.
    async_conn = ... 
    db = Database(async_conn)

    users = await db.async_get_users()
    await db.async_set_user_columns_status_by_id("inactive", 2)

asyncio.run(main())
```

### 3. Typed Dataclass/Pydantic Usage

Use generic-style calls with `db.method[Type](...)` to convert selected rows into Python objects or extract insert/update values from an object. For INSERT and UPDATE, `guess-what` can also infer the model type from a dict, dataclass, or Pydantic object passed as the first argument, so the generic type parameter is optional for common write calls. Supported model types are:

* `dict`
* Python `dataclass` classes
* Pydantic v2 models (`model_fields`)
* Pydantic v1 models (`__fields__`)

```python
from dataclasses import dataclass
from guess import Database

@dataclass
class User:
    name: str
    email: str
    status: str

db = Database(conn)

# INSERT INTO users (name,email,status) VALUES (?, ?, ?)
db.add_user[User](User("Alice", "alice@example.com", "pending"))
db.add_user(User("Bob", "bob@example.com", "active"))

# SELECT * FROM users WHERE name = ?
user = db.get_user_by_name[User]("Alice")
print(user)  # User(name="Alice", email="alice@example.com", status="pending")

# UPDATE users SET status = ? WHERE name = ?
db.set_user_columns_status_by_name[User](
    User("Alice", "alice@example.com", "active"),
    "Alice",
)
db.set_user_columns_status_by_name(
    User("Bob", "bob@example.com", "inactive"),
    "Bob",
)
```

For INSERT and UPDATE, you can also pass the object as a keyword named after the singular table. In this form, `guess-what` infers the model type from the object, so the generic type parameter is optional:

```python
db.add_user(user=User("Alice", "alice@example.com", "pending"))

db.set_user_columns_status_by_name(
    user=User("Alice", "alice@example.com", "active"),
    name="Alice",
)
```

For projected results, use a model that matches the selected columns:

```python
@dataclass
class UserContact:
    name: str
    email: str

contacts = db.get_users_columns_name_and_email[UserContact]()
print(contacts)  # [UserContact(name="Alice", email="alice@example.com")]
```

Use `dict` when you want named columns without defining a model. Dicts work for reads and writes:

```python
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

db.add_user(user={
    "name": "Cara",
    "email": "cara@example.com",
    "status": "pending",
})

user = db.get_user_by_name[dict]("Alice")
print(user)  # {"id": 1, "name": "Alice", "email": "alice@example.com", "status": "pending"}

db.set_user_columns_status_by_name[dict]({"status": "active"}, "Alice")
db.set_user_columns_status_by_name({"status": "inactive"}, "Bob")
db.set_user_columns_status_by_name[dict]({"status": "archived"}, name="Alice")
```

Pydantic models work the same way:

```python
from pydantic import BaseModel

class User(BaseModel):
    name: str
    email: str
    status: str

user = db.get_user_by_name[User]("Alice")
```

## 🛠️ Method Naming Conventions

`guess-what` parses the method names you call using regular expressions to map them to SQL queries. The syntax is composed of:

`[clause]_[table]_columns_[fields]_by_[conditions]`

For database calls, use:

`call_[function_or_procedure]`

*   **`[clause]`**: Supported clauses are:
    *   **SELECT**: `get`, `fetch`, `select`
    *   **UPDATE**: `set`, `edit`, `change`, `modify`, `update`
    *   **INSERT**: `add`, `create`, `insert`
    *   **DELETE**: `delete`, `remove`, `omit`, `drop`
    *   **CALL**: `call`, `invoke`
*   **`[table]`**: Singular form of the database table (automatically pluralized at runtime using inflection). E.g., `user` -> `users`. `call_...` targets are not pluralized.
*   **`[fields]`** *(optional)*: Underscore-separated column list joined with `_and_`. E.g., `name_and_email` -> `name, email`.
*   **`[conditions]`** *(optional)*: Underscore-separated filter columns joined with `_and_`. E.g., `status_and_role` -> `WHERE status = %s AND role = %s`.

Keyword arguments are supported for SELECT, UPDATE, INSERT, and DELETE. Values are ordered by the parsed method name, so caller order does not matter:

```python
db.get_user_by_name_and_status(status="pending", name="Alice")
db.set_user_columns_status_by_name(name="Alice", status="active")
db.add_user_columns_name_and_email(email="alice@example.com", name="Alice")
db.delete_user_by_status_and_role(role="member", status="inactive")
```

For SELECT and DELETE, keyword arguments can also define conditions directly, so `_by_...` is optional when using kwargs. This is equivalent to the `_by_...` form, but shorter for common lookups and deletes:

```python
db.get_user(id=123)
db.get_users(status="pending")
db.get_user_columns_name_and_email(status="active", role="admin")
db.delete_user(id=123)
db.delete_user(status="inactive", role="member")
```

For single-row SELECTs, one positional argument can also imply the primary key condition. Without a typed model, `guess-what` uses `id`. With a typed dataclass or Pydantic model, it looks for `id` or an entity-specific key such as `user_id`; if neither exists, it raises an error instead of guessing the wrong column:

```python
db.get_user(123)        # SELECT * FROM users WHERE id = %s
db.get_user[User](123)  # Uses User.id or User.user_id
```

Database functions and stored procedures can also be called with positional or keyword arguments. Keyword arguments are rendered as named database function parameters, so this form requires database support for named function-call arguments:

```python
db.call_refresh_cache("users", 10)
db.call_refresh_cache(table="users", limit=10)  # refresh_cache(table => %s,limit => %s)
```

### Examples:
*   `get_users` ➡️ `SELECT * FROM users`
*   `fetch_users` ➡️ `SELECT * FROM users`
*   `get_user_by_id` ➡️ `SELECT * FROM users WHERE id = %s`
*   `get_user(id=123)` ➡️ `SELECT * FROM users WHERE id = %s`
*   `get_user(123)` ➡️ `SELECT * FROM users WHERE id = %s`
*   `get_user_columns_name_and_email_by_id` ➡️ `SELECT name,email FROM users WHERE id = %s`
*   `add_user("Alice", "alice@example.com", "active")` ➡️ `INSERT INTO users VALUES (%s,%s,%s)`
*   `create_user("Alice", "alice@example.com", "active")` ➡️ `INSERT INTO users VALUES (%s,%s,%s)`
*   `add_user(User("Alice", "alice@example.com", "active"))` ➡️ `INSERT INTO users ( name,email,status ) VALUES (%s,%s,%s)`
*   `set_user_columns_status_by_id` ➡️ `UPDATE users SET status = %s WHERE id = %s`
*   `change_user_columns_status_by_id` ➡️ `UPDATE users SET status = %s WHERE id = %s`
*   `modify_user_columns_status_by_id` ➡️ `UPDATE users SET status = %s WHERE id = %s`
*   `set_user_columns_status_by_id(User(...), 1)` ➡️ `UPDATE users SET status = %s WHERE id = %s`
*   `delete_user_by_id` ➡️ `DELETE FROM users WHERE id = %s`
*   `omit_user_by_id` ➡️ `DELETE FROM users WHERE id = %s`
*   `drop_user_by_id` ➡️ `DELETE FROM users WHERE id = %s`
*   `delete_user(id=123)` ➡️ `DELETE FROM users WHERE id = %s`
*   `call_refresh_cache("users", 10)` ➡️ `refresh_cache(%s,%s)`
*   `invoke_refresh_cache("users", 10)` ➡️ `refresh_cache(%s,%s)`
*   `call_refresh_cache(table="users", limit=10)` ➡️ `refresh_cache(table => %s,limit => %s)`

---

## 🧪 Running Tests

To run the comprehensive test suite:

```bash
PYTHONPATH=src uv run pytest
```

PostgreSQL integration tests are optional. They run only when a DSN is provided, and the PostgreSQL driver can be supplied just for the test command:

```bash
GUESS_WHAT_POSTGRES_DSN="postgresql://user:password@localhost:5432/dbname" \
PYTHONPATH=src uv run --with psycopg2-binary pytest tests/test_integration_postgres.py
```
