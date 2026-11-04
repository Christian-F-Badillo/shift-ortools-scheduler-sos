from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class EmployeeInput:
    id: int
    name: str
    role_id: int
    area_id: Optional[int]


@dataclass
class ShiftInput:
    id: int
    name: str  # "MORNING" | "NIGHT"


@dataclass
class StaffRequirement:
    min_staff: int
    max_staff: Optional[int]  # None → no upper limit


@dataclass
class RoleRequirement:
    role_id: Optional[int]
    area_id: Optional[int]
    min_count: int
    max_count: Optional[int]  # None → no upper limit


@dataclass
class SolverInput:
    week_start: date
    employees: list[EmployeeInput]
    shifts: list[ShiftInput]

    # availability[employee_id] = [bool]*7
    # True  → employee is available that day of the week
    # False → vacation / sick / day-off (hard constraint: cannot be assigned)
    availability: dict[int, list[bool]]

    # staff_req[day_of_week][shift_id] = StaffRequirement
    staff_req: dict[int, dict[int, StaffRequirement]]

    # role_req[day_of_week][shift_id] = list[RoleRequirement]
    role_req: dict[int, dict[int, list[RoleRequirement]]]

    # Pre-grouped employee IDs for fast constraint generation
    employees_by_role: dict[int, list[int]]  # role_id → [emp_id, …]
    employees_by_area: dict[int, list[int]]  # area_id → [emp_id, …]

    # Penalty weights — higher = solver avoids this violation more aggressively
    weight_max_staff: int = 5
    weight_max_role: int = 4
    weight_no_night_morning: int = 10


@dataclass
class Assignment:
    employee_id: int
    day_of_week: int  # 0 = Monday … 6 = Sunday
    shift_id: int


@dataclass
class RelaxedConstraintInfo:
    constraint_id: str
    description: str
    priority: int
    affected: list[str]  # human-readable description of each violation


@dataclass
class SolveResult:
    # "full"    → solution found, all soft constraints satisfied
    # "partial" → solution found, some soft constraints violated
    # "none"    → hard constraints are infeasible
    feasibility: str
    assignments: list[Assignment]
    relaxed_constraints: list[RelaxedConstraintInfo]
    solve_time_ms: int
    diagnostic: Optional[str]
