import argparse
import http.client
import json
from pathlib import Path
from uuid import UUID

from retro_runtime.docker.client import UnixSocketConnection

MAX_RESPONSE_BYTES = 1024 * 1024


class RuntimeAgentClient:
    def __init__(self, socket_path: Path) -> None:
        self.socket_path = socket_path

    def request(
        self, method: str, path: str, payload: dict[str, object] | None = None
    ) -> tuple[int, object]:
        connection: http.client.HTTPConnection = UnixSocketConnection(self.socket_path)
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        headers = {"Content-Type": "application/json"} if body is not None else {}
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read(MAX_RESPONSE_BYTES)
            return response.status, json.loads(raw)
        finally:
            connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Runtime Agent UNIX-socket client")
    parser.add_argument("--socket", type=Path, default=Path("/run/retrobrowser/runtime-agent.sock"))
    subparsers = parser.add_subparsers(dest="action", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("request", type=Path)
    for action in ["inspect", "stop", "remove"]:
        command = subparsers.add_parser(action)
        command.add_argument("participant_id", type=UUID)
    subparsers.add_parser("list")
    subparsers.add_parser("capacity")
    subparsers.add_parser("health")
    arguments = parser.parse_args()
    client = RuntimeAgentClient(arguments.socket)
    if arguments.action == "create":
        raw = arguments.request.read_bytes()
        if len(raw) > 64 * 1024:
            raise SystemExit("request file is too large")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise SystemExit("request file must contain a JSON object")
        status, response = client.request("POST", "/v1/runtimes", payload)
    elif arguments.action == "list":
        status, response = client.request("GET", "/v1/runtimes")
    elif arguments.action == "health":
        status, response = client.request("GET", "/v1/health")
    elif arguments.action == "capacity":
        status, response = client.request("GET", "/v1/capacity")
    else:
        participant_id = arguments.participant_id
        if arguments.action == "inspect":
            status, response = client.request("GET", f"/v1/runtimes/{participant_id}")
        elif arguments.action == "stop":
            status, response = client.request("POST", f"/v1/runtimes/{participant_id}/stop")
        else:
            status, response = client.request("DELETE", f"/v1/runtimes/{participant_id}")
    print(json.dumps(response, indent=2, sort_keys=True))  # noqa: T201
    if status < 200 or status >= 300:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
