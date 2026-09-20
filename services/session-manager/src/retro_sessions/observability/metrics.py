from collections.abc import Iterable

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

from retro_sessions.models.domain import ParticipantState, Session, SessionState


class ServiceMetrics:
    """Low-cardinality service metrics; session UUIDs stay out of time-series labels."""

    def __init__(self) -> None:
        self.registry = CollectorRegistry(auto_describe=True)
        self.requests = Counter(
            "retrobrowser_session_manager_requests_total",
            "Session Manager HTTP requests.",
            ("method", "operation", "status"),
            registry=self.registry,
        )
        self.request_duration = Histogram(
            "retrobrowser_session_manager_request_duration_seconds",
            "Session Manager HTTP request duration.",
            ("method", "operation"),
            registry=self.registry,
        )
        self.errors = Counter(
            "retrobrowser_session_manager_errors_total",
            "Structured Session Manager errors.",
            ("category", "operation"),
            registry=self.registry,
        )
        self.sessions = Gauge(
            "retrobrowser_sessions",
            "Current sessions by lifecycle state.",
            ("state",),
            registry=self.registry,
        )
        self.participants = Gauge(
            "retrobrowser_participants",
            "Current participants by lifecycle state.",
            ("state",),
            registry=self.registry,
        )
        self.runtime_capacity = Gauge(
            "retrobrowser_runtime_capacity",
            "Configured participant runtime capacity.",
            registry=self.registry,
        )
        self.runtime_used = Gauge(
            "retrobrowser_runtime_used",
            "Managed participant runtimes currently present.",
            registry=self.registry,
        )
        self.runtime_available = Gauge(
            "retrobrowser_runtime_available",
            "Configured runtime slots currently available.",
            registry=self.registry,
        )

    def refresh(self, sessions: Iterable[Session], *, runtime_used: int, capacity: int) -> None:
        current = tuple(sessions)
        for session_state in SessionState:
            self.sessions.labels(state=session_state.value).set(
                sum(session.state is session_state for session in current)
            )
        for participant_state in ParticipantState:
            self.participants.labels(state=participant_state.value).set(
                sum(
                    participant.state is participant_state
                    for session in current
                    for participant in session.participants
                )
            )
        self.runtime_capacity.set(capacity)
        self.runtime_used.set(runtime_used)
        self.runtime_available.set(max(0, capacity - runtime_used))

    def render(self) -> bytes:
        return generate_latest(self.registry)
