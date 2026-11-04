"""
Service layer: all business logic and orchestration.

This is the only layer the API touches.
Every public function here maps 1-to-1 with one or more API endpoints.

Raises:
  NotFoundError   → resource not found (404)
  ConflictError   → state/uniqueness violation (409)
  InfeasibleError → hard constraints are unsatisfiable (422)
"""

import csv
import io
from datetime import date, datetime, timedelta

import repositories as repo
from exceptions import ConflictError, InfeasibleError, NotFoundError
from models import (
    AuditLog,
    AvailabilityStatus,
    RunStatus,
    ScheduleAssignment,
    ScheduleRun,
    ScheduleRunConstraint,
)
from solver.builder import solve
from solver.types import SolveResult
from sqlalchemy.orm import Session

DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
_SOFT_CONSTRAINT_IDS = ("max_staff", "max_role", "no_night_morning")


# ── Catalog ────────────────────────────────────────────────────────────────────


def list_roles(db: Session):
    return repo.list_roles(db)


def list_areas(db: Session):
    return repo.list_areas(db)


def list_shifts(db: Session):
    return repo.list_shifts(db)


# ── Employees ──────────────────────────────────────────────────────────────────


def list_employees(db: Session, include_inactive: bool = False):
    return repo.list_employees(db, include_inactive=include_inactive)


def get_employee_or_404(db: Session, employee_id: int):
    emp = repo.get_employee(db, employee_id)
    if emp is None:
        raise NotFoundError("Employee", employee_id)
    return emp


def create_employee(
    db: Session,
    name: str,
    role_id: int,
    area_id: int | None = None,
):
    emp = repo.create_employee(db, name=name, role_id=role_id, area_id=area_id)
    db.commit()
    db.refresh(emp)
    return emp


def update_employee(db: Session, employee_id: int, updates: dict):
    # Strip None values so we only patch what was explicitly sent
    clean = {k: v for k, v in updates.items() if v is not None}
    emp = repo.update_employee(db, employee_id, clean)
    if emp is None:
        raise NotFoundError("Employee", employee_id)
    db.commit()
    db.refresh(emp)
    return emp


def deactivate_employee(db: Session, employee_id: int):
    """Soft-delete: sets active=False instead of removing the row."""
    return update_employee(db, employee_id, {"active": False})


# ── Availability ───────────────────────────────────────────────────────────────


def set_availability(
    db: Session,
    employee_id: int,
    target_date: date,
    status: AvailabilityStatus,
):
    get_employee_or_404(db, employee_id)  # validates existence
    record = repo.upsert_availability(db, employee_id, target_date, status)
    db.commit()
    db.refresh(record)
    return record


def remove_availability(db: Session, employee_id: int, target_date: date):
    get_employee_or_404(db, employee_id)
    deleted = repo.delete_availability_record(db, employee_id, target_date)
    if not deleted:
        raise NotFoundError("EmployeeAvailability", f"{employee_id}/{target_date}")
    db.commit()


def get_week_availability(
    db: Session,
    employee_id: int,
    week_start: date,
):
    get_employee_or_404(db, employee_id)
    return repo.list_availability_for_week(db, employee_id, week_start)


# ── Shift requirements ─────────────────────────────────────────────────────────


def upsert_shift_requirement(
    db: Session,
    week_start: date,
    shift_id: int,
    day_of_week: int,
    min_staff: int,
    max_staff: int | None,
):
    if repo.get_shift(db, shift_id) is None:
        raise NotFoundError("Shift", shift_id)
    record = repo.upsert_shift_requirement(
        db, week_start, shift_id, day_of_week, min_staff, max_staff
    )
    db.commit()
    db.refresh(record)
    return record


def upsert_role_requirement(
    db: Session,
    week_start: date,
    shift_id: int,
    day_of_week: int,
    role_id: int | None,
    area_id: int | None,
    min_count: int,
    max_count: int | None,
):
    if role_id is None and area_id is None:
        raise ConflictError("At least one of role_id or area_id must be set.")
    if repo.get_shift(db, shift_id) is None:
        raise NotFoundError("Shift", shift_id)
    record = repo.upsert_role_requirement(
        db,
        week_start,
        shift_id,
        day_of_week,
        role_id,
        area_id,
        min_count,
        max_count,
    )
    db.commit()
    db.refresh(record)
    return record


