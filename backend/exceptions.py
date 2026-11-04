"""
Domain exceptions for the scheduler backend.

The API layer catches these and maps them to HTTP status codes:
  NotFoundError   → 404
  ConflictError   → 409
  ValidationError → 422  (Pydantic handles most of these automatically)
  InfeasibleError → 422  (solver could not find a solution)
"""


class NotFoundError(Exception):
    """Raised when a requested resource does not exist in the database."""

    def __init__(self, resource: str, identifier):
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} not found: {identifier}")


class ConflictError(Exception):
    """Raised when an operation would violate a uniqueness or state constraint."""

    pass


class InfeasibleError(Exception):
    """
    Raised when the solver cannot find any schedule satisfying the
    hard constraints.  Carries the diagnostic message from the solver.
    """

    def __init__(self, diagnostic: str):
        self.diagnostic = diagnostic
        super().__init__(diagnostic)
