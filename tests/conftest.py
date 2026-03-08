import os

import pytest

from src.node import NodeFactory

# Biolink Model version used throughout the test suite.  Should match config.yaml.
BIOLINK_VERSION = "4.3.6"


@pytest.fixture(scope="session")
def node_factory():
    """Session-scoped NodeFactory pointing at tests/testdata for label lookups.

    common_labels is pre-initialized to an empty dict so that tests don't
    require the babel_downloads/ pipeline output directory to exist.
    """
    here = os.path.abspath(os.path.dirname(__file__))
    labeldir = os.path.join(here, "testdata")
    fac = NodeFactory(labeldir, BIOLINK_VERSION)
    fac.common_labels = {}
    return fac
