import pytest
from unittest.mock import MagicMock, AsyncMock
from guess import Database


def test_sync_database_select_multiple():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.fetchall.return_value = [("Alice", "alice@example.com"), ("Bob", "bob@example.com")]

    db = Database(mock_conn)
    result = db.get_users()

    mock_conn.cursor.assert_called_once()
    mock_cursor.execute.assert_called_once_with("SELECT * FROM users", ())
    mock_cursor.fetchall.assert_called_once()
    mock_cursor.close.assert_called_once()
    assert result == [("Alice", "alice@example.com"), ("Bob", "bob@example.com")]


def test_sync_database_select_single():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.fetchall.return_value = [("Alice", "alice@example.com")]

    db = Database(mock_conn)
    result = db.get_user_by_id(1)

    mock_cursor.execute.assert_called_once_with("SELECT * FROM users WHERE id = %s", (1,))
    mock_cursor.fetchall.assert_called_once()
    mock_cursor.close.assert_called_once()
    assert result == ("Alice", "alice@example.com")


def test_sync_database_insert():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    db = Database(mock_conn)
    result = db.add_user_columns_name_and_email("Alice", "alice@example.com")

    mock_cursor.execute.assert_called_once_with("INSERT INTO users ( name,email ) VALUES (%s,%s)", ("Alice", "alice@example.com"))
    mock_cursor.close.assert_called_once()
    mock_conn.commit.assert_called_once()
    assert result is None


def test_sync_database_update():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    db = Database(mock_conn)
    db.set_user_columns_status_by_id("active", 42)

    mock_cursor.execute.assert_called_once_with("UPDATE users SET status = %s WHERE id = %s", ("active", 42))
    mock_cursor.close.assert_called_once()
    mock_conn.commit.assert_called_once()


def test_sync_database_non_matching_method():
    mock_conn = MagicMock()
    db = Database(mock_conn)

    # Calling an invalid method name shouldn't execute anything and return None
    result = db.invalid_method_name()
    assert result is None
    mock_conn.cursor.assert_not_called()


@pytest.mark.asyncio
async def test_async_database_select_multiple():
    mock_conn = MagicMock()
    mock_cursor = AsyncMock()
    
    # Setup mock_conn.cursor() to return an async context manager yielding mock_cursor
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor
    mock_cursor.execute.return_value = None
    mock_cursor.fetchall.return_value = [("Alice", "alice@example.com"), ("Bob", "bob@example.com")]

    db = Database(mock_conn, is_async=True)
    result = await db.get_users()

    mock_conn.cursor.assert_called_once()
    mock_cursor.execute.assert_called_once_with("SELECT * FROM users", ())
    mock_cursor.fetchall.assert_called_once()
    assert result == [("Alice", "alice@example.com"), ("Bob", "bob@example.com")]


@pytest.mark.asyncio
async def test_async_database_select_single():
    mock_conn = MagicMock()
    mock_cursor = AsyncMock()
    
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor
    mock_cursor.execute.return_value = None
    mock_cursor.fetchall.return_value = [("Alice", "alice@example.com")]

    db = Database(mock_conn)
    result = await db.async_get_user_by_id(1)

    mock_cursor.execute.assert_called_once_with("SELECT * FROM users WHERE id = %s", (1,))
    mock_cursor.fetchall.assert_called_once()
    assert result == ("Alice", "alice@example.com")


@pytest.mark.asyncio
async def test_async_database_insert():
    mock_conn = MagicMock()
    mock_cursor = AsyncMock()
    
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor
    mock_cursor.execute.return_value = "inserted_id_or_result"
    mock_conn.commit = AsyncMock()

    db = Database(mock_conn, is_async=True)
    result = await db.add_user_columns_name_and_email("Alice", "alice@example.com")

    mock_cursor.execute.assert_called_once_with("INSERT INTO users ( name,email ) VALUES (%s,%s)", ("Alice", "alice@example.com"))
    mock_conn.commit.assert_awaited_once()
    assert result == "inserted_id_or_result"
