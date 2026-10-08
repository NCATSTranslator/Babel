import os
from json import JSONDecodeError
from string import Template
from time import sleep
from urllib.error import HTTPError

from SPARQLWrapper import JSON, POST, POSTDIRECTLY, SPARQLWrapper2

from src.babel_utils import get_user_agent
from src.util import get_config, get_logger

logger = get_logger(__name__)


class TripleStore:
    """Connect to a SPARQL endpoint and provide services for loading and executing queries."""

    def __init__(self, hostname):
        self.service = SPARQLWrapper2(hostname)
        self.service.addCustomHttpHeader("User-Agent", get_user_agent())

    def get_template(self, query_name):
        """Load a template given a template name"""
        return Template(self.get_template_text(query_name))

    def get_template_text(self, query_name):
        """Get the text of a template given its name"""
        query = None
        fn = os.path.join(os.path.dirname(__file__), "query", f"{query_name}.sparql")
        with open(fn) as stream:
            query = stream.read()
        return query

    def execute_query(self, query, post=False, max_attempts=None, retry_base_delay_seconds=None):
        """Execute a SPARQL query.

        :param query: A SPARQL query.
        :param post: If True, send the query via HTTP POST.
        :param max_attempts: Total number of attempts (initial + retries) before giving up (default from config).
        :param retry_base_delay_seconds: Base delay in seconds for exponential back-off (default from config).
        :return: Returns a JSON formatted object.
        """
        sparql_cfg = get_config().get("sparql", {})
        if max_attempts is None:
            max_attempts = sparql_cfg.get("max_attempts", 3)
        if retry_base_delay_seconds is None:
            retry_base_delay_seconds = sparql_cfg.get("retry_base_delay_seconds", 1)

        if max_attempts < 1:
            raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")
        if retry_base_delay_seconds < 0:
            raise ValueError(f"retry_base_delay_seconds must be >= 0, got {retry_base_delay_seconds}")

        if post:
            self.service.setRequestMethod(POSTDIRECTLY)
            self.service.setMethod(POST)
        self.service.setQuery(query)
        self.service.setReturnFormat(JSON)
        return self._dispatch_with_retries(max_attempts, retry_base_delay_seconds)

    # HTTP status codes that indicate a transient server-side condition worth retrying.
    # 429 (rate limiting) and 5xx (server errors) are transient; 4xx client errors are not.
    _RETRYABLE_HTTP_CODES = frozenset({429, 500, 502, 503, 504})

    def _dispatch_with_retries(self, max_attempts: int, retry_base_delay_seconds: float):
        """Dispatch the query already loaded on self.service, retrying on transient failures."""
        attempt = 0
        while True:
            attempt += 1
            try:
                return self.service.query().convert()
            except HTTPError as e:
                if e.code not in self._RETRYABLE_HTTP_CODES or attempt >= max_attempts:
                    raise
                self._wait_before_retry(attempt, max_attempts, retry_base_delay_seconds, "SPARQL HTTP %d", e.code)
            except (JSONDecodeError, OSError) as e:
                if attempt >= max_attempts:
                    raise
                self._wait_before_retry(
                    attempt,
                    max_attempts,
                    retry_base_delay_seconds,
                    "Transient SPARQL query failure (%s)",
                    e.__class__.__name__,
                )

    def _wait_before_retry(
        self, attempt: int, max_attempts: int, retry_base_delay_seconds: float, msg: str, *args
    ) -> None:
        """Log a warning and sleep with exponential back-off before the next attempt."""
        wait_seconds = retry_base_delay_seconds * (2 ** (attempt - 1))
        logger.warning(
            msg + " on attempt %d/%d; retrying in %ss",
            *args,
            attempt,
            max_attempts,
            wait_seconds,
        )
        sleep(wait_seconds)

    def query(self, query_text, outputs, flat=False, post=False):
        """Execute a fully formed query and return results."""
        response = self.execute_query(query_text, post)
        result = None
        if flat:
            result = list(map(lambda b: [b[val].value if val in b else None for val in outputs], response.bindings))
        else:
            result = list(
                map(lambda b: {val: b[val].value if val in b else None for val in outputs}, response.bindings)
            )
        logger.debug("query result: %s", result)
        return result

    def query_template(self, template_text, outputs, inputs=[], post=False):
        """Given template text, inputs, and outputs, execute a query."""
        return self.query(Template(template_text).safe_substitute(**inputs), outputs, post=post)

    def query_template_file(self, template_file, outputs, inputs=[]):
        """Given the name of a template file, inputs, and outputs, execute a query."""
        return self.query(self.get_template_text(template_file), inputs, outputs)
