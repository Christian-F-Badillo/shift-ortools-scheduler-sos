import enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base

# ── Enumerations ───────────────────────────────────────────────────────────────


class AvailabilityStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    VACATION = "VACATION"
    SICK = "SICK"
    DAY_OFF = "DAY_OFF"


class Feasibility(str, enum.Enum):
    FULL = "full"
    PARTIAL = "partial"
    NONE = "none"


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


# ── Catalog tables ─────────────────────────────────────────────────────────────


class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    employees = relationship("Employee", back_populates="role")


class Area(Base):
    __tablename__ = "areas"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    employees = relationship("Employee", back_populates="area")


class Shift(Base):
    __tablename__ = "shifts"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)  # MORNING | NIGHT
    start_time = Column(Time, nullable=False)
    duration_hours = Column(Integer, nullable=False, default=9)


class SoftConstraintDef(Base):
    """
    Catalog of soft constraints.
    weight   : penalty coefficient in the CP-SAT objective.
    priority : 1 = last to relax, 10 = first to relax (informational).
    """

    __tablename__ = "soft_constraints"
    id = Column(
        String, primary_key=True
    )  # "max_staff" | "max_role" | "no_night_morning"
    description = Column(String, nullable=False)
    priority = Column(Integer, nullable=False)
    weight = Column(Integer, nullable=False)


# ── Employee & availability ────────────────────────────────────────────────────


class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=True)
    active = Column(Boolean, default=True, nullable=False)

    role = relationship("Role", back_populates="employees")
    area = relationship("Area", back_populates="employees")
    availability = relationship("EmployeeAvailability", back_populates="employee")


class EmployeeAvailability(Base):
    """
    One record per (employee, date) for any non-AVAILABLE day.
    Days with no record are assumed AVAILABLE.
    This handles mid-week vacations naturally.
    """

    __tablename__ = "employee_availability"
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    date = Column(Date, nullable=False)
    status = Column(Enum(AvailabilityStatus), nullable=False)

    employee = relationship("Employee", back_populates="availability")

    __table_args__ = (UniqueConstraint("employee_id", "date"),)


# ── Shift requirements ─────────────────────────────────────────────────────────


class ShiftRequirement(Base):
    """
    Global headcount limits per (week, shift, day_of_week).
    max_staff is nullable → no upper limit (treated as a soft constraint
    only when a value is set).
    """

    __tablename__ = "shift_requirements"
    id = Column(Integer, primary_key=True)
    week_start_date = Column(Date, nullable=False)
    shift_id = Column(Integer, ForeignKey("shifts.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0 = Mon … 6 = Sun
    min_staff = Column(Integer, nullable=False, default=1)
    max_staff = Column(Integer, nullable=True)

    shift = relationship("Shift")

    __table_args__ = (UniqueConstraint("week_start_date", "shift_id", "day_of_week"),)


class ShiftRoleRequirement(Base):
    """
    Per-role or per-area headcount limits for a (week, shift, day_of_week).
    Exactly one of role_id / area_id must be set.
    """

    __tablename__ = "shift_role_requirements"
    id = Column(Integer, primary_key=True)
    week_start_date = Column(Date, nullable=False)
    shift_id = Column(Integer, ForeignKey("shifts.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=True)
    min_count = Column(Integer, nullable=False, default=0)
    max_count = Column(Integer, nullable=True)

    shift = relationship("Shift")
    role = relationship("Role")
    area = relationship("Area")


# ── Schedule runs & results ────────────────────────────────────────────────────


class ScheduleRun(Base):
    """
    Immutable snapshot of one solver execution.
    parameters_snapshot : JSON — inputs used (employee count, week, shifts).
    relaxation_log      : JSON — which soft constraints were violated and where.
    """

    __tablename__ = "schedule_runs"
    id = Column(Integer, primary_key=True)
    week_start_date = Column(Date, nullable=False)
    created_at = Column(String, nullable=False)  # ISO-8601
    status = Column(Enum(RunStatus), default=RunStatus.PENDING)
    feasibility = Column(Enum(Feasibility), nullable=True)
    solve_time_ms = Column(Integer, nullable=True)
    parameters_snapshot = Column(JSON, nullable=True)
    relaxation_log = Column(JSON, nullable=True)
    diagnostic = Column(String, nullable=True)

    assignments = relationship("ScheduleAssignment", back_populates="run")
    run_constraints = relationship("ScheduleRunConstraint", back_populates="run")


class ScheduleAssignment(Base):
    __tablename__ = "schedule_assignments"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("schedule_runs.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    date = Column(Date, nullable=False)
    shift_id = Column(Integer, ForeignKey("shifts.id"), nullable=False)
    is_override = Column(Boolean, default=False, nullable=False)

    run = relationship("ScheduleRun", back_populates="assignments")
    employee = relationship("Employee")
    shift = relationship("Shift")


class ScheduleRunConstraint(Base):
    """Records whether each soft constraint was violated in a given run."""

    __tablename__ = "schedule_run_constraints"
    run_id = Column(Integer, ForeignKey("schedule_runs.id"), primary_key=True)
    constraint_id = Column(String, ForeignKey("soft_constraints.id"), primary_key=True)
    was_relaxed = Column(Boolean, default=False, nullable=False)

    run = relationship("ScheduleRun", back_populates="run_constraints")
    constraint = relationship("SoftConstraintDef")


class AuditLog(Base):
    """Append-only log for manual overrides and schedule events."""

    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("schedule_runs.id"), nullable=True)
    assignment_id = Column(
        Integer, ForeignKey("schedule_assignments.id"), nullable=True
    )
    action = Column(String, nullable=False)  # "OVERRIDE" | "CREATE" | …
    actor = Column(String, nullable=True)
    timestamp = Column(String, nullable=False)  # ISO-8601
    detail = Column(JSON, nullable=True)
