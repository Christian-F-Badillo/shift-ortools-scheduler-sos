"""
CP-SAT model for weekly shift scheduling.

Hard constraints  (never violated):
  H1. At most one shift per employee per day.
  H2. Respect per-day availability (vacation, sick, day-off).
  H3. Minimum staff per (day, shift).
  H4. Minimum staff per (day, shift, role/area).

Soft constraints  (penalized in the objective, violations reported):
  S1. Maximum staff per (day, shift)         [weight_max_staff]
  S2. Maximum staff per (day, shift, role)   [weight_max_role]
  S3. No night-shift followed by morning-shift the next day
                                             [weight_no_night_morning]

The solver minimizes the total weighted penalty in a single pass.
After solving, any variable with a non-zero penalty value is reported
as a "relaxed" constraint in the result.
"""

import time

from ortools.sat.python import cp_model

from .types import (
    Assignment,
    RelaxedConstraintInfo,
    SolveResult,
    SolverInput,
)

_MORNING = "MORNING"
_NIGHT = "NIGHT"


def solve(inp: SolverInput) -> SolveResult:
    t0 = time.perf_counter()

    model = cp_model.CpModel()
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0

    emp_ids = [e.id for e in inp.employees]
    shift_ids = [s.id for s in inp.shifts]
    shift_name = {s.id: s.name for s in inp.shifts}
    days = range(7)

    morning_id = next((s.id for s in inp.shifts if s.name == _MORNING), None)
    night_id = next((s.id for s in inp.shifts if s.name == _NIGHT), None)

    # ── Decision variables ─────────────────────────────────────────────────────
    # x[e, d, s] = 1  iff  employee e works shift s on day d
    x: dict[tuple[int, int, int], cp_model.IntVar] = {
        (e, d, s): model.new_bool_var(f"x_e{e}_d{d}_s{s}")
        for e in emp_ids
        for d in days
        for s in shift_ids
    }

    # ── HARD constraints ───────────────────────────────────────────────────────

    # H1. At most one shift per employee per day
    for e in emp_ids:
        for d in days:
            model.add_at_most_one(x[e, d, s] for s in shift_ids)

    # H2. Per-day availability (vacation, sick leave, rest day)
    for e in emp_ids:
        avail = inp.availability.get(e, [True] * 7)
        for d in days:
            if not avail[d]:
                for s in shift_ids:
                    model.add(x[e, d, s] == 0)

    # H3. Minimum global staff per (day, shift)
    for d in days:
        for s in shift_ids:
            req = inp.staff_req.get(d, {}).get(s)
            if req and req.min_staff > 0:
                model.add(sum(x[e, d, s] for e in emp_ids) >= req.min_staff)

    # H4. Minimum staff per (day, shift, role/area)
    for d in days:
        for s in shift_ids:
            for rr in inp.role_req.get(d, {}).get(s, []):
                if rr.min_count <= 0:
                    continue
                eligible = _eligible_employees(rr, inp)
                if eligible:
                    model.add(sum(x[e, d, s] for e in eligible) >= rr.min_count)

    # ── SOFT constraints (penalized overflow / indicator variables) ────────────
    penalties: list = []

    # S1. Maximum global staff per (day, shift)
    # overflow[d, s] = max(0, assigned − max_staff)
    overflow_vars: dict[tuple[int, int], cp_model.IntVar] = {}
    for d in days:
        for s in shift_ids:
            req = inp.staff_req.get(d, {}).get(s)
            if req and req.max_staff is not None:
                ov = model.new_int_var(0, len(emp_ids), f"ov_d{d}_s{s}")
                model.add(sum(x[e, d, s] for e in emp_ids) <= req.max_staff + ov)
                overflow_vars[d, s] = ov
                penalties.append(inp.weight_max_staff * ov)

    # S2. Maximum staff per (day, shift, role/area)
    # Key format: "rov_d{d}_s{s}_i{i}" — parsed back by _parse_ds() for reporting
    role_ov_vars: dict[str, cp_model.IntVar] = {}
    for d in days:
        for s in shift_ids:
            for i, rr in enumerate(inp.role_req.get(d, {}).get(s, [])):
                if rr.max_count is None:
                    continue
                eligible = _eligible_employees(rr, inp)
                if not eligible:
                    continue
                key = f"rov_d{d}_s{s}_i{i}"
                ov = model.new_int_var(0, len(eligible), key)
                model.add(sum(x[e, d, s] for e in eligible) <= rr.max_count + ov)
                role_ov_vars[key] = ov
                penalties.append(inp.weight_max_role * ov)

    # S3. No night → morning on consecutive days
    # bad[e, d] = 1  iff  night[d]=1 AND morning[d+1]=1
    # Modeled as: night[d] + morning[d+1] ≤ 1 + bad
    # Minimizing bad forces it to 0 unless both transitions are assigned.
    bad_rest_vars: dict[tuple[int, int], cp_model.IntVar] = {}
    if night_id is not None and morning_id is not None:
        for e in emp_ids:
            for d in range(6):  # day pairs (0,1) … (5,6)
                bad = model.new_bool_var(f"bad_e{e}_d{d}")
                model.add(x[e, d, night_id] + x[e, d + 1, morning_id] <= 1 + bad)
                bad_rest_vars[e, d] = bad
                penalties.append(inp.weight_no_night_morning * bad)

    if penalties:
        model.minimize(sum(penalties))

    # ── Solve ──────────────────────────────────────────────────────────────────
    status = solver.solve(model)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    if status == cp_model.INFEASIBLE:
        return SolveResult(
            feasibility="none",
            assignments=[],
            relaxed_constraints=[],
            solve_time_ms=elapsed_ms,
            diagnostic=_diagnose(inp),
        )

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolveResult(
            feasibility="none",
            assignments=[],
            relaxed_constraints=[],
            solve_time_ms=elapsed_ms,
            diagnostic="El solver agotó el tiempo límite o devolvió estado desconocido.",
        )

    # ── Extract assignments ────────────────────────────────────────────────────
    assignments = [
        Assignment(employee_id=e, day_of_week=d, shift_id=s)
        for e in emp_ids
        for d in days
        for s in shift_ids
        if solver.value(x[e, d, s])
    ]

    # ── Detect violated soft constraints ───────────────────────────────────────
    emp_name = {e.id: e.name for e in inp.employees}
    relaxed: list[RelaxedConstraintInfo] = []

    # S1 violations
    affected_max: list[str] = []
    for (d, s), ov in overflow_vars.items():
        v = solver.value(ov)
        if v > 0:
            affected_max.append(f"día {d} turno {shift_name[s]} (exceso: +{v})")
    if affected_max:
        relaxed.append(
            RelaxedConstraintInfo(
                constraint_id="max_staff",
                description="Máximo de personal por turno excedido",
                priority=3,
                affected=affected_max,
            )
        )

    # S2 violations
    affected_role: list[str] = []
    for key, ov in role_ov_vars.items():
        v = solver.value(ov)
        if v > 0:
            d, s = _parse_ds(key)
            affected_role.append(f"día {d} turno {shift_name[s]} (exceso: +{v})")
    if affected_role:
        relaxed.append(
            RelaxedConstraintInfo(
                constraint_id="max_role",
                description="Máximo por rol/área por turno excedido",
                priority=4,
                affected=affected_role,
            )
        )

    # S3 violations
    affected_rest: list[str] = []
    for (e, d), bad in bad_rest_vars.items():
        if solver.value(bad):
            affected_rest.append(
                f"{emp_name.get(e, str(e))} (día {d} noche → día {d + 1} mañana)"
            )
    if affected_rest:
        relaxed.append(
            RelaxedConstraintInfo(
                constraint_id="no_night_morning",
                description="Transición noche → mañana en días consecutivos",
                priority=7,
                affected=affected_rest,
            )
        )

    return SolveResult(
        feasibility="full" if not relaxed else "partial",
        assignments=assignments,
        relaxed_constraints=relaxed,
        solve_time_ms=elapsed_ms,
        diagnostic=None,
    )


