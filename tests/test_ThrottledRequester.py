import threading
import time as time_module
from contextlib import contextmanager
from datetime import datetime as dt
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from src.babel_utils import ThrottledRequester


@contextmanager
def _local_server(delay_ms=0):
    """Start an ephemeral HTTP server on a free port, yield its URL, then shut down."""
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            time_module.sleep(delay_ms / 1000)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):  # suppress request logging to stdout
            pass

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}/"
    finally:
        # Ensure the server loop stops, the thread exits, and the socket is closed.
        server.shutdown()
        t.join(timeout=5)
        server.server_close()


@pytest.mark.unit
def test_throttling():
    """Second request within the throttle window must wait; total runtime must exceed 500 ms."""
    with _local_server(delay_ms=0) as url:
        tr = ThrottledRequester(500)
        now = dt.now()
        _response, throttle1 = tr.get(url)
        _response, throttle2 = tr.get(url)
        later = dt.now()

    runtime = later - now
    assert not throttle1                             # first call: no throttle
    assert throttle2                                 # second call: throttled
    assert runtime > timedelta(milliseconds=500)     # wait was enforced
    assert runtime < timedelta(milliseconds=1500)    # sanity: didn't wait too long


@pytest.mark.unit
def test_no_throttling():
    """When the request itself takes longer than the throttle window, no extra wait is added."""
    with _local_server(delay_ms=600) as url:
        tr = ThrottledRequester(500)
        now = dt.now()
        _response, throttle1 = tr.get(url)   # takes ~600 ms — longer than the 500 ms delta
        _response, throttle2 = tr.get(url)   # delta already elapsed; no throttle needed
        later = dt.now()

    runtime = later - now
    assert not throttle1                             # first call: no throttle
    assert not throttle2                             # second call: request was slow enough
    assert runtime > timedelta(milliseconds=600)     # at least one real delay occurred
