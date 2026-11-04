"""Section 7 — Soft-constraint configuration."""


def test_get_constraints_empty(client):
    r = client.get("/config/constraints")
    assert r.status_code == 200
    assert r.json() == []


def test_get_constraints(client, seed):
    r = client.get("/config/constraints")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    ids = {c["id"] for c in data}
    assert ids == {"max_staff", "max_role", "no_night_morning"}


def test_get_constraints_shape(client, seed):
    for c in client.get("/config/constraints").json():
        assert set(c.keys()) >= {"id", "description", "priority", "weight"}


def test_patch_constraint_weight(client, seed):
    r = client.patch("/config/constraints/max_staff", json={"weight": 20})
    assert r.status_code == 200
    data = r.json()
    assert data["id"]     == "max_staff"
    assert data["weight"] == 20


def test_patch_constraint_priority(client, seed):
    r = client.patch("/config/constraints/no_night_morning", json={"priority": 9})
    assert r.status_code == 200
    assert r.json()["priority"] == 9


def test_patch_constraint_both_fields(client, seed):
    r = client.patch("/config/constraints/max_role", json={"weight": 8, "priority": 6})
    assert r.status_code == 200
    data = r.json()
    assert data["weight"]   == 8
    assert data["priority"] == 6


def test_patch_constraint_persists(client, seed):
    client.patch("/config/constraints/max_staff", json={"weight": 99})
    all_constraints = client.get("/config/constraints").json()
    updated = next(c for c in all_constraints if c["id"] == "max_staff")
    assert updated["weight"] == 99


def test_patch_constraint_not_found(client):
    r = client.patch("/config/constraints/nonexistent", json={"weight": 10})
    assert r.status_code == 404


def test_patch_constraint_empty_body_is_noop(client, seed):
    before = next(
        c for c in client.get("/config/constraints").json()
        if c["id"] == "max_staff"
    )
    r = client.patch("/config/constraints/max_staff", json={})
    assert r.status_code == 200
    assert r.json()["weight"] == before["weight"]
