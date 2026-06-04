import logging
import os
from json import JSONDecodeError
from string import Template
from time import sleep
from urllib.error import HTTPError, URLError

from SPARQLWrapper import JSON, POST, POSTDIRECTLY, SPARQLWrapper2

from src.util import LoggingUtil, get_config

logger = LoggingUtil.init_logging(__name__, logging.WARNING)


class TripleStore:
    """Connect to a SPARQL endpoint and provide services for loading and executing queries."""

    def __init__(self, hostname):
        self.service = SPARQLWrapper2(hostname)

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

    def execute_query(self, query, post=False, max_retries=None, retry_base_delay_seconds=None):
        """Execute a SPARQL query.

        :param query: A SPARQL query.
        :param post: If True, send the query via HTTP POST.
        :param max_retries: Maximum number of attempts before giving up (default from config).
        :param retry_base_delay_seconds: Base delay in seconds for exponential back-off (default from config).
        :return: Returns a JSON formatted object.
        """
        sparql_cfg = get_config().get("sparql", {})
        if max_retries is None:
            max_retries = sparql_cfg.get("max_retries", 3)
        if retry_base_delay_seconds is None:
            retry_base_delay_seconds = sparql_cfg.get("retry_base_delay_seconds", 1)

        if post:
            self.service.setRequestMethod(POSTDIRECTLY)
            self.service.setMethod(POST)
        self.service.setQuery(query)
        self.service.setReturnFormat(JSON)
        return self.dispatch_with_retries(max_retries, retry_base_delay_seconds)

    def dispatch_with_retries(self, max_retries: int, retry_base_delay_seconds: int):
        """Dispatch the query already loaded on self.service, retrying on transient failures."""
        attempt = 0
        while True:
            attempt += 1
            try:
                return self.service.query().convert()
            except HTTPError as e:
                if e.code < 500 or attempt >= max_retries:
                    raise
                self.wait_before_retry(attempt, max_retries, retry_base_delay_seconds, "SPARQL HTTP %d", e.code)
            except (JSONDecodeError, TimeoutError, URLError, OSError) as e:
                if attempt >= max_retries:
                    raise
                self.wait_before_retry(
                    attempt,
                    max_retries,
                    retry_base_delay_seconds,
                    "Transient SPARQL query failure (%s)",
                    e.__class__.__name__,
                )

    def wait_before_retry(self, attempt: int, max_retries: int, retry_base_delay_seconds: int, msg: str, *args) -> None:
        """Log a warning and sleep with exponential back-off before the next attempt."""
        wait_seconds = retry_base_delay_seconds * (2 ** (attempt - 1))
        logger.warning(
            msg + " on attempt %d/%d; retrying in %ss",
            *args,
            attempt,
            max_retries,
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
