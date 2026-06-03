import os
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from urllib.parse import unquote, urlparse

import pytest

from guess import Database

MYSQL_DSN = os.getenv("GUESS_WHAT_MYSQL_DSN")

pytestmark = pytest.mark.skipif(
    not MYSQL_DSN,
    reason="set GUESS_WHAT_MYSQL_DSN to run MySQL/MariaDB integration tests",
)

mysql_connector = pytest.importorskip("mysql.connector")


class EventStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass
class MysqlEvent:
    name: str
    starts_at: datetime
    event_date: date
    price: Decimal
    event_uuid: str
    is_public: bool
    notes: str | None
    payload: bytes
    status: EventStatus


def parse_mysql_dsn(dsn: str) -> dict[str, object]:
    parsed = urlparse(dsn)
    if parsed.scheme not in {"mysql", "mariadb"}:
        raise ValueError("GUESS_WHAT_MYSQL_DSN must start with mysql:// or mariadb://")

    config: dict[str, object] = {
        "host": parsed.hostname or "localhost",
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "database": parsed.path.lstrip("/"),
    }
    if parsed.port:
        config["port"] = parsed.port
    return config


@pytest.fixture()
def conn():
    connection = mysql_connector.connect(**parse_mysql_dsn(MYSQL_DSN))
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture()
def events_table(conn):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS guess_what_mysql_events")
        cur.execute(
            """
            CREATE TABLE guess_what_mysql_events (
                name VARCHAR(255) PRIMARY KEY,
                starts_at DATETIME NOT NULL,
                event_date DATE NOT NULL,
                price DECIMAL(10, 2) NOT NULL,
                event_uuid CHAR(36) NOT NULL,
                is_public BOOLEAN NOT NULL,
                notes TEXT,
                payload BLOB NOT NULL,
                status ENUM('active', 'archived') NOT NULL
            )
            """
        )
    conn.commit()
    try:
        yield
    finally:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS guess_what_mysql_events")
        conn.commit()


def test_mysql_database_handles_common_scalar_values(conn, events_table):
    db = Database(conn)

    db.add_guess_what_mysql_event(MysqlEvent(
        name="Launch",
        starts_at=datetime(2026, 6, 2, 14, 30, 45),
        event_date=date(2026, 6, 2),
        price=Decimal("19.99"),
        event_uuid="12345678-1234-5678-1234-567812345678",
        is_public=True,
        notes=None,
        payload=b"hello",
        status=EventStatus.ACTIVE,
    ))

    row = db.get_guess_what_mysql_event_by_name[dict]("Launch")

    assert row["name"] == "Launch"
    assert row["starts_at"] == datetime(2026, 6, 2, 14, 30, 45)
    assert row["event_date"] == date(2026, 6, 2)
    assert row["price"] == Decimal("19.99")
    assert row["event_uuid"] == "12345678-1234-5678-1234-567812345678"
    assert bool(row["is_public"]) is True
    assert row["notes"] is None
    assert bytes(row["payload"]) == b"hello"
    assert row["status"] == "active"

    db.set_guess_what_mysql_event_columns_notes_and_status_by_name(
        {"notes": "published", "status": EventStatus.ARCHIVED},
        "Launch",
    )

    assert db.get_guess_what_mysql_event_columns_notes_and_status_by_name("Launch") == (
        "published",
        "archived",
    )
