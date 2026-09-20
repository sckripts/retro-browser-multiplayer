import json
import logging
import os
import socket
import socketserver
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Any, cast
from uuid import UUID

from pydantic import ValidationError

from retro_runtime.errors import (
    ConflictError,
    EngineError,
    NotFoundError,
    OwnershipError,
)
from retro_runtime.models import CreateRuntimeRequest
from retro_runtime.observability import log_event
from retro_runtime.service import RuntimeService

MAX_REQUEST_BYTES = 64 * 1024
LOGGER = logging.getLogger(__name__)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


class RuntimeRequestHandler(BaseHTTPRequestHandler):
    server: RuntimeUnixServer

    def log_message(self, format: str, *args: object) -> None:
        # The default logger may include query strings. This API has none and
        # intentionally leaves structured logging to the service supervisor.
        return

    def _json(self, status: HTTPStatus, payload: object) -> None:
        encoded = json.dumps(payload, separators=(",", ":"), default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _error_event(self, category: str, error: Exception) -> None:
        log_event(
            LOGGER,
            logging.WARNING,
            str(error),
            event="request_error",
            category=category,
            operation=self.command + " " + self.path,
        )

    def _body(self) -> dict[str, Any]:
        if self.headers.get_content_type() != "application/json":
            raise ValueError("Content-Type must be application/json")
        length_value = self.headers.get("Content-Length")
        if length_value is None or not length_value.isdigit():
            raise ValueError("a valid Content-Length is required")
        length = int(length_value)
        if length < 2 or length > MAX_REQUEST_BYTES:
            raise ValueError("request body size is invalid")
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("request body is not valid JSON") from error
        if not isinstance(parsed, dict):
            raise ValueError("request body must be a JSON object")
        return cast(dict[str, Any], parsed)

    def _runtime_id(self, *, suffix: str = "") -> UUID | None:
        prefix = "/v1/runtimes/"
        if not self.path.startswith(prefix):
            return None
        value = self.path.removeprefix(prefix)
        if suffix:
            if not value.endswith(suffix):
                return None
            value = value.removesuffix(suffix)
        if "/" in value:
            return None
        try:
            return UUID(value)
        except ValueError:
            return None

    def _dispatch(self) -> None:
        service = self.server.service
        if self.command == "GET" and self.path == "/v1/health":
            healthy = service.health()
            status = HTTPStatus.OK if healthy else HTTPStatus.SERVICE_UNAVAILABLE
            self._json(status, {"ok": healthy})
            return
        if self.command == "GET" and self.path == "/v1/runtimes":
            records = [item.model_dump(mode="json") for item in service.list_managed_runtimes()]
            self._json(HTTPStatus.OK, {"items": records})
            return
        if self.command == "GET" and self.path == "/v1/capacity":
            self._json(HTTPStatus.OK, service.capacity().model_dump(mode="json"))
            return
        if self.command == "POST" and self.path == "/v1/runtimes":
            request = CreateRuntimeRequest.model_validate(self._body())
            record = service.create_runtime(request)
            self._json(HTTPStatus.CREATED, record.model_dump(mode="json"))
            return
        if self.command == "POST":
            runtime_id = self._runtime_id(suffix="/stop")
            if runtime_id is not None:
                record = service.stop_runtime(runtime_id)
                self._json(HTTPStatus.OK, record.model_dump(mode="json"))
                return
        if self.command == "GET":
            runtime_id = self._runtime_id()
            if runtime_id is not None:
                record = service.inspect_runtime(runtime_id)
                self._json(HTTPStatus.OK, record.model_dump(mode="json"))
                return
        if self.command == "DELETE":
            runtime_id = self._runtime_id()
            if runtime_id is not None:
                service.remove_runtime(runtime_id)
                self._json(HTTPStatus.OK, {"removed": True})
                return
        self._json(HTTPStatus.NOT_FOUND, {"error": "endpoint not found"})

    def _handle(self) -> None:
        try:
            self._dispatch()
        except ValidationError as error:
            self._error_event("validation", error)
            self._json(
                HTTPStatus.BAD_REQUEST,
                {"error": "invalid request", "details": error.errors(include_input=False)},
            )
        except ValueError as error:
            self._error_event("validation", error)
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except OwnershipError as error:
            self._error_event("ownership", error)
            self._json(HTTPStatus.FORBIDDEN, {"error": str(error)})
        except NotFoundError as error:
            self._error_event("not_found", error)
            self._json(HTTPStatus.NOT_FOUND, {"error": str(error)})
        except ConflictError as error:
            self._error_event("conflict", error)
            self._json(HTTPStatus.CONFLICT, {"error": str(error)})
        except EngineError:
            log_event(
                LOGGER,
                logging.ERROR,
                "container engine operation failed",
                event="request_error",
                category="engine",
                operation=self.command + " " + self.path,
            )
            self._json(HTTPStatus.BAD_GATEWAY, {"error": "container engine operation failed"})
        except Exception:
            log_event(
                LOGGER,
                logging.ERROR,
                "unhandled Runtime Agent request failure",
                event="request_error",
                category="internal",
                operation=self.command + " " + self.path,
                exc_info=True,
            )
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal server error"})

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def do_DELETE(self) -> None:
        self._handle()


class UnixStreamServer(socketserver.TCPServer):
    address_family = socket.AddressFamily(1)


class ThreadingUnixServer(socketserver.ThreadingMixIn, UnixStreamServer):
    daemon_threads = True


class RuntimeUnixServer(ThreadingUnixServer):
    service: RuntimeService

    def __init__(self, socket_path: str, service: RuntimeService) -> None:
        super().__init__(cast(Any, socket_path), RuntimeRequestHandler)
        self.service = service

    def server_bind(self) -> None:
        super().server_bind()
        socket_path = cast(str, self.server_address)
        os.chmod(socket_path, 0o660)
