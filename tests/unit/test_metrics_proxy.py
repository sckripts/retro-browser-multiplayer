import threading
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from typing import cast
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from session_entrypoint import metrics_proxy


class FakeMetricsResponse:
    def __enter__(self) -> FakeMetricsResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return

    def read(self, _limit: int) -> bytes:
        return b"# HELP fps Browser FPS\nfps 60\n"


@pytest.fixture
def metrics_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[str, list[Request]]]:
    monkeypatch.setenv("RETROBROWSER_METRICS_TOKEN", "m" * 64)
    monkeypatch.setenv("SELKIES_MASTER_TOKEN", "s" * 64)
    monkeypatch.setenv("SELKIES_SUBFOLDER", "/stream/participant")
    upstream_requests: list[Request] = []

    def fake_urlopen(request: Request, timeout: int) -> FakeMetricsResponse:
        assert timeout == 3
        upstream_requests.append(request)
        return FakeMetricsResponse()

    monkeypatch.setattr(metrics_proxy, "urlopen", fake_urlopen)
    server = ThreadingHTTPServer(("127.0.0.1", 0), metrics_proxy.MetricsProxyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = cast(tuple[str, int], server.server_address)
    try:
        yield f"http://{host}:{port}", upstream_requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_metrics_proxy_requires_scoped_token_and_uses_master_only_upstream(
    metrics_server: tuple[str, list[Request]],
) -> None:
    base_url, upstream_requests = metrics_server
    assert urlopen(f"{base_url}/healthz").read() == b"ok\n"  # noqa: S310 - loopback test
    with pytest.raises(HTTPError) as failure:
        urlopen(f"{base_url}/metrics")  # noqa: S310 - loopback test
    assert failure.value.code == 401

    body = urlopen(  # noqa: S310 - loopback test
        f"{base_url}/metrics?token={'m' * 64}"
    ).read()
    assert body == b"# HELP fps Browser FPS\nfps 60\n"
    assert len(upstream_requests) == 1
    assert upstream_requests[0].full_url.endswith("/stream/participant/api/metrics")
    assert upstream_requests[0].get_header("Authorization") == "Bearer " + "s" * 64
