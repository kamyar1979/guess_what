# Naming Conventions

`guess-what` translates semantic method names into SQL at runtime. This document describes the full naming grammar and argument rules.

## Basic Shape

```text
[clause]_[table]_columns_[fields]_by_[conditions]
```

For database functions and stored procedures:

```text
call_[function_or_procedure]
invoke_[function_or_procedure]
```

## Clauses

| SQL action | Supported verbs |
| --- | --- |
| SELECT | `get`, `fetch`, `select` |
| UPDATE | `set`, `edit`, `change`, `modify`, `update` |
| INSERT | `add`, `create`, `insert` |
| DELETE | `delete`, `remove`, `omit`, `drop` |
| CALL | `call`, `invoke` |

`[table]` is written in singular form and pluralized at runtime:

```python
db.get_user_by_id(1)  # SELECT * FROM users WHERE id = %s
```

`call_...` and `invoke_...` targets are not pluralized.

## Fields

Use `_columns_...` to select, insert, or update specific columns. Join multiple names with `_and_`:

```python
db.get_user_columns_name_and_email_by_id(1)
# SELECT name,email FROM users WHERE id = %s

db.set_user_columns_status_by_id("active", 1)
# UPDATE users SET status = %s WHERE id = %s
```

## Equality Conditions With `by`

Use `_by_...` for equality conditions. Join multiple condition fields with `_and_`:

```python
db.get_user_by_name_and_status("Alice", "active")
# SELECT * FROM users WHERE name = %s AND status = %s

db.delete_user_by_status_and_role("inactive", "member")
# DELETE FROM users WHERE status = %s AND role = %s
```

Keyword arguments are ordered by the parsed method name, so caller order does not matter:

```python
db.get_user_by_name_and_status(status="active", name="Alice")
db.set_user_columns_status_by_name(name="Alice", status="inactive")
db.add_user_columns_name_and_email(email="alice@example.com", name="Alice")
db.delete_user_by_status_and_role(role="member", status="inactive")
```

For SELECT and DELETE, named arguments can also define equality conditions directly:

```python
db.get_user(id=123)
db.get_users(status="pending")
db.delete_user(id=123)
db.delete_user(status="inactive", role="member")
```

You can keep the explicit `_by` marker and let kwargs provide the condition names:

```python
db.get_users_by(name="Alice", email="alice@example.com")
db.delete_users_by(status="inactive", role="member")
```

Calling an empty `_by` form without named arguments raises an error instead of generating a broad query.

## SELECT Counts

Use `_count` to return only the number of matching rows:

```python
db.get_users_count()
db.get_users_count(status="active")
db.get_users_count_when(age_less_than=5)
```

Generated count queries return a scalar integer instead of a one-column tuple.

## SELECT Sorting And Pagination

SELECT methods accept special keyword arguments for ordering and pagination. These arguments are not treated as conditions unless they are explicitly named in the method, such as `get_users_by_offset(offset=10)`.

```python
db.get_users(order_by="name")
db.get_users(sort_by="name")
db.get_users(order_by_desc="created_at")
db.get_users(sort_by_desc="created_at")
db.get_users(sort_by_reverse="created_at")
db.get_users(order_by=("name", "email"))
db.get_users(sort_by="name", sort_by_desc="created_at")
```

When multiple sort keyword arguments are used, their call-site order is preserved.

Pagination can be expressed as offset/limit or page/page size:

```python
db.get_users(offset=10, limit=10)
db.get_users(page=2, page_size=10)
```

Range-style pagination is also supported. Because `from` is a Python keyword, use `from_` in normal calls:

```python
db.get_users(from_=10, to=20)
db.get_users(**{"from": 10, "to": 20})
```

Sorting and pagination can be combined with inferred conditions:

```python
db.get_users(status="active", order_by_desc="name", limit=5)
# SELECT * FROM users WHERE status = %s ORDER BY name DESC LIMIT %s
```

## Operator Conditions With `when`

Use `_when` when conditions need operators other than equality. The operator is encoded in the named argument:

```python
db.get_users_when(age_less_than=30, name_like="Ali%")
db.get_users_when(id_in=[1, 2, 3])
db.set_user_columns_status_when(status="archived", last_seen_less_than=cutoff)
db.delete_logs_when(created_at_less_than=cutoff)
```

