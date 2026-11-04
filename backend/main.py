"""
Seed the database with example data and run a smoke test.

Usage:
    python main.py

Scenario:
    - 10 employees across 3 roles (Técnico, Soporte, Administrador)
    - 2 shifts: MORNING (07:00) and NIGHT (15:00), 9 h each
    - Week 2025-01-06 (Mon–Sun)
    - 2–4 staff required per shift per day, min 1 Técnico
    - Alice on vacation Wednesday–Friday
"""

from datetime import date, time, timedelta

import models
from database import Base, SessionLocal, engine
from service import run_schedule

DAY_NAMES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


# ── Seed ──────────────────────────────────────────────────────────────────────


def seed(db) -> tuple[date, dict[int, str]]:
    # Roles
    roles = {
        name: models.Role(name=name) for name in ("Técnico", "Soporte", "Administrador")
    }
    db.add_all(roles.values())
    db.flush()

    # Shifts
    morning = models.Shift(name="MORNING", start_time=time(7, 0), duration_hours=9)
    night = models.Shift(name="NIGHT", start_time=time(15, 0), duration_hours=9)
    db.add_all([morning, night])
    db.flush()

    # Soft constraint catalog
    db.add_all(
        [
            models.SoftConstraintDef(
                id="max_staff",
                description="Máximo de personal por turno",
                priority=3,
                weight=5,
            ),
            models.SoftConstraintDef(
                id="max_role",
                description="Máximo por rol/área por turno",
                priority=4,
                weight=4,
            ),
            models.SoftConstraintDef(
                id="no_night_morning",
                description="No turno noche seguido de mañana",
                priority=7,
                weight=10,
            ),
        ]
    )
    db.flush()

    # Employees
    raw_employees = [
        ("Alice", "Técnico"),
        ("Bob", "Técnico"),
        ("Carlos", "Soporte"),
        ("Diana", "Soporte"),
        ("Eduardo", "Técnico"),
        ("Fiona", "Soporte"),
        ("Gabriel", "Administrador"),
        ("Helena", "Técnico"),
        ("Ignacio", "Soporte"),
        ("Julia", "Administrador"),
    ]
    employees = [
        models.Employee(name=name, role_id=roles[role].id)
        for name, role in raw_employees
    ]
    db.add_all(employees)
    db.flush()

    # Shift requirements (same for every day of the test week)
    week_start = date(2025, 1, 6)  # Monday
    for d in range(7):
        for shift in (morning, night):
            db.add(
                models.ShiftRequirement(
                    week_start_date=week_start,
                    shift_id=shift.id,
                    day_of_week=d,
                    min_staff=2,
                    max_staff=4,
                )
            )
            # At least 1 Técnico per shift per day
            db.add(
                models.ShiftRoleRequirement(
                    week_start_date=week_start,
                    shift_id=shift.id,
                    day_of_week=d,
                    role_id=roles["Técnico"].id,
                    min_count=1,
                    max_count=None,
                )
            )

    # Alice on vacation Wednesday (day 2) through Friday (day 4)
    alice = employees[0]
    for offset in (2, 3, 4):
        db.add(
            models.EmployeeAvailability(
                employee_id=alice.id,
                date=week_start + timedelta(days=offset),
                status=models.AvailabilityStatus.VACATION,
            )
        )

    db.commit()
    return week_start, {e.id: e.name for e in employees}


# ── Display ───────────────────────────────────────────────────────────────────


def pretty_print(result, emp_names: dict[int, str], shift_names: dict[int, str]):
    sep = "─" * 52

    feasibility_label = {
        "full": "✓  COMPLETO  — todas las restricciones satisfechas",
        "partial": "⚠  PARCIAL   — algunas restricciones blandas relajadas",
        "none": "✗  INFACTIBLE — no se encontró solución",
    }

    print(f"\n{sep}")
    print(f"  {feasibility_label.get(result.feasibility, result.feasibility)}")
    print(f"  Tiempo de resolución : {result.solve_time_ms} ms")
    print(f"  Asignaciones         : {len(result.assignments)}")
    print(sep)

    if result.feasibility == "none":
        print(f"\n  Diagnóstico: {result.diagnostic}")
        return

    # Group assignments by day
    by_day: dict[int, list] = {d: [] for d in range(7)}
    for a in result.assignments:
        by_day[a.day_of_week].append(a)

    print()
    for d in range(7):
        entries = sorted(by_day[d], key=lambda a: a.shift_id)
        if not entries:
            print(f"  {DAY_NAMES[d]}  (sin asignaciones)")
            continue
        print(f"  {DAY_NAMES[d]}")
        for a in entries:
            icon = "☀" if shift_names[a.shift_id] == "MORNING" else "🌙"
            label = "Mañana" if shift_names[a.shift_id] == "MORNING" else "Noche "
            name = emp_names.get(a.employee_id, str(a.employee_id))
            print(f"    {icon} {label}  {name}")
        print()

    if result.relaxed_constraints:
        print("  Restricciones relajadas:")
        for rc in sorted(result.relaxed_constraints, key=lambda r: r.priority):
            print(f"    [{rc.priority}] {rc.description}")
            for item in rc.affected:
                print(f"         · {item}")
    else:
        print("  Todas las restricciones blandas fueron satisfechas.")

    print()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    week_start, emp_names = seed(db)

    shift_names = {s.id: s.name for s in db.query(models.Shift).all()}

    print(f"\nGenerando horario para la semana del {week_start}…")
    run, result = run_schedule(db, week_start)

    pretty_print(result, emp_names, shift_names)
    db.close()
