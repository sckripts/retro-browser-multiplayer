class RuntimeAgentError(Exception):
    """Base error exposed by the narrow agent API."""


class ConflictError(RuntimeAgentError):
    """The requested identifier is already used by a different runtime."""


class NotFoundError(RuntimeAgentError):
    """A managed runtime does not exist."""


class OwnershipError(RuntimeAgentError):
    """An operation targeted a container not owned by this agent."""


class EngineError(RuntimeAgentError):
    """The Docker Engine rejected or failed an operation."""
