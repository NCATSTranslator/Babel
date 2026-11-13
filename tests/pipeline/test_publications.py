"""Download the whole pubmed2db export pinned in config.yaml and parse it.

The export (~17 GB) is cached in babel_downloads/PubMed2DB/<version>/, like the pipeline's own download,
which checks every shard's SHA-256. ``parse_pubmed2db_into_tsvs()`` checks every shard against the record
count in its validation report; the test then asserts over the real output that:

- every row of titles.tsv has exactly two fields, which is what ``escape_tsv_field()`` is for;
- no identifier in the concords is one ``write_compendium()`` would fail the build on, i.e. every malformed
  DOI in the export was either repaired from ``input_data/pubmed_doi_repairs.tsv`` or skipped;
- the numbers repaired and skipped are the ones docs/sources/PubMed/dois/counts.json records, so the repairs
  table and the committed characterization describe the export that is pinned. When this fails after moving
  ``pubmed2db_version``, re-run docs/sources/PubMed/dois/characterize_dois.py;
- no repair takes a DOI away from a PMID that carries it well-formed: every PMID carrying a repaired DOI
  well-formed also carries the malformed DOI it repairs. The build applies a row of the repairs table to
  every PMID with that malformed DOI and keeps a shared DOI on the lowest PMID, so a repair that broke this
  could move the DOI to another clique (``PUBMED_DOI_REPAIRS``).

The cheap checks of the same export are ``tests/createcompendia/test_publications_export.py``.

Run with:
    uv run pytest tests/pipeline/test_publications.py --pipeline --network --no-cov -v
"""

import json
import os
import shutil
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import pytest
import yaml

from src.createcompendia import publications
from src.prefixes import DOI
from src.util import curie_format_problem, get_config, get_repo_root

CONFIG = get_config()
VERSION = CONFIG["pubmed2db_version"]
EXPORT_URL = CONFIG["pubmed2db_base_url"] + VERSION + "/"


def _carriers(args):
    """For one shard read with no repairs: ``(PMIDs carrying each malformed DOI in ``malformed_dois``,
    PMIDs carrying each lower-cased DOI in ``wanted`` well-formed)``. Module-level so it can be pickled."""
    shard_path, malformed_dois, wanted = args
    malformed_carriers = defaultdict(set)
    well_formed_carriers = defaultdict(set)
    for pmid, _, others, malformed in publications._read_shard(shard_path):
        for curie in malformed:
            if curie in malformed_dois:
                malformed_carriers[curie].add(pmid)
        for other in others:
            if other.startswith(DOI + ":") and other.lower() in wanted:
                well_formed_carriers[other.lower()].add(pmid)
    return malformed_carriers, well_formed_carriers


@pytest.mark.pipeline
@pytest.mark.network
# `slow` for its hour-long timeout: a cold download of ~17 GB plus the parse can outrun `pipeline`'s 15 min.
@pytest.mark.slow
@pytest.mark.skipif(shutil.which("wget") is None, reason="wget is not installed")
def test_full_export_downloads_and_parses(tmp_path):
    """The whole pinned export should download and parse with every shard matching its record count; every
    row of the resulting titles.tsv should have exactly two fields; no concord identifier should be
    malformed; and the malformed DOIs repaired and skipped should number what the committed characterization
    of this export says."""
    download_dir = os.path.join(CONFIG["download_directory"], "PubMed2DB", VERSION)
    done_file = os.path.join(download_dir, "downloaded")
    if not os.path.exists(done_file):
        publications.download_pubmed2db(EXPORT_URL, CONFIG["pubmed2db_validation_report"], download_dir, done_file)

    titles_file = tmp_path / "titles.tsv"
    publications.parse_pubmed2db_into_tsvs(
        download_dir,
        str(titles_file),
        str(tmp_path / "PMID"),
        str(tmp_path / "PMID_DOI"),
        str(tmp_path / "shared_identifiers.tsv"),
        str(tmp_path / "metadata.yaml"),
        EXPORT_URL,
        workers=os.cpu_count(),
    )

    with open(titles_file) as f:
        bad_rows = [line for line in f if line.count("\t") != 1]
    assert bad_rows == []

    with open(tmp_path / "PMID_DOI") as f:
        malformed = [line for line in f if curie_format_problem(line.rstrip("\n").split("\t")[2])]
    assert malformed == []

    with open(get_repo_root() / "docs/sources/PubMed/dois/counts.json") as f:
        characterized = json.load(f)
    assert characterized["export"] == VERSION, "counts.json characterizes another export: re-run characterize_dois.py"
    with open(tmp_path / "metadata.yaml") as f:
        counts = yaml.safe_load(f)["counts"]
    assert counts["repaired_malformed_article_ids"] == characterized["repaired"]
    assert counts["skipped_malformed_article_ids"] == characterized["skipped"] + len(
        characterized["malformed_identifiers_that_are_not_dois"]
    )

    # No repair takes a DOI away from a PMID that has it well-formed (see the module docstring).
    repairs = publications.load_doi_repairs(publications.PUBMED_DOI_REPAIRS)
    wanted = frozenset(repaired.lower() for values in repairs.values() for repaired in values)
    shards = [os.path.join(download_dir, shard) for shard in publications.expected_shard_counts(download_dir)]
    malformed_carriers = defaultdict(set)
    well_formed_carriers = defaultdict(set)
    with ProcessPoolExecutor() as pool:
        for shard_malformed, shard_well_formed in pool.map(
            _carriers, [(shard, frozenset(repairs), wanted) for shard in shards]
        ):
            for curie, pmids in shard_malformed.items():
                malformed_carriers[curie] |= pmids
            for doi, pmids in shard_well_formed.items():
                well_formed_carriers[doi] |= pmids
    takes_away = {
        (malformed, repaired): sorted(well_formed_carriers[repaired.lower()] - malformed_carriers[malformed])
        for malformed, values in repairs.items()
        for repaired in values
        # A row for a DOI this export doesn't carry is never applied, so it takes nothing away.
        if malformed_carriers[malformed]
    }
    assert {pair: pmids for pair, pmids in takes_away.items() if pmids} == {}
