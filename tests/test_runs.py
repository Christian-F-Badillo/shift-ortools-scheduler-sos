"""Section 5 — Schedule runs and manual overrides."""
from datetime import timedelta

from tests.conftest import WEEK, add_full_week_requirements


# ── POST /runs ─────────────────────────────────────────────────────────────────

def test_create_run_success(client, seed):
    add_full_week_requirements(client, seed)
    r = client.post("/runs", json={"week_start": WEEK.isoformat()})
    assert r.status_code == 201
    data = r.json()
    assert data["feasibility"] in ("full", "partial")
    assert data["assignments_count"] > 0
    assert isinstance(data["run_id"], int)
    assert isinstance(data["solve_time_ms"], int)
    assert isinstance(data["relaxed_constraints"], list)


def test_create_run_full_feasibility(client, seed):
    """With enough employees and relaxed limits, solver should be fully feasible."""
    add_full_week_requirements(client, seed)
    data = client.post("/runs", json={"week_start": WEEK.isoformat()}).json()
    # With 6 employees and min=2 / max=4 per shift, full feasibility is expected
    assert data["feasibility"] == "full"
    assert data["relaxed_constraints"] == []


def test_create_run_week_not_monday_returns_422(client, seed):
    r = client.post("/runs", json={"week_start": "2025-02-04"})   # Tuesday
    assert r.status_code == 422


def test_create_run_infeasible_returns_422(client, seed):
    """min_staff > total employees → hard constraints conflict."""
    for day in range(7):
        for sid in [seed["morning_id"], seed["night_id"]]:
            client.put(
                "/requirements/shifts",
                params={"week_start": WEEK.isoformat(), "shift_id": sid, "day_of_week": day},
                json={"min_staff": 10},   # impossible: only 6 employees
            )
    r = client.post("/runs", json={"week_start": WEEK.isoformat()})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "run_id" in detail
    assert "message" in detail


def test_create_run_infeasible_still_persisted(client, seed):
    """Even a failed solve should persist a run record."""
    for day in range(7):
        for sid in [seed["morning_id"], seed["night_id"]]:
            client.put(
                "/requirements/shifts",
                params={"week_start": WEEK.isoformat(), "shift_id": sid, "day_of_week": day},
                json={"min_staff": 10},
            )
    r422 = client.post("/runs", json={"week_start": WEEK.isoformat()})
    run_id = r422.json()["detail"]["run_id"]
    rget = client.get(f"/runs/{run_id}")
    assert rget.status_code == 200
    assert rget.json()["feasibility"] == "none"


# ── GET /runs ──────────────────────────────────────────────────────────────────

def test_list_runs_empty(client, seed):
    assert client.get("/runs").json() == []


def test_list_runs_after_solve(client, seed):
    add_full_week_requirements(client, seed)
    client.post("/runs", json={"week_start": WEEK.isoformat()})
    runs = client.get("/runs").json()
    assert len(runs) == 1
    assert runs[0]["status"] == "done"


def test_list_runs_filter_by_week(client, seed):
    add_full_week_requirements(client, seed)
    client.post("/runs", json={"week_start": WEEK.isoformat()})

    r = client.get("/runs", params={"week_start": WEEK.isoformat()})
    assert len(r.json()) == 1

    r2 = client.get("/runs", params={"week_start": "2025-03-03"})
    assert r2.json() == []


def test_list_runs_limit(client, seed):
    add_full_week_requirements(client, seed)
    # Create 3 runs for different weeks
    for offset in range(3):
        w = WEEK + timedelta(weeks=offset)
        add_full_week_requirements(client, seed, week=w)
        client.post("/runs", json={"week_start": w.isoformat()})

    r = client.get("/runs", params={"limit": 2})
    assert len(r.json()) == 2


# ── GET /runs/{id} ─────────────────────────────────────────────────────────────

