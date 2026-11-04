"""
Pydantic v2 schemas for the scheduler API.

Convention:
  *Create  → POST body (fields required for creation)
  *Update  → PATCH body (all fields optional)
  *Read    → response body (ORM → schema via from_attributes=True)

The API layer imports these; the service layer works with ORM models.
"""

from datetime import date, time
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from .models import AvailabilityStatus, Feasibility, RunStatus

# ── Shared base ────────────────────────────────────────────────────────────────


class _OrmBase(BaseModel):
    """All Read schemas inherit this to enable ORM serialization."""

    model_config = ConfigDict(from_attributes=True)


# ── Catalog: roles & areas ─────────────────────────────────────────────────────


class CatalogCreate(BaseModel):
    name: str


class RoleRead(_OrmBase):
    id: int
    name: str


class AreaRead(_OrmBase):
    id: int
    name: str


# ── Catalog: shifts ────────────────────────────────────────────────────────────


class ShiftRead(_OrmBase):
    id: int
    name: str
    start_time: time
    duration_hours: int


# ── Employees ──────────────────────────────────────────────────────────────────


class EmployeeCreate(BaseModel):
    name: str
    role_id: int
    area_id: Optional[int] = None


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    role_id: Optional[int] = None
    area_id: Optional[int] = None
    active: Optional[bool] = None


class EmployeeRead(_OrmBase):
    id: int
    name: str
    role_id: int
    area_id: Optional[int]
    active: bool


# ── Availability ───────────────────────────────────────────────────────────────


class AvailabilitySet(BaseModel):
    status: AvailabilityStatus


class AvailabilityRead(_OrmBase):
    employee_id: int
    date: date
    status: AvailabilityStatus


# ── Shift requirements ─────────────────────────────────────────────────────────


class ShiftRequirementUpsert(BaseModel):
    min_staff: int = 1
    max_staff: Optional[int] = None


class RoleRequirementUpsert(BaseModel):
    role_id: Optional[int] = None
    area_id: Optional[int] = None
    min_count: int = 0
    max_count: Optional[int] = None


class ShiftRequirementRead(_OrmBase):
    id: int
    week_start_date: date
    shift_id: int
    day_of_week: int
    min_staff: int
    max_staff: Optional[int]


class ShiftRoleRequirementRead(_OrmBase):
    id: int
    week_start_date: date
    shift_id: int
    day_of_week: int
    role_id: Optional[int]
    area_id: Optional[int]
    min_count: int
    max_count: Optional[int]


class WeekRequirementsRead(BaseModel):
    """Full picture of requirements for a week, grouped for the UI."""

    week_start_date: date
    shift_requirements: list[ShiftRequirementRead]
    role_requirements: list[ShiftRoleRequirementRead]


# ── Solve ──────────────────────────────────────────────────────────────────────


class SolveRequest(BaseModel):
    week_start: date

    @field_validator("week_start")
    @classmethod
    def must_be_monday(cls, v: date) -> date:
        if v.weekday() != 0:
            raise ValueError("week_start must be a Monday (weekday 0)")
        return v


class RelaxedConstraintOut(BaseModel):
    constraint_id: str
    description: str
    priority: int
    affected: list[str]


class SolveResponse(BaseModel):
    run_id: int
    feasibility: str  # "full" | "partial" | "none"
    solve_time_ms: int
    assignments_count: int
    relaxed_constraints: list[RelaxedConstraintOut]
    diagnostic: Optional[str]


# ── Schedule runs ──────────────────────────────────────────────────────────────


class RunRead(_OrmBase):
    id: int
    week_start_date: date
    created_at: str
    status: RunStatus
    feasibility: Optional[Feasibility]
    solve_time_ms: Optional[int]
    relaxation_log: Optional[list]
    diagnostic: Optional[str]


class AssignmentRead(_OrmBase):
    id: int
    run_id: int
    employee_id: int
    date: date
    shift_id: int
    is_override: bool


class AssignmentOverride(BaseModel):
    """Body for PATCH /runs/{run_id}/assignments/{assignment_id}."""

    new_shift_id: int
    actor: Optional[str] = None


# ── Soft constraints config ────────────────────────────────────────────────────


class SoftConstraintRead(_OrmBase):
    id: str
    description: str
    priority: int
    weight: int


class SoftConstraintUpdate(BaseModel):
    weight: Optional[int] = None
    priority: Optional[int] = None
