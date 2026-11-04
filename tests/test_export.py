"""Section 6 — Schedule export (CSV and XLSX)."""
from tests.conftest import WEEK, add_full_week_requirements


def _run_id(client, seed) -> int:
    add_full_week_requirements(client, seed)
    return client.post("/runs", json={"week_start": WEEK.isoformat()}).json()["run_id"]


# ── CSV ────────────────────────────────────────────────────────────────────────

def test_export_csv_status(client, seed):
    rid = _run_id(client, seed)
    r = client.get(f"/runs/{rid}/export", params={"format": "csv"})
    assert r.status_code == 200


def test_export_csv_content_type(client, seed):
    rid = _run_id(client, seed)
    r = client.get(f"/runs/{rid}/export", params={"format": "csv"})
    assert "text/csv" in r.headers["content-type"]


def test_export_csv_has_header_row(client, seed):
    rid = _run_id(client, seed)
    text = client.get(f"/runs/{rid}/export", params={"format": "csv"}).text
    header = text.strip().split("\n")[0].strip()
    expected = {"Fecha", "Día", "Turno", "Hora_inicio", "Empleado", "Rol", "Área", "Override"}
    assert expected == set(header.split(","))


def test_export_csv_has_data_rows(client, seed):
    rid = _run_id(client, seed)
    lines = client.get(f"/runs/{rid}/export", params={"format": "csv"}).text.strip().split("\n")
    assert len(lines) > 1   # header + at least one assignment


def test_export_csv_default_format(client, seed):
    rid = _run_id(client, seed)
    r = client.get(f"/runs/{rid}/export")   # default format = csv
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]


def test_export_csv_content_disposition(client, seed):
    rid = _run_id(client, seed)
    r = client.get(f"/runs/{rid}/export", params={"format": "csv"})
    cd = r.headers.get("content-disposition", "")
    assert f"schedule_{rid}.csv" in cd


# ── XLSX ───────────────────────────────────────────────────────────────────────

def test_export_xlsx_status(client, seed):
    rid = _run_id(client, seed)
    r = client.get(f"/runs/{rid}/export", params={"format": "xlsx"})
    assert r.status_code == 200


def test_export_xlsx_content_type(client, seed):
    rid = _run_id(client, seed)
    r = client.get(f"/runs/{rid}/export", params={"format": "xlsx"})
    assert "spreadsheetml" in r.headers["content-type"]


def test_export_xlsx_is_valid_zip(client, seed):
    """XLSX files are ZIP archives; check magic bytes."""
    rid = _run_id(client, seed)
    r = client.get(f"/runs/{rid}/export", params={"format": "xlsx"})
    assert r.content[:4] == b"PK\x03\x04"


def test_export_xlsx_readable_by_openpyxl(client, seed):
    import io, openpyxl
    rid = _run_id(client, seed)
    r = client.get(f"/runs/{rid}/export", params={"format": "xlsx"})
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert len(wb.sheetnames) == 7   # one sheet per day of week


def test_export_xlsx_content_disposition(client, seed):
    rid = _run_id(client, seed)
    r = client.get(f"/runs/{rid}/export", params={"format": "xlsx"})
    assert f"schedule_{rid}.xlsx" in r.headers.get("content-disposition", "")


# ── Error cases ────────────────────────────────────────────────────────────────

def test_export_invalid_format(client, seed):
    rid = _run_id(client, seed)
    r = client.get(f"/runs/{rid}/export", params={"format": "pdf"})
    assert r.status_code == 422


def test_export_run_not_found(client):
    r = client.get("/runs/9999/export", params={"format": "csv"})
    assert r.status_code == 404
