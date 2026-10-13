import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from scripts.kubernetes_load_test import run, send_request


def _start_server(status):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(status)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture
def ok_url():
    server = _start_server(200)
    yield f"http://127.0.0.1:{server.server_port}/predict"
    server.shutdown()
    server.server_close()


@pytest.fixture
def failing_url():
    server = _start_server(503)
    yield f"http://127.0.0.1:{server.server_port}/predict"
    server.shutdown()
    server.server_close()


def test_all_success_reports_zero_failed(ok_url):
    result = run(ok_url, duration=1, rate=20, timeout=2, workers=4)

    assert result["total"] >= 15
    assert result["failed"] == 0
    assert result["errors"] == {}


def test_http_errors_are_counted_not_crashing(failing_url):
    result = run(failing_url, duration=1, rate=20, timeout=2, workers=4)

    assert result["successful"] == 0
    assert result["failed"] == result["total"] >= 15
    assert result["errors"] == {"http_503": result["total"]}


def test_connection_refused_is_a_failure():
    assert (
        send_request("http://127.0.0.1:1/predict", {}, timeout=1)
        is not None
    )
    