def get_week_requirements(db: Session, week_start: date):
    return {
        "week_start_date": week_start,
        "shift_requirements": repo.list_shift_requirements_for_week(db, week_start),
        "role_requirements": repo.list_role_requirements_for_week(db, week_start),
    }


# ── Schedule run ───────────────────────────────────────────────────────────────


def run_schedule(
    db: Session,
    week_start: date,
) -> tuple[ScheduleRun, SolveResult]:
    """
    Full scheduling run: load → solve → persist.

    Raises InfeasibleError if hard constraints have no solution.
    Returns (ScheduleRun ORM object, raw SolveResult dataclass).
    """
    run = ScheduleRun(
        week_start_date=week_start,
        created_at=datetime.utcnow().isoformat(),
        status=RunStatus.RUNNING,
    )
    db.add(run)
    db.flush()

    try:
        solver_input = repo.build_solver_input(db, week_start)

        run.parameters_snapshot = {
            "week_start": week_start.isoformat(),
            "employee_count": len(solver_input.employees),
            "shifts": [s.name for s in solver_input.shifts],
        }

        result = solve(solver_input)

        run.status = RunStatus.DONE
        run.feasibility = result.feasibility
        run.solve_time_ms = result.solve_time_ms
        run.diagnostic = result.diagnostic
        run.relaxation_log = [
            {
                "constraint_id": rc.constraint_id,
                "description": rc.description,
                "affected": rc.affected,
            }
            for rc in result.relaxed_constraints
        ]

        if result.feasibility != "none":
            week_dates = [week_start + timedelta(days=d) for d in range(7)]
            for a in result.assignments:
                db.add(
                    ScheduleAssignment(
                        run_id=run.id,
                        employee_id=a.employee_id,
                        date=week_dates[a.day_of_week],
                        shift_id=a.shift_id,
                    )
                )
            relaxed_ids = {rc.constraint_id for rc in result.relaxed_constraints}
            for cid in _SOFT_CONSTRAINT_IDS:
                db.add(
                    ScheduleRunConstraint(
                        run_id=run.id,
                        constraint_id=cid,
                        was_relaxed=cid in relaxed_ids,
                    )
                )

        db.commit()
        db.refresh(run)

    except Exception as exc:
        db.rollback()
        run.status = RunStatus.FAILED
        run.diagnostic = str(exc)
        db.commit()
        raise

    if result.feasibility == "none":
        raise InfeasibleError(result.diagnostic or "No solution found.")

    return run, result


def get_run_or_404(db: Session, run_id: int) -> ScheduleRun:
    run = repo.get_run(db, run_id)
    if run is None:
        raise NotFoundError("ScheduleRun", run_id)
    return run


def list_runs(
    db: Session,
    week_start: date | None = None,
    limit: int = 20,
) -> list[ScheduleRun]:
    return repo.list_runs(db, week_start=week_start, limit=limit)


def get_run_assignments(
    db: Session,
    run_id: int,
) -> list[ScheduleAssignment]:
    get_run_or_404(db, run_id)
    return repo.get_assignments_for_run(db, run_id)


# ── Manual override ────────────────────────────────────────────────────────────


def override_assignment(
    db: Session,
    run_id: int,
    assignment_id: int,
    new_shift_id: int,
    actor: str | None = None,
) -> ScheduleAssignment:
    """
    Manually change the shift of an existing assignment.
    Validates that:
      - The run and assignment both exist.
      - The assignment belongs to the given run.
      - The new shift exists.
      - The employee is available on the assignment date for the new shift.
    Writes an AuditLog entry on success.
    """
    get_run_or_404(db, run_id)

    assignment = repo.get_assignment(db, assignment_id)
    if assignment is None:
        raise NotFoundError("ScheduleAssignment", assignment_id)
    if assignment.run_id != run_id:
        raise ConflictError(
            f"Assignment {assignment_id} does not belong to run {run_id}."
        )

    new_shift = repo.get_shift(db, new_shift_id)
    if new_shift is None:
        raise NotFoundError("Shift", new_shift_id)

    # Check employee availability on that specific date
    avail_record = repo.get_availability_record(
        db, assignment.employee_id, assignment.date
    )
    if avail_record and avail_record.status != AvailabilityStatus.AVAILABLE:
        raise ConflictError(
            f"Employee {assignment.employee_id} is marked as "
            f"{avail_record.status} on {assignment.date}. "
            "Cannot override to that date."
        )

    old_shift_id = assignment.shift_id
    assignment.shift_id = new_shift_id
    assignment.is_override = True

    db.add(
        AuditLog(
            run_id=run_id,
            assignment_id=assignment_id,
            action="OVERRIDE",
            actor=actor,
            timestamp=datetime.utcnow().isoformat(),
            detail={
                "employee_id": assignment.employee_id,
                "date": assignment.date.isoformat(),
                "old_shift_id": old_shift_id,
                "new_shift_id": new_shift_id,
            },
        )
    )

    db.commit()
    db.refresh(assignment)
    return assignment


