import os
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

import pytest

from guess import Database

POSTGRES_DSN = os.getenv("GUESS_WHAT_POSTGRES_DSN")

pytestmark = pytest.mark.skipif(
    not POSTGRES_DSN,
    reason="set GUESS_WHAT_POSTGRES_DSN to run PostgreSQL integration tests",
)

psycopg2 = pytest.importorskip("psycopg2")
psycopg2_extras = pytest.importorskip("psycopg2.extras")


class EventStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass
class PgEvent:
    name: str
    starts_at: datetime
    event_date: date
    event_time: time
    price: Decimal
    event_uuid: UUID
    is_public: bool
    notes: str | None
    payload: bytes
    status: EventStatus


@dataclass
class PgArrayEvent:
    name: str
    tags: list[str]
    scores: list[int]
    participant_ids: list[UUID]
    prices: list[Decimal]
    empty_tags: list[str]
    optional_tags: list[str] | None


@pytest.fixture()
def conn():
    connection = psycopg2.connect(POSTGRES_DSN)
    psycopg2_extras.register_uuid(conn_or_curs=connection)
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture()
def events_table(conn):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS guess_what_events")
        cur.execute(
            """
            CREATE TABLE guess_what_events (
                name TEXT PRIMARY KEY,
                starts_at TIMESTAMP NOT NULL,
                event_date DATE NOT NULL,
                event_time TIME NOT NULL,
                price NUMERIC NOT NULL,
                event_uuid UUID NOT NULL,
                is_public BOOLEAN NOT NULL,
                notes TEXT,
                payload BYTEA NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
    conn.commit()
    try:
        yield
    finally:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS guess_what_events")
        conn.commit()


@pytest.fixture()
def enum_table(conn):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS guess_what_enum_events")
        cur.execute("DROP TYPE IF EXISTS guess_what_event_status")
        cur.execute("CREATE TYPE guess_what_event_status AS ENUM ('active', 'archived')")
        cur.execute(
            """
            CREATE TABLE guess_what_enum_events (
                name TEXT PRIMARY KEY,
                status guess_what_event_status NOT NULL
            )
            """
        )
    conn.commit()
    try:
        yield
    finally:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS guess_what_enum_events")
            cur.execute("DROP TYPE IF EXISTS guess_what_event_status")
        conn.commit()


@pytest.fixture()
def array_table(conn):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS guess_what_array_events")
        cur.execute(
            """
            CREATE TABLE guess_what_array_events (
                name TEXT PRIMARY KEY,
                tags TEXT[] NOT NULL,
                scores INTEGER[] NOT NULL,
                participant_ids UUID[] NOT NULL,
                prices NUMERIC[] NOT NULL,
                empty_tags TEXT[] NOT NULL,
                optional_tags TEXT[]
            )
            """
        )
    conn.commit()
    try:
        yield
    finally:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS guess_what_array_events")
        conn.commit()


def test_postgres_database_handles_common_scalar_values(conn, events_table):
    db = Database(conn)
    event_uuid = UUID("12345678-1234-5678-1234-567812345678")

    db.add_guess_what_event(PgEvent(
        name="Launch",
        starts_at=datetime(2026, 6, 2, 14, 30, 45),
        event_date=date(2026, 6, 2),
        event_time=time(14, 30, 45),
        price=Decimal("19.99"),
        event_uuid=event_uuid,
        is_public=True,
        notes=None,
        payload=b"hello",
        status=EventStatus.ACTIVE,
    ))

    row = db.get_guess_what_event_by_name[dict]("Launch")

    assert row["name"] == "Launch"
    assert row["starts_at"] == datetime(2026, 6, 2, 14, 30, 45)
    assert row["event_date"] == date(2026, 6, 2)
    assert row["event_time"] == time(14, 30, 45)
    assert row["price"] == Decimal("19.99")
    assert row["event_uuid"] == event_uuid
    assert row["is_public"] is True
    assert row["notes"] is None
    assert bytes(row["payload"]) == b"hello"
    assert row["status"] == EventStatus.ACTIVE

    db.set_guess_what_event_columns_notes_by_name({"notes": "published"}, "Launch")

    assert db.get_guess_what_event_columns_notes_by_name("Launch") == ("published",)


def test_postgres_database_handles_native_enum_values(conn, enum_table):
    db = Database(conn)

    db.add_guess_what_enum_event({
        "name": "Launch",
        "status": EventStatus.ACTIVE,
    })

    assert db.get_guess_what_enum_event_by_name[dict]("Launch") == {
        "name": "Launch",
        "status": "active",
    }

    db.set_guess_what_enum_event_columns_status_by_name(
        {"status": EventStatus.ARCHIVED},
        "Launch",
    )

    assert db.get_guess_what_enum_event_columns_status_by_name("Launch") == ("archived",)


def test_postgres_database_handles_array_values(conn, array_table):
    db = Database(conn)
    first_id = UUID("12345678-1234-5678-1234-567812345678")
    second_id = UUID("87654321-4321-8765-4321-876543218765")

    db.add_guess_what_array_event(PgArrayEvent(
        name="Launch",
        tags=["python", "database"],
        scores=[10, 20],
        participant_ids=[first_id, second_id],
        prices=[Decimal("19.99"), Decimal("25.50")],
        empty_tags=[],
        optional_tags=None,
    ))

    row = db.get_guess_what_array_event_by_name[dict]("Launch")

    assert row == {
        "name": "Launch",
        "tags": ["python", "database"],
        "scores": [10, 20],
        "participant_ids": [first_id, second_id],
        "prices": [Decimal("19.99"), Decimal("25.50")],
        "empty_tags": [],
        "optional_tags": None,
    }

    db.set_guess_what_array_event_columns_tags_and_scores_by_name(
        {
            "tags": ["released", "stable"],
            "scores": [30, 40],
        },
        "Launch",
    )

    assert db.get_guess_what_array_event_columns_tags_and_scores_by_name("Launch") == (
        ["released", "stable"],
        [30, 40],
    )