Supported suffixes:

| Named argument suffix | SQL operator |
| --- | --- |
| no suffix / `equal` | `=` |
| `not_equal` | `<>` |
| `greater_than` | `>` |
| `greater_than_or_equal` | `>=` |
| `less_than` | `<` |
| `less_than_or_equal` | `<=` |
| `like` | `LIKE` |
| `not_like` | `NOT LIKE` |
| `in` | `IN (...)` |

Examples:

```python
db.get_users_when(status="active")
# SELECT * FROM users WHERE status = %s

db.get_users_when(age_greater_than_or_equal=18, name_like="A%")
# SELECT * FROM users WHERE age >= %s AND name LIKE %s

db.get_users_when(id_in=[1, 2, 3])
# SELECT * FROM users WHERE id IN (%s,%s,%s)

db.delete_users_when(status_not_equal="active")
# DELETE FROM users WHERE status <> %s
```

The `in` operator requires a non-empty list or tuple. Its values are still passed as bound parameters:

```python
db.get_users_when(id_in=[1, 2, 3])
# args: (1, 2, 3)
```

`_when` is marker-only. This form is not supported:

```python
db.get_users_when_age_less_than(30)
```

Use this instead:

```python
db.get_users_when(age_less_than=30)
```

## UPDATE With `when`

For UPDATE, field values and condition values are intentionally separated.

Named field values:

```python
db.set_user_columns_status_when(status="inactive", age_less_than=30)
# UPDATE users SET status = %s WHERE age < %s
```

Dataclass, Pydantic, or dict values object:

```python
db.set_user_columns_status_when(User(...), name_like="Ali%")
db.set_user_columns_status_when(user=User(...), name_not_like="Ali%")
db.set_user_columns_status_when({"status": "inactive"}, email_like="alice@%")
```

Multiple positional field values are rejected with `_when` because they are easy to misorder:

```python
db.set_user_columns_name_and_email_when("Alice", "alice@example.com", age_less_than=30)
# raises ValueError
```

Use named field values or a values object instead.

## Primary Key Shorthand

For single-row SELECTs, one positional argument can imply the primary key condition:

```python
db.get_user(123)
# SELECT * FROM users WHERE id = %s

db.get_user[User](123)
# Uses User.id or User.user_id
```

Without a typed model, `guess-what` uses `id`. With a typed dataclass or Pydantic model, it looks for `id` or an entity-specific key such as `user_id`. If neither exists, it raises an error instead of guessing the wrong column.

## Typed Models And Dicts

Generic-style calls can map SELECT results into typed objects:

```python
user = db.get_user_by_name[User]("Alice")
row = db.get_user_by_name[dict]("Alice")
```

Supported result/write types:

* `dict`
* Python dataclasses
* Pydantic v2 models with `model_fields`
* Pydantic v1 models with `__fields__`

For INSERT and UPDATE, the generic type can often be omitted when the first argument is a dataclass, Pydantic object, or dict:

```python
db.add_user(User("Alice", "alice@example.com", "pending"))
db.add_user({"name": "Bob", "email": "bob@example.com", "status": "active"})
db.set_user_columns_status_by_name(User("Alice", "alice@example.com", "active"), "Alice")
```

You can also pass the object using a keyword named after the singular table:

```python
db.add_user(user=User("Alice", "alice@example.com", "pending"))
db.add_user(user={"name": "Bob", "email": "bob@example.com", "status": "active"})

db.set_user_columns_status_by_name(
    user=User("Alice", "alice@example.com", "active"),
    name="Alice",
)
```

## INSERT Without Columns

When you omit `_columns_...`, positional INSERT values are inserted in table order:

```python
db.add_user("Alice", "alice@example.com", "active")
# INSERT INTO users VALUES (%s,%s,%s)
```

Prefer explicit columns when the table has generated values such as auto-increment IDs.

## Database Function Calls

Database functions and stored procedures can be called with positional arguments:

```python
db.call_refresh_cache("users", 10)
db.invoke_refresh_cache("users", 10)
# refresh_cache(%s,%s)
```

Keyword arguments are rendered as named database function parameters:

```python
db.call_refresh_cache(table="users", limit=10)
# refresh_cache(table => %s,limit => %s)
```

This form relies on database support for named function-call arguments.
