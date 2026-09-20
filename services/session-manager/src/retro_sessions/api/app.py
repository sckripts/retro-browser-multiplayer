import asyncio
import hashlib
import hmac
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import timedelta
from secrets import compare_digest
from time import perf_counter
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import SecretStr, ValidationError

from retro_sessions.errors import (
    AuthorizationError,
    CapacityError,
    ConflictError,
    NotFoundError,
    OrchestrationError,
)
from retro_sessions.models.domain import (
    Actor,
    CreateSessionRequest,
    RuntimeCapacity,
    Session,
    SessionDiagnostic,
    SessionList,
    StreamLaunch,
)
from retro_sessions.observability import ServiceMetrics, log_event
from retro_sessions.services.session_service import SessionService

LOGGER = logging.getLogger(__name__)
UserIdHeader = Annotated[
    str,
    Header(
        alias="X-Authenticated-User-Id",
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:@-]*$",
    ),
]
DisplayNameHeader = Annotated[
    str,
    Header(alias="X-Authenticated-User-Display-Name", min_length=1, max_length=64),
]
AuthorizationHeader = Annotated[str | None, Header(alias="Authorization")]


def authenticated_actor(user_id: UserIdHeader, display_name: DisplayNameHeader) -> Actor:
    """Consume identity asserted by the authenticated private RomM caller."""
    try:
        return Actor(user_id=user_id, display_name=display_name)
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT) from error


