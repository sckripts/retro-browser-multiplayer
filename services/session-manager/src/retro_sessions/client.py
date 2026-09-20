import argparse
import base64
import http.client
import json
import os
import socket
from secrets import token_bytes
from urllib.parse import quote
from uuid import UUID


def _request(
    method: str,
    path: str,
    *,
    user_id: str,
    display_name: str,
    payload: dict[str, object] | None = None,
    emit: bool = True,
) -> object:
    encoded = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
    headers = {
        "Authorization": f"Bearer {os.environ['SESSION_MANAGER_SERVICE_TOKEN']}",
        "X-Authenticated-User-Id": user_id,
        "X-Authenticated-User-Display-Name": display_name,
    }
    if encoded is not None:
        headers["Content-Type"] = "application/json"
    connection = http.client.HTTPConnection("127.0.0.1", 8080, timeout=240)
    try:
        connection.request(method, path, body=encoded, headers=headers)
        response = connection.getresponse()
        raw = response.read(1024 * 1024)
    finally:
        connection.close()
    document = json.loads(raw) if raw else {}
    if emit:
        print(json.dumps(document, separators=(",", ":")))  # noqa: T201
    if response.status < 200 or response.status >= 300:
        raise SystemExit(1)
    return document


def _websocket_status(host: str, port: int, path: str, token: str | None) -> int:
    query = "" if token is None else f"?token={quote(token, safe='')}"
    key = base64.b64encode(token_bytes(16)).decode()
    request = (
        f"GET {path}api/websockets{query} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Origin: http://127.0.0.1:8093\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        f"Sec-WebSocket-Key: {key}\r\n\r\n"
    ).encode()
    with socket.create_connection((host, port), timeout=10) as connection:
        connection.sendall(request)
        response = connection.recv(4096)
    first_line = response.split(b"\r\n", 1)[0].decode("ascii")
    return int(first_line.split()[1])


def main() -> None:
    parser = argparse.ArgumentParser(description="Milestone 8 private API proof client")
    subparsers = parser.add_subparsers(dest="action", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("--name", default="Milestone 8 Netplay")
    create.add_argument("--user-id", default="milestone8-host")
    create.add_argument("--display-name", default="Milestone Host")
    join = subparsers.add_parser("join")
    join.add_argument("session_id", type=UUID)
    join.add_argument("--user-id", default="milestone8-client")
    join.add_argument("--display-name", default="Milestone Client")
    launch = subparsers.add_parser("launch")
    launch.add_argument("session_id", type=UUID)
    launch.add_argument("--user-id", default="milestone8-host")
    launch.add_argument("--display-name", default="Milestone Host")
    kick = subparsers.add_parser("kick")
    kick.add_argument("session_id", type=UUID)
    kick.add_argument("participant_id", type=UUID)
    kick.add_argument("--user-id", default="milestone8-host")
    kick.add_argument("--display-name", default="Milestone Host")
    leave = subparsers.add_parser("leave")
    leave.add_argument("session_id", type=UUID)
    leave.add_argument("--user-id", default="milestone8-host")
    leave.add_argument("--display-name", default="Milestone Host")
    heartbeat = subparsers.add_parser("heartbeat")
    heartbeat.add_argument("session_id", type=UUID)
    heartbeat.add_argument("--user-id", default="milestone10-host")
    heartbeat.add_argument("--display-name", default="Milestone Host")
    get = subparsers.add_parser("get")
    get.add_argument("session_id", type=UUID)
    get.add_argument("--user-id", default="milestone10-host")
    get.add_argument("--display-name", default="Milestone Host")
    verify = subparsers.add_parser("verify-stream")
    verify.add_argument("session_id", type=UUID)
    verify.add_argument("--user-id", default="milestone9-host")
    verify.add_argument("--display-name", default="Milestone Host")
    arguments = parser.parse_args()
    if arguments.action == "create":
        _request(
            "POST",
            "/v1/sessions",
            user_id=arguments.user_id,
            display_name=arguments.display_name,
            payload={"display_name": arguments.name, "romm_rom_id": 1, "max_players": 2},
        )
    elif arguments.action == "join":
        _request(
            "POST",
            f"/v1/sessions/{arguments.session_id}/join",
            user_id=arguments.user_id,
            display_name=arguments.display_name,
        )
    elif arguments.action == "launch":
        _request(
            "POST",
            f"/v1/sessions/{arguments.session_id}/launch",
            user_id=arguments.user_id,
            display_name=arguments.display_name,
        )
    elif arguments.action == "kick":
        _request(
            "POST",
            (f"/v1/sessions/{arguments.session_id}/participants/{arguments.participant_id}/kick"),
            user_id=arguments.user_id,
            display_name=arguments.display_name,
        )
    elif arguments.action == "leave":
        _request(
            "POST",
            f"/v1/sessions/{arguments.session_id}/leave",
            user_id=arguments.user_id,
            display_name=arguments.display_name,
        )
    elif arguments.action == "heartbeat":
        _request(
            "POST",
            f"/v1/sessions/{arguments.session_id}/heartbeat",
            user_id=arguments.user_id,
            display_name=arguments.display_name,
        )
    elif arguments.action == "get":
        _request(
            "GET",
            f"/v1/sessions/{arguments.session_id}",
            user_id=arguments.user_id,
            display_name=arguments.display_name,
        )
    else:
        document = _request(
            "POST",
            f"/v1/sessions/{arguments.session_id}/launch",
            user_id=arguments.user_id,
            display_name=arguments.display_name,
            emit=False,
        )
        if not isinstance(document, dict):
            raise SystemExit("launch response is not an object")
        path = document.get("stream_path")
        token = document.get("access_token")
        if not isinstance(path, str) or not isinstance(token, str):
            raise SystemExit("launch response is missing safe stream material")
        if _websocket_status("edge", 8080, path, None) != 401:
            raise SystemExit("tokenless gameplay WebSocket was not rejected")
        if _websocket_status("edge", 8080, path, token) != 101:
            raise SystemExit("scoped controller token was not accepted")
        print("secure stream gate verified")  # noqa: T201


if __name__ == "__main__":
    main()
