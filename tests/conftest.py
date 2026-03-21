import os

import pytest

from src.node import NodeFactory
from src.util import get_config

# Biolink Model version used throughout the test suite.  Should match config.yaml.
BIOLINK_VERSION = get_config()["biolink_version"]

# Per-mark timeout overrides (pytest-timeout); unit tests inherit the global timeout = 30
MARK_TIMEOUTS = {
    "network": 600,
    "slow": 600,
    "pipeline": 3600,
}

@pytest.fixture(scope="session")
def node_factory():
    """Session-scoped NodeFactory pointing at tests/data for label lookups.

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
    parser.addoption(
        "--all",
        action="store_true",
        default=False,
        help="Run all tests (equivalent to --network --pipeline)",
    )
    parser.addoption(
        "--regenerate",
        action="store_true",
        default=False,
        help=(
            "Force pipeline processing fixtures to re-run write_X_ids() even when "
            "their output files already exist in the intermediate directory. "
            "Without this flag, existing files are treated as up-to-date and reused."
        ),
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "unit: fast offline tests with no external dependencies")
    config.addinivalue_line("markers", "network: requires live internet access")
    config.addinivalue_line("markers", "slow: correct but takes >30s even offline")
    config.addinivalue_line("markers", "pipeline: invokes Snakemake rules; requires babel_downloads/")

    # Auto-disable coverage when xdist workers are requested.
    # Combining pytest-cov with -n causes an OSError("cannot send (already closed?)")
    # from execnet during pytest_sessionfinish.  Setting no_cov here is equivalent to
    # passing --no-cov and takes effect before pytest-cov starts collecting data.
    try:
        n_workers = config.getoption("-n", default=None)
    except (ValueError, AttributeError):
        n_workers = None
    if n_workers is not None and str(n_workers) not in ("0", "no"):
        if hasattr(config.option, "no_cov") and not config.option.no_cov:
            config.option.no_cov = True
            print(  # noqa: T201
                "\nNOTE: coverage disabled automatically because -n was given "
                "(pytest-cov + pytest-xdist causes teardown errors; use --no-cov explicitly to suppress this message)."
            )


def pytest_collection_modifyitems(config, items):
    run_all = config.getoption("--all")
    skip_network = pytest.mark.skip(reason="pass --network (or --all) to run")
    skip_pipeline = pytest.mark.skip(reason="pass --pipeline (or --all) to run (and ensure babel_downloads/ exists)")
    for item in items:
        if "network" in item.keywords and not run_all and not config.getoption("--network"):
            item.add_marker(skip_network)
        if "pipeline" in item.keywords and not run_all and not config.getoption("--pipeline"):
            item.add_marker(skip_pipeline)

    for item in items:
        if item.get_closest_marker("timeout"):
            continue  # explicit override wins
        applicable = [seconds for mark_name, seconds in MARK_TIMEOUTS.items() if item.get_closest_marker(mark_name)]
        if applicable:
            item.add_marker(pytest.mark.timeout(max(applicable)))