def create_app(
    service: SessionService,
    *,
    service_token: SecretStr,
    cleanup_interval: timedelta = timedelta(seconds=10),
    metrics: ServiceMetrics | None = None,
) -> FastAPI:
    expected_token = service_token.get_secret_value()
    if len(expected_token) < 32:
        raise ValueError("service token must contain at least 32 characters")
    if cleanup_interval <= timedelta(0):
        raise ValueError("cleanup interval must be positive")
    service_metrics = metrics or ServiceMetrics()

    def audit_actor(user_id: str) -> str:
        """Create a rotation-scoped identifier without logging the upstream subject."""
        return hmac.new(
            expected_token.encode(),
            b"retrobrowser-audit-user\0" + user_id.encode(),
            hashlib.sha256,
        ).hexdigest()[:24]

    def audit(action: str, actor: Actor, session_id: UUID, **fields: object) -> None:
        log_event(
            LOGGER,
            logging.INFO,
            "session lifecycle action",
            event="audit",
            action=action,
            outcome="success",
            actor_id=audit_actor(actor.user_id),
            session_id=session_id,
            **fields,
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await asyncio.to_thread(service.reconcile_startup)

        async def cleanup_loop() -> None:
            while True:
                await asyncio.sleep(cleanup_interval.total_seconds())
                try:
                    await asyncio.to_thread(service.sweep)
                except Exception:
                    service_metrics.errors.labels(category="internal", operation="sweep").inc()
                    LOGGER.exception("session lifecycle sweep failed")

        task = asyncio.create_task(cleanup_loop())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    def authenticate_service(request: Request, authorization: AuthorizationHeader = None) -> None:
        scheme, separator, credential = (authorization or "").partition(" ")
        valid = (
            separator == " "
            and scheme.lower() == "bearer"
            and compare_digest(credential, expected_token)
        )
        if not valid:
            service_metrics.errors.labels(
                category="authentication", operation=request.url.path
            ).inc()
            log_event(
                LOGGER,
                logging.WARNING,
                "invalid service credential",
                event="request_error",
                category="authentication",
                operation=request.url.path,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid service credential",
                headers={"WWW-Authenticate": "Bearer"},
            )

    app = FastAPI(
        title="Retro Session Manager",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    v1 = APIRouter(prefix="/v1", dependencies=[Depends(authenticate_service)])

    @app.middleware("http")
    async def observe_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = perf_counter()
        response: Response
        try:
            response = await call_next(request)
        except Exception:
            operation = request.url.path
            service_metrics.requests.labels(request.method, operation, "500").inc()
            service_metrics.request_duration.labels(request.method, operation).observe(
                perf_counter() - started
            )
            raise
        route = request.scope.get("route")
        operation = getattr(route, "path", request.url.path)
        service_metrics.requests.labels(request.method, operation, str(response.status_code)).inc()
        service_metrics.request_duration.labels(request.method, operation).observe(
            perf_counter() - started
        )
        return response

    def record_error(request: Request, category: str, error: Exception) -> None:
        route = request.scope.get("route")
        operation = str(getattr(route, "path", request.url.path))
        service_metrics.errors.labels(category=category, operation=operation).inc()
        log_event(
            LOGGER,
            logging.WARNING,
            str(error),
            event="request_error",
            category=category,
            operation=operation,
        )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, error: NotFoundError) -> JSONResponse:
        record_error(request, "not_found", error)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": str(error)})

    @app.exception_handler(AuthorizationError)
    async def authorization_handler(request: Request, error: AuthorizationError) -> JSONResponse:
        record_error(request, "authorization", error)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"error": str(error)})

    @app.exception_handler(CapacityError)
    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, error: ConflictError) -> JSONResponse:
        record_error(request, "conflict", error)
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"error": str(error)})

    @app.exception_handler(OrchestrationError)
    async def orchestration_handler(request: Request, error: OrchestrationError) -> JSONResponse:
        record_error(request, "orchestration", error)
        return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content={"error": str(error)})

    @app.get("/healthz")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/readyz")
    def readiness(response: Response) -> dict[str, bool]:
        ready = service.ready()
        if not ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"ready": ready}

    @app.get("/metrics", include_in_schema=False)
    def prometheus_metrics() -> Response:
        sessions, runtime_used, capacity = service.operational_snapshot()
        service_metrics.refresh(sessions, runtime_used=runtime_used, capacity=capacity)
        return Response(
            service_metrics.render(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @v1.get("/operations/capacity", response_model=RuntimeCapacity)
    def runtime_capacity() -> RuntimeCapacity:
        return service.capacity()

    @v1.get("/sessions/{session_id}/diagnostics", response_model=SessionDiagnostic)
    def session_diagnostics(session_id: UUID) -> SessionDiagnostic:
        return service.diagnostics(session_id)

    @v1.post("/sessions", response_model=Session, status_code=status.HTTP_201_CREATED)
    def create_session(
        request: CreateSessionRequest,
        actor: Annotated[Actor, Depends(authenticated_actor)],
    ) -> Session:
        session = service.create(actor, request)
        audit("session.create", actor, session.session_id)
        return session

    @v1.get("/sessions", response_model=SessionList)
    def list_sessions() -> SessionList:
        return SessionList(items=service.discover())

    @v1.get("/sessions/{session_id}", response_model=Session)
    def get_session(session_id: UUID) -> Session:
        return service.get(session_id)

    @v1.post("/sessions/{session_id}/join", response_model=Session)
    def join_session(
        session_id: UUID,
        actor: Annotated[Actor, Depends(authenticated_actor)],
    ) -> Session:
        session = service.join(session_id, actor)
        audit("participant.join", actor, session_id)
        return session

    @v1.post("/sessions/{session_id}/leave", response_model=Session)
    def leave_session(
        session_id: UUID,
        actor: Annotated[Actor, Depends(authenticated_actor)],
    ) -> Session:
        session = service.leave(session_id, actor)
        audit("participant.leave", actor, session_id)
        return session

    @v1.post("/sessions/{session_id}/launch", response_model=StreamLaunch)
    def launch_session(
        session_id: UUID,
        actor: Annotated[Actor, Depends(authenticated_actor)],
    ) -> StreamLaunch:
        launch = service.launch(session_id, actor)
        audit("stream.launch", actor, session_id)
        return launch

    @v1.post("/sessions/{session_id}/heartbeat", response_model=Session)
    def heartbeat_session(
        session_id: UUID,
        actor: Annotated[Actor, Depends(authenticated_actor)],
    ) -> Session:
        return service.heartbeat(session_id, actor)

    @v1.post(
        "/sessions/{session_id}/participants/{participant_id}/kick",
        response_model=Session,
    )
    def kick_participant(
        session_id: UUID,
        participant_id: UUID,
        actor: Annotated[Actor, Depends(authenticated_actor)],
    ) -> Session:
        session = service.kick(session_id, actor, participant_id)
        audit("participant.kick", actor, session_id, participant_id=participant_id)
        return session

    @v1.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
    def close_session(
        session_id: UUID,
        actor: Annotated[Actor, Depends(authenticated_actor)],
    ) -> Response:
        service.close(session_id, actor)
        audit("session.close", actor, session_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    app.include_router(v1)
    return app
