"""Section 4 — Shift and role requirements."""
from tests.conftest import WEEK, add_full_week_requirements


# ── GET /requirements ──────────────────────────────────────────────────────────

def test_get_requirements_empty(client, seed):
    r = client.get("/requirements", params={"week_start": WEEK.isoformat()})
    assert r.status_code == 200
    data = r.json()
    assert data["week_start_date"]    == WEEK.isoformat()
    assert data["shift_requirements"] == []
    assert data["role_requirements"]  == []


def test_get_requirements_after_seed(client, seed):
    add_full_week_requirements(client, seed)
    r = client.get("/requirements", params={"week_start": WEEK.isoformat()})
    assert r.status_code == 200
    data = r.json()
    assert len(data["shift_requirements"]) == 14   # 7 days × 2 shifts
    assert len(data["role_requirements"])  == 14


def test_get_requirements_different_week_is_empty(client, seed):
    add_full_week_requirements(client, seed)
    r = client.get("/requirements", params={"week_start": "2025-03-03"})
    assert r.json()["shift_requirements"] == []


# ── PUT /requirements/shifts ───────────────────────────────────────────────────

def test_upsert_shift_req_basic(client, seed):
    r = client.put(
        "/requirements/shifts",
        params={"week_start": WEEK.isoformat(), "shift_id": seed["morning_id"], "day_of_week": 0},
        json={"min_staff": 2, "max_staff": 5},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["min_staff"] == 2
    assert data["max_staff"] == 5
    assert data["day_of_week"] == 0


def test_upsert_shift_req_no_max(client, seed):
    r = client.put(
        "/requirements/shifts",
        params={"week_start": WEEK.isoformat(), "shift_id": seed["morning_id"], "day_of_week": 1},
        json={"min_staff": 1},
    )
    assert r.status_code == 200
    assert r.json()["max_staff"] is None


def test_upsert_shift_req_idempotent(client, seed):
    params = {"week_start": WEEK.isoformat(), "shift_id": seed["morning_id"], "day_of_week": 0}
    client.put("/requirements/shifts", params=params, json={"min_staff": 2})
    r = client.put("/requirements/shifts", params=params, json={"min_staff": 3})
    assert r.status_code == 200
    assert r.json()["min_staff"] == 3


def test_upsert_shift_req_shift_not_found(client, seed):
    r = client.put(
        "/requirements/shifts",
        params={"week_start": WEEK.isoformat(), "shift_id": 9999, "day_of_week": 0},
        json={"min_staff": 2},
    )
    assert r.status_code == 404


def test_upsert_shift_req_invalid_day(client, seed):
    r = client.put(
        "/requirements/shifts",
        params={"week_start": WEEK.isoformat(), "shift_id": seed["morning_id"], "day_of_week": 7},
        json={"min_staff": 2},
    )
    assert r.status_code == 422   # FastAPI validation: day_of_week must be ≤ 6


# ── PUT /requirements/roles ────────────────────────────────────────────────────

def test_upsert_role_req_by_role(client, seed):
    r = client.put(
        "/requirements/roles",
        params={"week_start": WEEK.isoformat(), "shift_id": seed["morning_id"], "day_of_week": 0},
        json={"role_id": seed["tecnico_id"], "min_count": 1, "max_count": 3},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["role_id"]   == seed["tecnico_id"]
    assert data["min_count"] == 1
    assert data["max_count"] == 3


def test_upsert_role_req_by_area(client, seed):
    r = client.put(
        "/requirements/roles",
        params={"week_start": WEEK.isoformat(), "shift_id": seed["morning_id"], "day_of_week": 0},
        json={"area_id": seed["area_id"], "min_count": 1},
    )
    assert r.status_code == 200
    assert r.json()["area_id"] == seed["area_id"]


def test_upsert_role_req_no_role_or_area_returns_409(client, seed):
    r = client.put(
        "/requirements/roles",
        params={"week_start": WEEK.isoformat(), "shift_id": seed["morning_id"], "day_of_week": 0},
        json={"min_count": 1},
    )
    assert r.status_code == 409


def test_upsert_role_req_idempotent(client, seed):
    params = {"week_start": WEEK.isoformat(), "shift_id": seed["morning_id"], "day_of_week": 0}
    client.put("/requirements/roles", params=params, json={"role_id": seed["tecnico_id"], "min_count": 1})
    r = client.put("/requirements/roles", params=params, json={"role_id": seed["tecnico_id"], "min_count": 2})
    assert r.status_code == 200
    assert r.json()["min_count"] == 2
