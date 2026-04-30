import logging
import os
from json import JSONDecodeError
from string import Template
from time import sleep
from urllib.error import HTTPError, URLError

from SPARQLWrapper import JSON, POST, POSTDIRECTLY, SPARQLWrapper2

from src.util import LoggingUtil

logger = LoggingUtil.init_logging(__name__, logging.ERROR)

SPARQL_MAX_RETRIES = 3
SPARQL_RETRY_BASE_DELAY_SECONDS = 1


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

    def execute_query(self, query, post=False):
        """Execute a SPARQL query.

        :param query: A SPARQL query.
        :return: Returns a JSON formatted object.
        """
        if post:
            self.service.setRequestMethod(POSTDIRECTLY)
            self.service.setMethod(POST)
        self.service.setQuery(query)
        self.service.setReturnFormat(JSON)
        return self._execute_query_with_retries()

    def _execute_query_with_retries(self):
        attempt = 0
        while True:
            attempt += 1
            try:
                return self.service.query().convert()
            except HTTPError as e:
                if e.code < 500 or attempt >= SPARQL_MAX_RETRIES:
                    raise
                wait_seconds = SPARQL_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "SPARQL HTTP %d on attempt %d/%d; retrying in %ss",
                    e.code,
                    attempt,
                    SPARQL_MAX_RETRIES,
                    wait_seconds,
                )
                sleep(wait_seconds)
            except (JSONDecodeError, TimeoutError, URLError, OSError) as e:
                if attempt >= SPARQL_MAX_RETRIES:
                    raise
                wait_seconds = SPARQL_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "Transient SPARQL query failure (%s) on attempt %d/%d; retrying in %ss",
                    e.__class__.__name__,
                    attempt,
                    SPARQL_MAX_RETRIES,
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
            result = list(map(lambda b: {val: b[val].value if val in b else None for val in outputs}, response.bindings))
        logger.debug("query result: %s", result)
        return result

    def query_template(self, template_text, outputs, inputs=[], post=False):
        """Given template text, inputs, and outputs, execute a query."""
        return self.query(Template(template_text).safe_substitute(**inputs), outputs, post=post)

    def query_template_file(self, template_file, outputs, inputs=[]):
        """Given the name of a template file, inputs, and outputs, execute a query."""
        return self.query(self.get_template_text(template_file), inputs, outputs)