def test_get_run_by_id(client, seed):
    add_full_week_requirements(client, seed)
    run_id = client.post("/runs", json={"week_start": WEEK.isoformat()}).json()["run_id"]

    r = client.get(f"/runs/{run_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == run_id
    assert data["status"]          == "done"
    assert data["week_start_date"] == WEEK.isoformat()
    assert data["solve_time_ms"]   is not None


def test_get_run_not_found(client):
    assert client.get("/runs/9999").status_code == 404


# ── GET /runs/{id}/assignments ─────────────────────────────────────────────────

def test_get_run_assignments(client, seed):
    add_full_week_requirements(client, seed)
    run_id = client.post("/runs", json={"week_start": WEEK.isoformat()}).json()["run_id"]

    r = client.get(f"/runs/{run_id}/assignments")
    assert r.status_code == 200
    assignments = r.json()
    assert len(assignments) > 0
    for a in assignments:
        assert "employee_id" in a
        assert "shift_id"    in a
        assert "date"        in a
        assert a["is_override"] is False


def test_get_run_assignments_dates_in_range(client, seed):
    add_full_week_requirements(client, seed)
    run_id = client.post("/runs", json={"week_start": WEEK.isoformat()}).json()["run_id"]

    from datetime import date
    from tests.conftest import WEEK as W
    week_end = W + timedelta(days=6)
    for a in client.get(f"/runs/{run_id}/assignments").json():
        d = date.fromisoformat(a["date"])
        assert W <= d <= week_end


def test_get_run_assignments_not_found(client):
    assert client.get("/runs/9999/assignments").status_code == 404


# ── PATCH /runs/{id}/assignments/{id} ─────────────────────────────────────────

def test_override_assignment(client, seed):
    add_full_week_requirements(client, seed)
    run_id = client.post("/runs", json={"week_start": WEEK.isoformat()}).json()["run_id"]

    a = client.get(f"/runs/{run_id}/assignments").json()[0]
    other = seed["night_id"] if a["shift_id"] == seed["morning_id"] else seed["morning_id"]

    r = client.patch(
        f"/runs/{run_id}/assignments/{a['id']}",
        json={"new_shift_id": other, "actor": "manager_test"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["is_override"] is True
    assert data["shift_id"]    == other


def test_override_assignment_no_actor(client, seed):
    add_full_week_requirements(client, seed)
    run_id = client.post("/runs", json={"week_start": WEEK.isoformat()}).json()["run_id"]
    a = client.get(f"/runs/{run_id}/assignments").json()[0]
    other = seed["night_id"] if a["shift_id"] == seed["morning_id"] else seed["morning_id"]

    r = client.patch(f"/runs/{run_id}/assignments/{a['id']}", json={"new_shift_id": other})
    assert r.status_code == 200


def test_override_assignment_run_not_found(client, seed):
    r = client.patch(
        "/runs/9999/assignments/1",
        json={"new_shift_id": seed["morning_id"]},
    )
    assert r.status_code == 404


def test_override_assignment_not_found(client, seed):
    add_full_week_requirements(client, seed)
    run_id = client.post("/runs", json={"week_start": WEEK.isoformat()}).json()["run_id"]

    r = client.patch(
        f"/runs/{run_id}/assignments/9999",
        json={"new_shift_id": seed["morning_id"]},
    )
    assert r.status_code == 404


def test_override_assignment_wrong_run_returns_409(client, seed):
    """Trying to override via a run that does not own the assignment → 409."""
    add_full_week_requirements(client, seed)
    run1_id = client.post("/runs", json={"week_start": WEEK.isoformat()}).json()["run_id"]

    next_week = WEEK + timedelta(weeks=1)
    add_full_week_requirements(client, seed, week=next_week)
    run2_id = client.post("/runs", json={"week_start": next_week.isoformat()}).json()["run_id"]

    # An assignment from run1 — try to patch it via run2
    a_id = client.get(f"/runs/{run1_id}/assignments").json()[0]["id"]
    r = client.patch(
        f"/runs/{run2_id}/assignments/{a_id}",
        json={"new_shift_id": seed["morning_id"]},
    )
    assert r.status_code == 409


def test_override_vacation_day_returns_409(client, seed):
    """Cannot override to a day where the employee is on vacation."""
    add_full_week_requirements(client, seed)
    run_id = client.post("/runs", json={"week_start": WEEK.isoformat()}).json()["run_id"]

    # Find an assignment for Alice and mark her as vacation on that date
    assignments = client.get(f"/runs/{run_id}/assignments").json()
    alice_a = next((a for a in assignments if a["employee_id"] == seed["alice_id"]), None)
    if alice_a is None:
        return   # Alice may not have been scheduled; skip

    client.put(
        f"/employees/{seed['alice_id']}/availability/{alice_a['date']}",
        json={"status": "VACATION"},
    )
    other = seed["night_id"] if alice_a["shift_id"] == seed["morning_id"] else seed["morning_id"]
    r = client.patch(
        f"/runs/{run_id}/assignments/{alice_a['id']}",
        json={"new_shift_id": other},
    )
    assert r.status_code == 409
