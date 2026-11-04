"""
Repository layer: all SQLAlchemy queries, both reads and writes.
No business logic or validation here — that belongs in service.py.
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session, joinedload

from backend.models import (
    Area,
    AvailabilityStatus,
    Employee,
    EmployeeAvailability,
    Role,
    ScheduleAssignment,
    ScheduleRun,
    Shift,
    ShiftRequirement,
    ShiftRoleRequirement,
    SoftConstraintDef,
)
from backend.solver.types import (
    EmployeeInput,
    RoleRequirement,
    ShiftInput,
    SolverInput,
    StaffRequirement,
)

# ── Catalog reads ──────────────────────────────────────────────────────────────


def list_roles(db: Session) -> list[Role]:
    return db.query(Role).order_by(Role.name).all()


def list_areas(db: Session) -> list[Area]:
    return db.query(Area).order_by(Area.name).all()


def get_role(db: Session, role_id: int) -> Role | None:
    return db.get(Role, role_id)


def get_area(db: Session, area_id: int) -> Area | None:
    return db.get(Area, area_id)


def create_role(db: Session, name: str) -> Role:
    record = Role(name=name)
    db.add(record)
    db.flush()
    return record


def create_area(db: Session, name: str) -> Area:
    record = Area(name=name)
    db.add(record)
    db.flush()
    return record


def list_shifts(db: Session) -> list[Shift]:
    return db.query(Shift).all()


def get_shift(db: Session, shift_id: int) -> Shift | None:
    return db.get(Shift, shift_id)


# ── Employee reads & writes ────────────────────────────────────────────────────


def list_employees(
    db: Session,
    include_inactive: bool = False,
) -> list[Employee]:
    q = db.query(Employee)
    if not include_inactive:
        q = q.filter(Employee.active.is_(True))
    return q.order_by(Employee.name).all()


def get_employee(db: Session, employee_id: int) -> Employee | None:
    return db.get(Employee, employee_id)


def create_employee(
    db: Session,
    name: str,
    role_id: int,
    area_id: int | None = None,
) -> Employee:
    emp = Employee(name=name, role_id=role_id, area_id=area_id)
    db.add(emp)
    db.flush()
    return emp


def update_employee(
    db: Session,
    employee_id: int,
    updates: dict,
) -> Employee | None:
    emp = db.get(Employee, employee_id)
    if emp is None:
        return None
    for key, value in updates.items():
        if hasattr(emp, key) and value is not None:
            setattr(emp, key, value)
    db.flush()
    return emp


# ── Availability reads & writes ────────────────────────────────────────────────


def get_availability_record(
    db: Session,
    employee_id: int,
    target_date: date,
) -> EmployeeAvailability | None:
    return (
        db.query(EmployeeAvailability)
        .filter(
            EmployeeAvailability.employee_id == employee_id,
            EmployeeAvailability.date == target_date,
        )
        .first()
    )


def upsert_availability(
    db: Session,
    employee_id: int,
    target_date: date,
    status: AvailabilityStatus,
) -> EmployeeAvailability:
    record = get_availability_record(db, employee_id, target_date)
    if record:
        record.status = status
    else:
        record = EmployeeAvailability(
            employee_id=employee_id,
            date=target_date,
            status=status,
        )
        db.add(record)
    db.flush()
    return record


def delete_availability_record(
    db: Session,
    employee_id: int,
    target_date: date,
) -> bool:
    """Returns True if a record was deleted, False if none existed."""
    record = get_availability_record(db, employee_id, target_date)
    if record is None:
        return False
    db.delete(record)
    db.flush()
    return True


def get_availability_for_week(
    db: Session,
    week_start: date,
    employee_ids: list[int],
) -> dict[int, list[bool]]:
    """
    Returns availability[employee_id] = [bool]*7.
    True = available, False = vacation/sick/day-off.
    Days with no record default to True.
    """
    week_dates = [week_start + timedelta(days=d) for d in range(7)]

    records = (
        db.query(EmployeeAvailability)
        .filter(
            EmployeeAvailability.employee_id.in_(employee_ids),
            EmployeeAvailability.date.in_(week_dates),
        )
        .all()
    )

    unavailable: set[tuple[int, date]] = {
        (r.employee_id, r.date)
        for r in records
        if r.status != AvailabilityStatus.AVAILABLE
    }

    return {
        e_id: [(e_id, week_dates[d]) not in unavailable for d in range(7)]
        for e_id in employee_ids
    }


def list_availability_for_week(
    db: Session,
    employee_id: int,
    week_start: date,
) -> list[EmployeeAvailability]:
    week_dates = [week_start + timedelta(days=d) for d in range(7)]
    return (
        db.query(EmployeeAvailability)
        .filter(
            EmployeeAvailability.employee_id == employee_id,
            EmployeeAvailability.date.in_(week_dates),
        )
        .order_by(EmployeeAvailability.date)
        .all()
    )


# ── Shift requirements reads & writes ─────────────────────────────────────────


def get_staff_requirements(
    db: Session,
    week_start: date,
    shift_ids: list[int],
) -> dict[int, dict[int, StaffRequirement]]:
    """Returns staff_req[day_of_week][shift_id]."""
    records = (
        db.query(ShiftRequirement)
        .filter(
            ShiftRequirement.week_start_date == week_start,
            ShiftRequirement.shift_id.in_(shift_ids),
        )
        .all()
    )
    result: dict[int, dict[int, StaffRequirement]] = {}
    for r in records:
        result.setdefault(r.day_of_week, {})[r.shift_id] = StaffRequirement(
            min_staff=r.min_staff,
            max_staff=r.max_staff,
        )
    return result


def get_role_requirements(
    db: Session,
    week_start: date,
    shift_ids: list[int],
) -> dict[int, dict[int, list[RoleRequirement]]]:
    """Returns role_req[day_of_week][shift_id] = list[RoleRequirement]."""
    records = (
        db.query(ShiftRoleRequirement)
        .filter(
            ShiftRoleRequirement.week_start_date == week_start,
            ShiftRoleRequirement.shift_id.in_(shift_ids),
        )
        .all()
    )
    result: dict[int, dict[int, list[RoleRequirement]]] = {}
    for r in records:
        result.setdefault(r.day_of_week, {}).setdefault(r.shift_id, []).append(
            RoleRequirement(
                role_id=r.role_id,
                area_id=r.area_id,
                min_count=r.min_count,
                max_count=r.max_count,
            )
        )
    return result


def list_shift_requirements_for_week(
    db: Session,
    week_start: date,
) -> list[ShiftRequirement]:
    return (
        db.query(ShiftRequirement)
        .filter(ShiftRequirement.week_start_date == week_start)
        .all()
    )


def list_role_requirements_for_week(
    db: Session,
    week_start: date,
) -> list[ShiftRoleRequirement]:
    return (
        db.query(ShiftRoleRequirement)
        .filter(ShiftRoleRequirement.week_start_date == week_start)
        .all()
    )


def upsert_shift_requirement(
    db: Session,
    week_start: date,
    shift_id: int,
    day_of_week: int,
    min_staff: int,
    max_staff: int | None,
) -> ShiftRequirement:
    record = (
        db.query(ShiftRequirement)
        .filter(
            ShiftRequirement.week_start_date == week_start,
            ShiftRequirement.shift_id == shift_id,
            ShiftRequirement.day_of_week == day_of_week,
        )
        .first()
    )
    if record:
        record.min_staff = min_staff
        record.max_staff = max_staff
    else:
        record = ShiftRequirement(
            week_start_date=week_start,
            shift_id=shift_id,
            day_of_week=day_of_week,
            min_staff=min_staff,
            max_staff=max_staff,
        )
        db.add(record)
    db.flush()
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
) -> ShiftRoleRequirement:
    record = (
        db.query(ShiftRoleRequirement)
        .filter(
            ShiftRoleRequirement.week_start_date == week_start,
            ShiftRoleRequirement.shift_id == shift_id,
            ShiftRoleRequirement.day_of_week == day_of_week,
            ShiftRoleRequirement.role_id == role_id,
            ShiftRoleRequirement.area_id == area_id,
        )
        .first()
    )
    if record:
        record.min_count = min_count
        record.max_count = max_count
    else:
        record = ShiftRoleRequirement(
            week_start_date=week_start,
            shift_id=shift_id,
            day_of_week=day_of_week,
            role_id=role_id,
            area_id=area_id,
            min_count=min_count,
            max_count=max_count,
        )
        db.add(record)
    db.flush()
    return record


# ── Schedule run reads ─────────────────────────────────────────────────────────


def get_run(db: Session, run_id: int) -> ScheduleRun | None:
    return db.get(ScheduleRun, run_id)


def list_runs(
    db: Session,
    week_start: date | None = None,
    limit: int = 20,
) -> list[ScheduleRun]:
    q = db.query(ScheduleRun)
    if week_start:
        q = q.filter(ScheduleRun.week_start_date == week_start)
    return q.order_by(ScheduleRun.id.desc()).limit(limit).all()


def get_assignment(db: Session, assignment_id: int) -> ScheduleAssignment | None:
    return (
        db.query(ScheduleAssignment)
        .options(
            joinedload(ScheduleAssignment.employee),
            joinedload(ScheduleAssignment.shift),
        )
        .filter(ScheduleAssignment.id == assignment_id)
        .first()
    )


def get_assignments_for_run(
    db: Session,
    run_id: int,
) -> list[ScheduleAssignment]:
    return (
        db.query(ScheduleAssignment)
        .options(
            joinedload(ScheduleAssignment.employee),
            joinedload(ScheduleAssignment.shift),
        )
        .filter(ScheduleAssignment.run_id == run_id)
        .order_by(ScheduleAssignment.date, ScheduleAssignment.shift_id)
        .all()
    )


# ── Soft constraints config ────────────────────────────────────────────────────


def list_soft_constraints(db: Session) -> list[SoftConstraintDef]:
    return db.query(SoftConstraintDef).order_by(SoftConstraintDef.priority.desc()).all()


def get_soft_constraint_weights(db: Session) -> dict[str, int]:
    return {r.id: r.weight for r in db.query(SoftConstraintDef).all()}


def update_soft_constraint(
    db: Session,
    constraint_id: str,
    updates: dict,
) -> SoftConstraintDef | None:
    record = db.get(SoftConstraintDef, constraint_id)
    if record is None:
        return None
    for key, value in updates.items():
        if value is not None and hasattr(record, key):
            setattr(record, key, value)
    db.flush()
    return record


# ── Composite: build full SolverInput ─────────────────────────────────────────


def build_solver_input(db: Session, week_start: date) -> SolverInput:
    """
    Load all data needed for one scheduling run and return a SolverInput.
    Single entry point called by service.run_schedule().
    """
    employees = list_employees(db, include_inactive=False)
    shifts = list_shifts(db)
    emp_ids = [e.id for e in employees]
    shift_ids = [s.id for s in shifts]

    availability = get_availability_for_week(db, week_start, emp_ids)
    staff_req = get_staff_requirements(db, week_start, shift_ids)
    role_req = get_role_requirements(db, week_start, shift_ids)
    weights = get_soft_constraint_weights(db)

    employees_by_role: dict[int, list[int]] = {}
    employees_by_area: dict[int, list[int]] = {}
    for e in employees:
        employees_by_role.setdefault(e.role_id, []).append(e.id)
        if e.area_id:
            employees_by_area.setdefault(e.area_id, []).append(e.id)

    return SolverInput(
        week_start=week_start,
        employees=[
            EmployeeInput(id=e.id, name=e.name, role_id=e.role_id, area_id=e.area_id)
            for e in employees
        ],
        shifts=[ShiftInput(id=s.id, name=s.name) for s in shifts],
        availability=availability,
        staff_req=staff_req,
        role_req=role_req,
        employees_by_role=employees_by_role,
        employees_by_area=employees_by_area,
        weight_max_staff=weights.get("max_staff", 5),
        weight_max_role=weights.get("max_role", 4),
        weight_no_night_morning=weights.get("no_night_morning", 10),
    )
