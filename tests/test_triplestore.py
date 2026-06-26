"""Tests for TripleStore.execute_query() retry and error-handling logic.

The retry path is tested without a live SPARQL server using two thin fakes:

_FakeQueryResult — wraps a single return value for one call to .convert().
    If the value is an Exception instance, .convert() raises it; otherwise it
    returns the value.  This mirrors SPARQLWrapper2's QueryResult contract,
    where .convert() is what actually parses the HTTP response and can raise
    JSONDecodeError or HTTPError if the body is malformed or the status was bad.

_FakeService — replaces ts.service with a queue of _FakeQueryResult values.
    Each call to .query() pops the next entry; if the queue is empty it raises
    RuntimeError so a test that forgot to supply enough responses fails loudly.
    The no-op setRequestMethod / setMethod / setQuery / setReturnFormat stubs
    absorb the configuration calls that execute_query() makes before dispatch.

_mock_triplestore() wires both fakes into a TripleStore and patches out
`sleep` so retry delays are instant in tests.
"""

from json import JSONDecodeError
from urllib.error import HTTPError

import pytest

from src.triplestore import TripleStore


class _FakeQueryResult:
    """Single query result consumed by one .convert() call.

    Stores either a plain return value or an exception.  If an exception is
    stored, .convert() raises it, simulating a failed HTTP round-trip (e.g.
    JSONDecodeError when the server returns malformed JSON, or HTTPError when
    SPARQLWrapper surfaces an HTTP error status).
    """

    def __init__(self, value):
        self._value = value

    def convert(self):
        if isinstance(self._value, Exception):
            raise self._value
        return self._value


class _FakeService:
    """Replacement for SPARQLWrapper2 that replays a pre-loaded response queue.

    Construct with an iterable of values (plain objects or Exception instances)
    that will be returned by successive .query() calls.  Each call pops the
    first entry and wraps it in _FakeQueryResult.  Attempting to call .query()
    on an empty queue raises RuntimeError, which surfaces in tests as a clear
    "you didn't supply enough responses" failure rather than a silent wrong answer.

    The set*() methods are no-ops that absorb the configuration calls
    execute_query() makes before dispatching (setRequestMethod, setMethod,
    setQuery, setReturnFormat).
    """

    def __init__(self, values):
        self._values = list(values)

    def setRequestMethod(self, _):
        return None

    def setMethod(self, _):
        return None

    def setQuery(self, _):
        return None

    def setReturnFormat(self, _):
        return None

    def query(self):
        if not self._values:
            raise RuntimeError("No values remaining in fake service")
        return _FakeQueryResult(self._values.pop(0))


def _mock_triplestore(monkeypatch, responses):
    """Return a TripleStore whose network layer is replaced with _FakeService.

    `responses` is passed directly to _FakeService, so each entry may be a
    plain dict/value (success) or an Exception subclass instance (failure).
    `sleep` is patched to a no-op so retry back-off doesn't slow down tests.
    """
    ts = TripleStore("https://example.invalid/sparql")
    ts.service = _FakeService(responses)
    monkeypatch.setattr("src.triplestore.sleep", lambda _: None)
    return ts


# ---------------------------------------------------------------------------
# Retry behaviour — transient errors
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_execute_query_retries_on_json_decode_error(monkeypatch):
    """A JSONDecodeError on the first attempt is retried; the second succeeds."""
    ts = _mock_triplestore(
        monkeypatch,
        [
            JSONDecodeError("bad json", "{}", 1),
            {"ok": True},
        ],
    )

    result = ts.execute_query("SELECT * WHERE {?s ?p ?o}")
    assert result == {"ok": True}


@pytest.mark.unit
def test_execute_query_retries_on_http_503(monkeypatch):
    """HTTP 503 (service unavailable) is a transient server error and should be retried."""
    ts = _mock_triplestore(
        monkeypatch,
        [
            HTTPError("https://example.invalid", 503, "Service Unavailable", hdrs=None, fp=None),
            {"ok": True},
        ],
    )

    result = ts.execute_query("SELECT * WHERE {?s ?p ?o}")
    assert result == {"ok": True}


@pytest.mark.unit
def test_execute_query_retries_on_http_429(monkeypatch):
    """HTTP 429 (rate limiting) is a transient error and should be retried."""
    ts = _mock_triplestore(
        monkeypatch,
        [
            HTTPError("https://example.invalid", 429, "Too Many Requests", hdrs=None, fp=None),
            {"ok": True},
        ],
    )

    result = ts.execute_query("SELECT * WHERE {?s ?p ?o}")
    assert result == {"ok": True}


# ---------------------------------------------------------------------------
# Non-retryable errors
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_execute_query_does_not_retry_http_400(monkeypatch):
    """HTTP 400 is a client error (bad query); it propagates immediately without retrying."""
    ts = _mock_triplestore(
        monkeypatch,
        [
            HTTPError("https://example.invalid", 400, "Bad Request", hdrs=None, fp=None),
        ],
    )

    with pytest.raises(HTTPError):
        ts.execute_query("SELECT * WHERE {?s ?p ?o}")


# ---------------------------------------------------------------------------
# Retry exhaustion
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_execute_query_raises_after_all_attempts_exhausted(monkeypatch):
    """When every attempt fails, the exception from the final attempt propagates to the caller."""
    ts = _mock_triplestore(
        monkeypatch,
        [
            HTTPError("https://example.invalid", 503, "Service Unavailable", hdrs=None, fp=None),
            HTTPError("https://example.invalid", 503, "Service Unavailable", hdrs=None, fp=None),
            HTTPError("https://example.invalid", 503, "Service Unavailable", hdrs=None, fp=None),
        ],
    )

    with pytest.raises(HTTPError) as exc_info:
        ts.execute_query("SELECT * WHERE {?s ?p ?o}", max_attempts=3)
    assert exc_info.value.code == 503


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_execute_query_rejects_invalid_max_attempts(monkeypatch):
    """max_attempts=0 is rejected immediately with a ValueError before any query is sent."""
    ts = _mock_triplestore(monkeypatch, [])
    with pytest.raises(ValueError, match="max_attempts"):
        ts.execute_query("SELECT * WHERE {?s ?p ?o}", max_attempts=0)


@pytest.mark.unit
def test_execute_query_rejects_negative_delay(monkeypatch):
    """A negative retry_base_delay_seconds is rejected immediately with a ValueError."""
    ts = _mock_triplestore(monkeypatch, [])
    with pytest.raises(ValueError, match="retry_base_delay_seconds"):
        ts.execute_query("SELECT * WHERE {?s ?p ?o}", retry_base_delay_seconds=-1)
