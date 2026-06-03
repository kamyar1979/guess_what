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

`guess-what` does not install database drivers. Install the driver for the database you use:

```bash
pip install psycopg2-binary  # PostgreSQL example
pip install mysql-connector-python  # MySQL example
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

`guess-what` parses method names into SQL using a naming grammar. The full reference lives in [docs/naming-conventions.md](docs/naming-conventions.md).

Common patterns:

```python
db.get_users()
db.get_user_by_id(123)
db.get_users_by(name="Alice", email="alice@example.com")
db.get_user_columns_name_and_email(email="alice@example.com")
db.add_user_columns_name_and_email(name="Alice", email="alice@example.com")
db.set_user_columns_status_by_id("active", 123)
db.delete_user(id=123)
```

Use `_when` for operator conditions:

```python
db.get_users_when(age_less_than=30, name_like="Ali%")
db.get_users_when(id_in=[1, 2, 3])
db.set_user_columns_status_when(status="archived", last_seen_less_than=cutoff)
db.delete_logs_when(created_at_less_than=cutoff)
```

Database functions and stored procedures use `call_...` or `invoke_...`:

```python
db.call_refresh_cache("users", 10)
db.invoke_refresh_cache(table="users", limit=10)
```

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

MySQL/MariaDB integration tests are optional too:

```bash
GUESS_WHAT_MYSQL_DSN="mariadb://user:password@localhost:3306/dbname" \
PYTHONPATH=src uv run --with mysql-connector-python pytest tests/test_integration_mysql.py
```
