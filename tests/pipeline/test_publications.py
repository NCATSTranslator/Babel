"""PubMed pipeline test: a miniature end-to-end publications build.

Downloads a handful of real PubMed baseline and update files, verifies them against their published
MD5 checksums, parses them into titles/ids/concords, and builds a small Publication.txt compendium —
i.e. every step the `publications` Snakemake target runs, at a size that fits in a test.

It also exercises preloading (docs/RunningBabel.md, "Preloading PubMed downloads") against the real
server: the second download pass over the same directory must leave the already-downloaded files
alone.

Everything is written into a temporary download/output directory, so the test never touches (or
clobbers) a real babel_downloads/babel_outputs tree.

Run with:
    uv run pytest tests/pipeline/test_publications.py --pipeline --no-cov -v
"""

import json
import os
import re

import pytest
import requests

import src.createcompendia.publications as publications
import src.util
from src.babel_utils import pull_via_wget
from src.categories import PUBLICATION
from src.prefixes import PMID
from src.util import ensure_parent_dir

pytestmark = [pytest.mark.pipeline, pytest.mark.network]

PUBMED_BASE = "https://ftp.ncbi.nlm.nih.gov/pubmed/"

# How many files to take from each of baseline/ and updatefiles/. Each is a few tens of MB; five of
# each is enough to exercise the parse and the compendium build without downloading the ~50 GB corpus.
FILES_PER_DIRECTORY = 5


def list_pubmed_files(subdir):
    """Return the sorted names of the .xml.gz files PubMed publishes in `subdir`."""
    response = requests.get(f"{PUBMED_BASE}{subdir}/", timeout=60)
    response.raise_for_status()
    return sorted(set(re.findall(r'href="(pubmed\d+n\d+\.xml\.gz)"', response.text)))


@pytest.fixture(scope="module")
def pubmed_config(tmp_path_factory):
    """Point Babel's download and output directories at a temporary tree for this module."""
    tmp = tmp_path_factory.mktemp("pubmed")
    config = dict(src.util.get_config())
    config["download_directory"] = str(tmp / "babel_downloads")
    config["output_directory"] = str(tmp / "babel_outputs")

    # write_compendium()'s factories load the common (UberGraph) labels/synonyms/descriptions as a
    # fallback for CURIEs that have none of their own. Publications have none, and building the real
    # files means a large UberGraph download, so stand in empty ones to keep this test self-contained.
    for common_files in config["common"].values():
        for common_file in common_files:
            path = os.path.join(config["download_directory"], "common", common_file)
            ensure_parent_dir(path)
            open(path, "w").close()

    original = src.util.config_yaml
    src.util.config_yaml = config
    yield config
    src.util.config_yaml = original


@pytest.fixture(scope="module")
def pubmed_downloads(pubmed_config):
    """Download FILES_PER_DIRECTORY files (and their .md5s) from each of baseline/ and updatefiles/,
    into the same <download_directory>/PubMed/<subdir> layout the pipeline uses."""
    directories = {}
    for subdir in ("baseline", "updatefiles"):
        filenames = list_pubmed_files(subdir)[:FILES_PER_DIRECTORY]
        assert len(filenames) == FILES_PER_DIRECTORY, f"PubMed {subdir}/ listed only {len(filenames)} files"

        for filename in filenames:
            for name in (filename, f"{filename}.md5"):
                pull_via_wget(
                    f"{PUBMED_BASE}{subdir}/",
                    name,
                    decompress=False,
                    subpath=f"PubMed/{subdir}",
                )

        directories[subdir] = os.path.join(pubmed_config["download_directory"], "PubMed", subdir)

    return directories


# DOWNLOADING AND VERIFYING


def test_downloaded_files_verify_against_their_published_md5s(pubmed_downloads, tmp_path):
    """Freshly downloaded PubMed files should pass MD5 verification without anything being
    re-downloaded, and the `verified` done-marker should be written."""
    done_file = tmp_path / "verified"

    publications.verify_pubmed_downloads(list(pubmed_downloads.values()), str(done_file))

    assert done_file.exists()
    for directory in pubmed_downloads.values():
        for filename in os.listdir(directory):
            if filename.endswith(".gz"):
                path = os.path.join(directory, filename)
                assert publications.verify_pubmed_download_against_md5(path, f"{path}.md5")


