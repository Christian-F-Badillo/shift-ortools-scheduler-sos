"""Section 1 — Catalogs (read-only)."""


def test_get_roles_empty(client):
    r = client.get("/roles")
    assert r.status_code == 200
    assert r.json() == []


def test_get_roles(client, seed):
    r = client.get("/roles")
    assert r.status_code == 200
    names = {item["name"] for item in r.json()}
    assert "Técnico" in names
    assert "Soporte" in names


def test_get_roles_shape(client, seed):
    for role in client.get("/roles").json():
        assert set(role.keys()) >= {"id", "name"}


def test_get_areas_empty(client):
    assert client.get("/areas").json() == []


def test_get_areas(client, seed):
    r = client.get("/areas")
    assert r.status_code == 200
    assert any(a["name"] == "Operaciones" for a in r.json())


def test_get_shifts_empty(client):
    assert client.get("/shifts").json() == []


def test_get_shifts(client, seed):
    r = client.get("/shifts")
    assert r.status_code == 200
    names = {s["name"] for s in r.json()}
    assert names == {"MORNING", "NIGHT"}


def test_get_shifts_shape(client, seed):
    for shift in client.get("/shifts").json():
        assert shift["duration_hours"] == 9
        assert "start_time" in shift
