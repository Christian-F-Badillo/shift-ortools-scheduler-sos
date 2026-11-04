"""Section 3 — Availability / leave management."""

DATE = "2025-02-05"


def test_set_vacation(client, seed):
    r = client.put(
        f"/employees/{seed['alice_id']}/availability/{DATE}",
        json={"status": "VACATION"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"]      == "VACATION"
    assert data["employee_id"] == seed["alice_id"]
    assert data["date"]        == DATE


def test_set_sick(client, seed):
    r = client.put(
        f"/employees/{seed['alice_id']}/availability/{DATE}",
        json={"status": "SICK"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "SICK"


def test_set_day_off(client, seed):
    r = client.put(
        f"/employees/{seed['alice_id']}/availability/{DATE}",
        json={"status": "DAY_OFF"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "DAY_OFF"


def test_set_available_explicit(client, seed):
    """Setting AVAILABLE is valid even if it's the default."""
    r = client.put(
        f"/employees/{seed['alice_id']}/availability/{DATE}",
        json={"status": "AVAILABLE"},
    )
    assert r.status_code == 200


def test_set_availability_updates_existing(client, seed):
    client.put(
        f"/employees/{seed['alice_id']}/availability/{DATE}",
        json={"status": "VACATION"},
    )
    r = client.put(
        f"/employees/{seed['alice_id']}/availability/{DATE}",
        json={"status": "SICK"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "SICK"


def test_set_availability_employee_not_found(client):
    r = client.put(
        f"/employees/9999/availability/{DATE}",
        json={"status": "VACATION"},
    )
    assert r.status_code == 404


def test_delete_availability(client, seed):
    client.put(
        f"/employees/{seed['alice_id']}/availability/{DATE}",
        json={"status": "VACATION"},
    )
    r = client.delete(f"/employees/{seed['alice_id']}/availability/{DATE}")
    assert r.status_code == 204


def test_delete_availability_not_found(client, seed):
    r = client.delete(f"/employees/{seed['alice_id']}/availability/{DATE}")
    assert r.status_code == 404


def test_delete_availability_employee_not_found(client):
    r = client.delete(f"/employees/9999/availability/{DATE}")
    assert r.status_code == 404