# ── Exports ────────────────────────────────────────────────────────────────────


def export_schedule_csv(db: Session, run_id: int) -> str:
    """
    Returns a UTF-8 CSV string with one row per assignment.
    Columns: Fecha, Día, Turno, Hora_inicio, Empleado, Rol, Área, Override
    """
    get_run_or_404(db, run_id)
    assignments = repo.get_assignments_for_run(db, run_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["Fecha", "Día", "Turno", "Hora_inicio", "Empleado", "Rol", "Área", "Override"]
    )

    for a in assignments:
        day_name = DAY_NAMES[a.date.weekday()]
        role_name = a.employee.role.name if a.employee.role else ""
        area_name = a.employee.area.name if a.employee.area else ""
        writer.writerow(
            [
                a.date.isoformat(),
                day_name,
                a.shift.name,
                a.shift.start_time.strftime("%H:%M"),
                a.employee.name,
                role_name,
                area_name,
                "Sí" if a.is_override else "No",
            ]
        )

    return output.getvalue()


def export_schedule_xlsx(db: Session, run_id: int) -> bytes:
    """
    Returns an .xlsx file as bytes.
    One sheet per day of the week, with header row styled in blue.
    Requires openpyxl.
    """
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError as e:
        raise RuntimeError("openpyxl is required for Excel export.") from e

    run = get_run_or_404(db, run_id)
    assignments = repo.get_assignments_for_run(db, run_id)

    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # remove default sheet

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2563EB")  # blue-600
    override_fill = PatternFill("solid", fgColor="FEF9C3")  # yellow-100

    # Group assignments by day of week
    by_day: dict[int, list] = {d: [] for d in range(7)}
    for a in assignments:
        by_day[a.date.weekday()].append(a)

    headers = ["Hora inicio", "Turno", "Empleado", "Rol", "Área", "Override"]

    for day_idx, day_assignments in by_day.items():
        ws = wb.create_sheet(title=DAY_NAMES[day_idx])

        # Date subtitle
        if day_assignments:
            ws.cell(row=1, column=1, value=str(day_assignments[0].date))
        else:
            week_date = run.week_start_date + timedelta(days=day_idx)
            ws.cell(row=1, column=1, value=str(week_date))
        ws.cell(row=1, column=1).font = Font(italic=True, color="6B7280")

        # Headers
        for col, h in enumerate(headers, start=1):
            cell = ws.cell(row=2, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")

        # Rows
        for row_idx, a in enumerate(day_assignments, start=3):
            role_name = a.employee.role.name if a.employee.role else ""
            area_name = a.employee.area.name if a.employee.area else ""
            row_data = [
                a.shift.start_time.strftime("%H:%M"),
                a.shift.name,
                a.employee.name,
                role_name,
                area_name,
                "Sí" if a.is_override else "",
            ]
            for col, value in enumerate(row_data, start=1):
                cell = ws.cell(row=row_idx, column=col, value=value)
                if a.is_override:
                    cell.fill = override_fill

        # Auto-width
        for col in ws.columns:
            max_len = max((len(str(c.value or "")) for c in col), default=0)
            ws.column_dimensions[col[0].column_letter].width = max(max_len + 2, 10)

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


# ── Soft constraints config ────────────────────────────────────────────────────


def list_soft_constraints(db: Session):
    return repo.list_soft_constraints(db)


def update_soft_constraint(
    db: Session,
    constraint_id: str,
    updates: dict,
):
    clean = {k: v for k, v in updates.items() if v is not None}
    record = repo.update_soft_constraint(db, constraint_id, clean)
    if record is None:
        raise NotFoundError("SoftConstraintDef", constraint_id)
    db.commit()
    db.refresh(record)
    return record