# ── Helpers ────────────────────────────────────────────────────────────────────


def _eligible_employees(rr, inp: SolverInput) -> list[int]:
    """Return employee IDs that satisfy a RoleRequirement filter."""
    if rr.role_id is not None:
        return inp.employees_by_role.get(rr.role_id, [])
    if rr.area_id is not None:
        return inp.employees_by_area.get(rr.area_id, [])
    return []


def _parse_ds(key: str) -> tuple[int, int]:
    """
    Extract (day, shift_id) from a role_ov_vars key.
    Key format: "rov_d{day}_s{shift_id}_i{index}"
    """
    parts = key.split("_")  # ["rov", "d2", "s1", "i0"]
    return int(parts[1][1:]), int(parts[2][1:])


def _diagnose(inp: SolverInput) -> str:
    """
    Quick sanity check: find (day, shift) pairs where min_staff
    exceeds the number of available employees.
    Falls back to a generic message for role/area conflicts.
    """
    emp_ids = [e.id for e in inp.employees]
    messages: list[str] = []

    for d in range(7):
        available = sum(1 for e in emp_ids if inp.availability.get(e, [True] * 7)[d])
        for s in inp.shifts:
            req = inp.staff_req.get(d, {}).get(s.id)
            if req and req.min_staff > available:
                messages.append(
                    f"Día {d} turno {s.name}: "
                    f"mínimo requerido {req.min_staff}, "
                    f"disponibles {available}"
                )

    if not messages:
        return (
            "Conflicto en restricciones duras de rol/área. "
            "Revise los requisitos mínimos por rol para cada turno."
        )
    return " | ".join(messages)
