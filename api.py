"""
FastAPI application.

Error mapping:
  NotFoundError  → 404
  ConflictError  → 409
  Pydantic       → 422 (automatic)
  InfeasibleRun  → 422 (manual, inside create_run)
"""

from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from backend import service
from backend.database import Base, engine, get_db
from backend.exceptions import ConflictError, InfeasibleError, NotFoundError
from backend.schemas import (
    AreaRead,
    CatalogCreate,
    AssignmentOverride,
    AssignmentRead,
    AvailabilityRead,
    AvailabilitySet,
    EmployeeCreate,
    EmployeeRead,
    EmployeeUpdate,
    RelaxedConstraintOut,
    RoleRead,
    RoleRequirementUpsert,
    RunRead,
    ShiftRead,
    ShiftRequirementRead,
    ShiftRequirementUpsert,
    ShiftRoleRequirementRead,
    SoftConstraintRead,
    SoftConstraintUpdate,
    SolveRequest,
    SolveResponse,
    WeekRequirementsRead,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Scheduler API", version="1.0.0")

DASHBOARD_FILE = Path(__file__).parent / "frontend" / "index.html"


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(DASHBOARD_FILE)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _404(e: NotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(e))


def _409(e: ConflictError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(e))


# ── 1. Catalogs ────────────────────────────────────────────────────────────────


@app.get("/roles", response_model=list[RoleRead])
def get_roles(db: Session = Depends(get_db)):
    return service.list_roles(db)


@app.get("/areas", response_model=list[AreaRead])
def get_areas(db: Session = Depends(get_db)):
    return service.list_areas(db)


@app.post("/roles", response_model=RoleRead, status_code=201)
def create_role(body: CatalogCreate, db: Session = Depends(get_db)):
    try:
        return service.create_role(db, body.name)
    except ConflictError as e:
        raise _409(e)


@app.post("/areas", response_model=AreaRead, status_code=201)
def create_area(body: CatalogCreate, db: Session = Depends(get_db)):
    try:
        return service.create_area(db, body.name)
    except ConflictError as e:
        raise _409(e)


@app.get("/shifts", response_model=list[ShiftRead])
def get_shifts(db: Session = Depends(get_db)):
    return service.list_shifts(db)


# ── 2. Employees ───────────────────────────────────────────────────────────────


@app.get("/employees", response_model=list[EmployeeRead])
def get_employees(
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    return service.list_employees(db, include_inactive=include_inactive)


@app.post("/employees", response_model=EmployeeRead, status_code=201)
def create_employee(body: EmployeeCreate, db: Session = Depends(get_db)):
    try:
        return service.create_employee(db, **body.model_dump())
    except NotFoundError as e:
        raise _404(e)
    except ConflictError as e:
        raise _409(e)


@app.patch("/employees/{employee_id}", response_model=EmployeeRead)
def update_employee(
    employee_id: int,
    body: EmployeeUpdate,
    db: Session = Depends(get_db),
):
    try:
        return service.update_employee(
            db, employee_id, body.model_dump(exclude_none=True)
        )
    except NotFoundError as e:
        raise _404(e)


# ── 3. Availability ────────────────────────────────────────────────────────────

@app.get("/employees/{employee_id}/availability", response_model=list[AvailabilityRead])
def get_employee_availability(employee_id: int, week_start: date = Query(...), db: Session = Depends(get_db)):
    try:
        return service.get_week_availability(db, employee_id, week_start)
    except NotFoundError as e:
        raise _404(e)



@app.put(
    "/employees/{employee_id}/availability/{target_date}",
    response_model=AvailabilityRead,
)
def set_availability(
    employee_id: int,
    target_date: date,
    body: AvailabilitySet,
    db: Session = Depends(get_db),
):
    try:
        return service.set_availability(db, employee_id, target_date, body.status)
    except NotFoundError as e:
        raise _404(e)


@app.delete(
    "/employees/{employee_id}/availability/{target_date}",
    status_code=204,
)
def remove_availability(
    employee_id: int,
    target_date: date,
    db: Session = Depends(get_db),
):
    try:
        service.remove_availability(db, employee_id, target_date)
    except NotFoundError as e:
        raise _404(e)


# ── 4. Requirements ────────────────────────────────────────────────────────────


@app.put("/requirements/shifts", response_model=ShiftRequirementRead)
def upsert_shift_requirement(
    week_start: date = Query(...),
    shift_id: int = Query(...),
    day_of_week: int = Query(..., ge=0, le=6),
    body: ShiftRequirementUpsert = Body(...),
    db: Session = Depends(get_db),
):
    try:
        return service.upsert_shift_requirement(
            db,
            week_start,
            shift_id,
            day_of_week,
            body.min_staff,
            body.max_staff,
        )
    except NotFoundError as e:
        raise _404(e)


@app.put("/requirements/roles", response_model=ShiftRoleRequirementRead)
def upsert_role_requirement(
    week_start: date = Query(...),
    shift_id: int = Query(...),
    day_of_week: int = Query(..., ge=0, le=6),
    body: RoleRequirementUpsert = Body(...),
    db: Session = Depends(get_db),
):
    try:
        return service.upsert_role_requirement(
            db,
            week_start,
            shift_id,
            day_of_week,
            body.role_id,
            body.area_id,
            body.min_count,
            body.max_count,
        )
    except NotFoundError as e:
        raise _404(e)
    except ConflictError as e:
        raise _409(e)


@app.get("/requirements", response_model=WeekRequirementsRead)
def get_requirements(
    week_start: date = Query(...),
    db: Session = Depends(get_db),
):
    return service.get_week_requirements(db, week_start)


# ── 5. Runs ────────────────────────────────────────────────────────────────────


@app.post("/runs", response_model=SolveResponse, status_code=201)
def create_run(body: SolveRequest, db: Session = Depends(get_db)):
    try:
        run, result = service.run_schedule(db, body.week_start)

    except InfeasibleError as e:
        raise HTTPException(
            status_code=422,
            detail={"message": e.diagnostic, "run_id": e.run_id},
        )

    return SolveResponse(
        run_id=run.id,
        feasibility=result.feasibility,
        solve_time_ms=result.solve_time_ms,
        assignments_count=len(result.assignments),
        relaxed_constraints=[
            RelaxedConstraintOut(
                constraint_id=rc.constraint_id,
                description=rc.description,
                priority=rc.priority,
                affected=rc.affected,
            )
            for rc in result.relaxed_constraints
        ],
        diagnostic=result.diagnostic,
    )


@app.get("/runs", response_model=list[RunRead])
def list_runs(
    week_start: Optional[date] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return service.list_runs(db, week_start=week_start, limit=limit)


@app.get("/runs/{run_id}", response_model=RunRead)
def get_run(run_id: int, db: Session = Depends(get_db)):
    try:
        return service.get_run_or_404(db, run_id)
    except NotFoundError as e:
        raise _404(e)


@app.get("/runs/{run_id}/assignments", response_model=list[AssignmentRead])
def get_run_assignments(run_id: int, db: Session = Depends(get_db)):
    try:
        return service.get_run_assignments(db, run_id)
    except NotFoundError as e:
        raise _404(e)


@app.patch(
    "/runs/{run_id}/assignments/{assignment_id}",
    response_model=AssignmentRead,
)
def override_assignment(
    run_id: int,
    assignment_id: int,
    body: AssignmentOverride,
    db: Session = Depends(get_db),
):
    try:
        return service.override_assignment(
            db, run_id, assignment_id, body.new_shift_id, body.actor
        )
    except NotFoundError as e:
        raise _404(e)
    except ConflictError as e:
        raise _409(e)


# ── 6. Export ──────────────────────────────────────────────────────────────────


@app.get("/runs/{run_id}/export")
def export_schedule(
    run_id: int,
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
):
    try:
        if format == "csv":
            content = service.export_schedule_csv(db, run_id)
            return Response(
                content=content,
                media_type="text/csv; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="schedule_{run_id}.csv"'
                },
            )
        content = service.export_schedule_xlsx(db, run_id)
        return Response(
            content=content,
            media_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            headers={
                "Content-Disposition": f'attachment; filename="schedule_{run_id}.xlsx"'
            },
        )
    except NotFoundError as e:
        raise _404(e)


# ── 7. Soft-constraint config ──────────────────────────────────────────────────


@app.get("/config/constraints", response_model=list[SoftConstraintRead])
def get_soft_constraints(db: Session = Depends(get_db)):
    return service.list_soft_constraints(db)


@app.patch(
    "/config/constraints/{constraint_id}",
    response_model=SoftConstraintRead,
)
def update_soft_constraint(
    constraint_id: str,
    body: SoftConstraintUpdate,
    db: Session = Depends(get_db),
):
    try:
        return service.update_soft_constraint(
            db, constraint_id, body.model_dump(exclude_none=True)
        )
    except NotFoundError as e:
        raise _404(e)
