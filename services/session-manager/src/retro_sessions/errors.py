class SessionManagerError(Exception):
    """Base class for expected domain failures."""


class NotFoundError(SessionManagerError):
    """Requested domain object does not exist."""


class AuthorizationError(SessionManagerError):
    """Actor is not authorized for an operation."""


class ConflictError(SessionManagerError):
    """Operation conflicts with current state."""


class CapacityError(ConflictError):
    """Session has no free participant slot."""


class RepositoryConflict(ConflictError):
    """Optimistic repository revision no longer matches."""


class OrchestrationError(SessionManagerError):
    """A participant runtime could not reach or leave its required state."""
