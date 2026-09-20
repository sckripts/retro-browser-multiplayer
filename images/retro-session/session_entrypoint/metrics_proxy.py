import hmac
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

MAX_METRICS_BYTES = 2 * 1024 * 1024


class MetricsProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def _response(self, status: HTTPStatus, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path == "/healthz":
            self._response(HTTPStatus.OK, b"ok\n")
            return
        values = parse_qs(parsed.query, keep_blank_values=True)
        supplied = values.get("token", [])
        expected = os.environ["RETROBROWSER_METRICS_TOKEN"]
        if (
            parsed.path != "/metrics"
            or len(supplied) != 1
            or not hmac.compare_digest(supplied[0], expected)
        ):
            self._response(HTTPStatus.UNAUTHORIZED, b"unauthorized\n")
            return
        subfolder = os.environ["SELKIES_SUBFOLDER"]
        master_token = os.environ["SELKIES_MASTER_TOKEN"]
        request = Request(
            f"http://127.0.0.1:8080{subfolder}/api/metrics",
            headers={"Authorization": f"Bearer {master_token}"},
        )
        try:
            with urlopen(request, timeout=3) as response:  # noqa: S310 - fixed loopback URL
                data = response.read(MAX_METRICS_BYTES + 1)
            if len(data) > MAX_METRICS_BYTES:
                self._response(HTTPStatus.BAD_GATEWAY, b"upstream response too large\n")
                return
        except HTTPError, URLError, TimeoutError:
            self._response(HTTPStatus.BAD_GATEWAY, b"metrics upstream unavailable\n")
            return
        self._response(HTTPStatus.OK, data)


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 9091), MetricsProxyHandler)  # noqa: S104
    server.serve_forever()


if __name__ == "__main__":
    main()
