"""
Shared pytest fixtures and test helpers.

Fixture hierarchy:
  engine → (client, seed)   ← both depend on the same engine
  tests use:  def test_foo(client, seed)

StaticPool ensures that every SQLAlchemy session on the same engine
shares the same in-memory SQLite connection, so seed data written by
one session is visible to the client's sessions.
"""

from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api import app
from backend import models
from backend.database import Base, get_db

# Monday used as the reference week in all tests
WEEK = date(2025, 2, 3)


# ── Core fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture()
def client(engine):
    """TestClient with the in-memory test database injected."""
    Session = sessionmaker(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def seed(engine) -> dict:
    """
    Seed catalog data: 2 roles, 1 area, 2 shifts, 3 soft-constraint defs,
    6 employees.  Returns a dict of entity IDs for use in tests.
    """
    Session = sessionmaker(bind=engine)
    db = Session()

    tecnico = models.Role(name="Técnico")
    soporte = models.Role(name="Soporte")
    db.add_all([tecnico, soporte])
    db.flush()

    area = models.Area(name="Operaciones")
    db.add(area)
    db.flush()

    morning = models.Shift(name="MORNING", start_time=time(7, 0), duration_hours=9)
    night = models.Shift(name="NIGHT", start_time=time(15, 0), duration_hours=9)
    db.add_all([morning, night])
    db.flush()

    db.add_all(
        [
            models.SoftConstraintDef(
                id="max_staff",
                description="Máximo de personal por turno",
                priority=3,
                weight=5,
            ),
            models.SoftConstraintDef(
                id="max_role",
                description="Máximo por rol/área por turno",
                priority=4,
                weight=4,
            ),
            models.SoftConstraintDef(
                id="no_night_morning",
                description="No turno noche seguido de mañana",
                priority=7,
                weight=10,
            ),
        ]
    )

    emps = [
        models.Employee(name="Alice", role_id=tecnico.id),  # 0
        models.Employee(name="Bob", role_id=tecnico.id),  # 1
        models.Employee(name="Carlos", role_id=soporte.id),  # 2
        models.Employee(name="Diana", role_id=soporte.id),  # 3
        models.Employee(name="Eduardo", role_id=tecnico.id),  # 4
        models.Employee(name="Fiona", role_id=soporte.id),  # 5
    ]
    db.add_all(emps)
    db.commit()

    ids = {
        "tecnico_id": tecnico.id,
        "soporte_id": soporte.id,
        "area_id": area.id,
        "morning_id": morning.id,
        "night_id": night.id,
        "alice_id": emps[0].id,
        "bob_id": emps[1].id,
        "carlos_id": emps[2].id,
        "diana_id": emps[3].id,
        "eduardo_id": emps[4].id,
        "fiona_id": emps[5].id,
    }
    db.close()
    return ids


# ── Test helpers ───────────────────────────────────────────────────────────────


def add_full_week_requirements(
    client: TestClient,
    seed: dict,
    week: date = WEEK,
) -> None:
    """
    Add shift requirements for every day of the week via the API.
    min_staff=2, max_staff=4, with at least 1 Técnico per shift.
    """
    for day in range(7):
        for shift_id in [seed["morning_id"], seed["night_id"]]:
            client.put(
                "/requirements/shifts",
                params={
                    "week_start": week.isoformat(),
                    "shift_id": shift_id,
                    "day_of_week": day,
                },
                json={"min_staff": 2, "max_staff": 4},
            )
            client.put(
                "/requirements/roles",
                params={
                    "week_start": week.isoformat(),
                    "shift_id": shift_id,
                    "day_of_week": day,
                },
                json={"role_id": seed["tecnico_id"], "min_count": 1},
            )
