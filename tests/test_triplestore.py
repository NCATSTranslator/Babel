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


def test_execute_query_does_not_retry_http_400(monkeypatch):
    ts = _mock_triplestore(
        monkeypatch,
        [
            HTTPError("https://example.invalid", 400, "Bad Request", hdrs=None, fp=None),
        ],
    )

    with pytest.raises(HTTPError):
        ts.execute_query("SELECT * WHERE {?s ?p ?o}")
