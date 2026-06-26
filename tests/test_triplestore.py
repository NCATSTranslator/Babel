from json import JSONDecodeError
from urllib.error import HTTPError

import pytest

from src.triplestore import TripleStore


class _FakeQueryResult:
    def __init__(self, value):
        self._value = value

    def convert(self):
        if isinstance(self._value, Exception):
            raise self._value
        return self._value


class _FakeService:
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
    ts = TripleStore("https://example.invalid/sparql")
    ts.service = _FakeService(responses)
    monkeypatch.setattr("src.triplestore.sleep", lambda _: None)
    return ts


@pytest.mark.unit
def test_execute_query_retries_on_json_decode_error(monkeypatch):
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


@pytest.mark.unit
def test_execute_query_does_not_retry_http_400(monkeypatch):
    ts = _mock_triplestore(
        monkeypatch,
        [
            HTTPError("https://example.invalid", 400, "Bad Request", hdrs=None, fp=None),
        ],
    )

    with pytest.raises(HTTPError):
        ts.execute_query("SELECT * WHERE {?s ?p ?o}")


@pytest.mark.unit
def test_execute_query_raises_after_all_attempts_exhausted(monkeypatch):
    """After max_attempts failures the original exception propagates."""
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


@pytest.mark.unit
def test_execute_query_rejects_invalid_max_attempts(monkeypatch):
    ts = _mock_triplestore(monkeypatch, [])
    with pytest.raises(ValueError, match="max_attempts"):
        ts.execute_query("SELECT * WHERE {?s ?p ?o}", max_attempts=0)


@pytest.mark.unit
def test_execute_query_rejects_negative_delay(monkeypatch):
    ts = _mock_triplestore(monkeypatch, [])
    with pytest.raises(ValueError, match="retry_base_delay_seconds"):
        ts.execute_query("SELECT * WHERE {?s ?p ?o}", retry_base_delay_seconds=-1)