def test_redownloading_leaves_the_already_downloaded_files_alone(pubmed_downloads):
    """Downloading again over a directory we've already filled should leave every file untouched —
    this is what makes carrying PubMed files forward into a new run cheap."""
    baseline = pubmed_downloads["baseline"]
    before = {name: os.stat(os.path.join(baseline, name)).st_mtime_ns for name in sorted(os.listdir(baseline))}

    filename = min(name for name in before if name.endswith(".xml.gz"))
    pull_via_wget(f"{PUBMED_BASE}baseline/", filename, decompress=False, subpath="PubMed/baseline")

    after = {name: os.stat(os.path.join(baseline, name)).st_mtime_ns for name in sorted(os.listdir(baseline))}
    assert after == before


# PARSING AND BUILDING THE COMPENDIUM


@pytest.fixture(scope="module")
def parsed_pubmed(pubmed_downloads, pubmed_config, tmp_path_factory):
    """Parse the downloaded files into the titles / ids / concords / statuses the compendium needs."""
    out = tmp_path_factory.mktemp("parsed")
    outputs = {
        "titles_file": str(out / "titles.tsv"),
        "status_file": str(out / "statuses.jsonl.gz"),
        "pmid_id_file": str(out / "PMID"),
        "pmid_doi_concord_file": str(out / "PMID_DOI"),
        "metadata_yaml": str(out / "metadata.yaml"),
    }

    publications.parse_pubmed_into_tsvs(
        pubmed_downloads["baseline"],
        pubmed_downloads["updatefiles"],
        outputs["titles_file"],
        outputs["status_file"],
        outputs["pmid_id_file"],
        outputs["pmid_doi_concord_file"],
        outputs["metadata_yaml"],
    )

    return outputs


def test_parsing_produces_pmid_ids_titles_and_doi_concords(parsed_pubmed):
    """Parsing the downloaded files should yield PMID ids, titles, DOI/PMC concords and statuses."""
    with open(parsed_pubmed["pmid_id_file"]) as f:
        ids = [line.rstrip("\n").split("\t") for line in f]
    assert ids, "no PMIDs parsed"
    assert all(curie.startswith(f"{PMID}:") for curie, _ in ids)

    with open(parsed_pubmed["titles_file"]) as f:
        titles = [line.rstrip("\n").split("\t") for line in f]
    assert titles, "no titles parsed"

    with open(parsed_pubmed["pmid_doi_concord_file"]) as f:
        concords = [line.rstrip("\n").split("\t") for line in f]
    assert concords, "no concords parsed"
    assert {relation for _, relation, _ in concords} == {"eq"}


def test_building_a_publication_compendium(parsed_pubmed, pubmed_config, tmp_path):
    """The parsed files should build into a Publication.txt whose cliques carry PMID identifiers and
    the titles we parsed. Uses an empty icRDF.tsv: information content is not what's under test."""
    icrdf = tmp_path / "icRDF.tsv"
    icrdf.write_text("")

    compendium = os.path.join(pubmed_config["output_directory"], "compendia", "Publication.txt")
    publications.generate_compendium(
        [parsed_pubmed["pmid_doi_concord_file"]],
        [parsed_pubmed["metadata_yaml"]],
        [parsed_pubmed["pmid_id_file"]],
        [parsed_pubmed["titles_file"]],
        compendium,
        str(icrdf),
    )

    with open(compendium) as f:
        cliques = [json.loads(line) for line in f]

    assert cliques, "Publication.txt is empty"
    for clique in cliques:
        assert clique["type"] == PUBLICATION
        assert clique["identifiers"], f"clique with no identifiers: {clique}"

    # Every PMID we parsed should have made it into the compendium. (Identifiers are written with the
    # compact on-disk keys: "i" is the CURIE, "l" the label — see docs/DataFormats.md.)
    with open(parsed_pubmed["pmid_id_file"]) as f:
        parsed_pmids = {line.split("\t")[0] for line in f}
    labels = {identifier["i"]: identifier["l"] for clique in cliques for identifier in clique["identifiers"]}
    assert parsed_pmids <= set(labels)

    # A PMID and the DOI (or PMCID) we concorded it with should land in the same clique.
    with open(parsed_pubmed["pmid_doi_concord_file"]) as f:
        pmid, _, equivalent_curie = f.readline().rstrip("\n").split("\t")
    clique_with_pmid = next(c for c in cliques if any(i["i"] == pmid for i in c["identifiers"]))
    assert equivalent_curie in {identifier["i"] for identifier in clique_with_pmid["identifiers"]}

    # Titles become the labels on their PMIDs.
    with open(parsed_pubmed["titles_file"]) as f:
        first_pmid, first_title = f.readline().rstrip("\n").split("\t")
    assert labels[first_pmid] == first_title
