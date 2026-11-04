"""Section 2 — Employee management."""


def test_list_employees_empty(client):
    r = client.get("/employees")
    assert r.status_code == 200
    assert r.json() == []


def test_list_employees(client, seed):
    r = client.get("/employees")
    assert r.status_code == 200
    assert len(r.json()) == 6


def test_list_employees_only_active_by_default(client, seed):
    client.patch(f"/employees/{seed['alice_id']}", json={"active": False})
    active = client.get("/employees").json()
    assert len(active) == 5
    assert all(e["active"] for e in active)


def test_list_employees_include_inactive(client, seed):
    client.patch(f"/employees/{seed['alice_id']}", json={"active": False})
    all_emps = client.get("/employees", params={"include_inactive": "true"}).json()
    assert len(all_emps) == 6


def test_create_employee_minimal(client, seed):
    r = client.post("/employees", json={"name": "Nuevo", "role_id": seed["tecnico_id"]})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Nuevo"
    assert data["role_id"] == seed["tecnico_id"]
    assert data["area_id"] is None
    assert data["active"] is True
    assert "id" in data


def test_create_employee_with_area(client, seed):
    r = client.post("/employees", json={
        "name": "Con Área",
        "role_id": seed["soporte_id"],
        "area_id": seed["area_id"],
    })
    assert r.status_code == 201
    assert r.json()["area_id"] == seed["area_id"]


def test_create_employee_persists(client, seed):
    client.post("/employees", json={"name": "Persistido", "role_id": seed["tecnico_id"]})
    names = [e["name"] for e in client.get("/employees").json()]
    assert "Persistido" in names


def test_patch_employee_name(client, seed):
    r = client.patch(f"/employees/{seed['alice_id']}", json={"name": "Alicia"})
    assert r.status_code == 200
    assert r.json()["name"] == "Alicia"


def test_patch_employee_role(client, seed):
    r = client.patch(f"/employees/{seed['alice_id']}", json={"role_id": seed["soporte_id"]})
    assert r.status_code == 200
    assert r.json()["role_id"] == seed["soporte_id"]


def test_patch_employee_deactivate(client, seed):
    r = client.patch(f"/employees/{seed['alice_id']}", json={"active": False})
    assert r.status_code == 200
    assert r.json()["active"] is False


def test_patch_employee_not_found(client):
    r = client.patch("/employees/9999", json={"name": "X"})
    assert r.status_code == 404


def test_patch_employee_empty_body_is_noop(client, seed):
    before = client.get("/employees").json()
    alice_before = next(e for e in before if e["id"] == seed["alice_id"])
    r = client.patch(f"/employees/{seed['alice_id']}", json={})
    assert r.status_code == 200
    assert r.json()["name"] == alice_before["name"]
