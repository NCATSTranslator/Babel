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
    labeldir = os.path.join(here, "data")
    fac = NodeFactory(labeldir, BIOLINK_VERSION)
    fac.common_labels = {}
    return fac


def pytest_addoption(parser):
    parser.addoption(
        "--network",
        action="store_true",
        default=False,
        help="Run tests that require live internet access",
    )
    parser.addoption(
        "--pipeline",
        action="store_true",
        default=False,
        help="Run tests that invoke Snakemake rules (requires babel_downloads/)",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "unit: fast offline tests with no external dependencies")
    config.addinivalue_line("markers", "network: requires live internet access")
    config.addinivalue_line("markers", "slow: correct but takes >30s even offline")
    config.addinivalue_line("markers", "pipeline: invokes Snakemake rules; requires babel_downloads/")


def pytest_collection_modifyitems(config, items):
    skip_network = pytest.mark.skip(reason="pass --network to run")
    skip_pipeline = pytest.mark.skip(reason="pass --pipeline to run (and ensure babel_downloads/ exists)")
    for item in items:
        if "network" in item.keywords and not config.getoption("--network"):
            item.add_marker(skip_network)
        if "pipeline" in item.keywords and not config.getoption("--pipeline"):
            item.add_marker(skip_pipeline)
