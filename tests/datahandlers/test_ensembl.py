# Tests for datahandlers/ensembl.py
import csv
import json
import logging
import os

import pytest
import requests
from apybiomart import find_datasets

from src.datahandlers.ensembl import pull_ensembl

logging.basicConfig(level=logging.INFO)


def read_biomart_file(biomart_file):
    """
    Reads a BioMart output file (TSV) and yields each row as a dictionary.

    :param biomart_file: An opened file object containing tab-delimited data, formatted
                         as output from BioMart.
    :type biomart_file: file-like object
    :return: A generator yielding dictionaries representing each row from the input file.
    :rtype: Iterator[Dict[str, str]]
    """
    reader = csv.DictReader(biomart_file, dialect="excel-tab")
    yield from reader


def normalize_list_of_dictionaries(dict_list):
    """
    Sort and normalize a list of dictionaries by converting them into sorted JSON strings.

    This function accepts a list of dictionaries, serializes each dictionary into its JSON
    representation, and ensures keys are sorted so that the overall lists can be compared.

    :param dict_list: A list containing dictionary objects to be normalized, with keys
        sorted and represented as JSON strings.
    :type dict_list: list[dict]
    :return: A list of JSON strings where each string represents a dictionary input
        with sorted keys.
    :rtype: list[str]
    """
    return sorted(json.dumps(dictionary, sort_keys=True) for dictionary in dict_list)


@pytest.mark.network
@pytest.mark.xfail(
    reason="requires network access to the Ensembl BioMart service. "
    "To fix: record a VCR cassette or use responses/pytest-httpserver to "
    "replay the BioMart HTTP responses without a live connection.",
    strict=False,
)
def test_pull_ensembl(tmp_path):
    # Make a temporary directory for testing.
    pull_ensembl_test_dir = tmp_path / "pull_ensembl_test"
    output_dir = pull_ensembl_test_dir / "download"
    os.makedirs(output_dir)

    # Pull a single ENSEMBL file to that. This should trigger https://github.com/NCATSTranslator/Babel/issues/193
    single_query_report = pull_ensembl(
        output_dir, output_dir / "download_complete", ["choffmanni_gene_ensembl", "hgfemale_gene_ensembl"]
    )

    # uamericanus_gene_ensembl should be downloadable as a single file in the above example, but we're going to
    # deliberately download it in multiple chunks so it's clearer.
    download_as_splits = pull_ensembl_test_dir / "download_as_splits"
    os.makedirs(download_as_splits)
    split_query_report = pull_ensembl(
        download_as_splits, download_as_splits / "download_complete", ["choffmanni_gene_ensembl"], max_attribute_count=4
    )

    # We need to check two things:
    # 1. Whether the single/split reports make sense.
    single_uamericanus = single_query_report["choffmanni_gene_ensembl"]
    split_uamericanus = split_query_report["choffmanni_gene_ensembl"]

    # No batches with the single query, two batches with the artificially lowered max_attribute_count limit.
    assert len(single_uamericanus["batches"]) == 0
    assert len(split_uamericanus["batches"]) == 2

    # Make sure we have the right counts in the reports returned by pull_ensembl().
    assert split_uamericanus["num_rows"] == single_uamericanus["num_rows"]
    expected_attributes = set(single_uamericanus["attributes"])
    assert set(split_uamericanus["attributes"]) == expected_attributes
    batched_attributes = {"ensembl_gene_id"}
    for batch in split_uamericanus["batches"]:
        batched_attributes.update(batch["attributes"])
    assert batched_attributes == expected_attributes

    # 2. Whether the unsplit file is identical to the split file.
    unsplit_tsv = output_dir / "choffmanni_gene_ensembl" / "BioMart.tsv"
    split_tsv = download_as_splits / "choffmanni_gene_ensembl" / "BioMart.tsv"
    assert unsplit_tsv.exists()
    assert split_tsv.exists()
    with open(unsplit_tsv) as unsplit_file, open(split_tsv) as split_file:
        # So we can't compare these files directly, because rows with the same ensembl_gene_id shows up in an
        # undetermined order. So we need to load them, group them by ENSEMBL gene ID, and then compare those sets.
        unsplit_rows = list(read_biomart_file(unsplit_file))
        split_rows = list(read_biomart_file(split_file))
        assert len(unsplit_rows) == len(split_rows)
        assert unsplit_rows[0].keys() == split_rows[0].keys()

        # Confirm that the normalized lists of data dictionaries are the same.
        unsplit_rows_normalized = normalize_list_of_dictionaries(unsplit_rows)
        split_rows_normalized = normalize_list_of_dictionaries(split_rows)
        assert unsplit_rows_normalized == split_rows_normalized


@pytest.mark.network
@pytest.mark.timeout(120)
def test_biomart_find_datasets_response_format():
    """
    Diagnose the 'Too many columns specified: expected 9 and found 1' error from
    apybiomart.find_datasets().  That call parses the BioMart ?type=datasets response
    as a 9-column TSV; if the API is returning an error page (HTML/JSON) instead of
    tab-separated text the parse will fail.

    This test hits the live BioMart HTTPS endpoint, prints the raw response so we can
    see what the server actually returns, and then checks that the response looks like
    the tab-separated text that apybiomart expects.

    apybiomart uses http:// internally; Ensembl now redirects / blocks HTTP, so we
    probe https:// here to see the actual current server response.
    """
    url = "https://www.ensembl.org/biomart/martservice"
    try:
        resp = requests.get(url, params={"type": "datasets", "mart": "ENSEMBL_MART_ENSEMBL"}, timeout=90)
    except requests.exceptions.Timeout:
        pytest.skip("BioMart endpoint timed out — service may be down or unreachable from this host")

    raw = resp.text
    first_500 = raw[:500]
    print(f"\n--- BioMart find_datasets raw response (first 500 chars) ---\n{first_500}\n---")
    print(f"HTTP status: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('Content-Type', '(none)')}")

    # Count tab-separated columns in the first non-empty line.
    first_line = next((ln for ln in raw.splitlines() if ln.strip()), "")
    tab_count = first_line.count("\t")
    print(f"First non-empty line tab count: {tab_count}")
    print(f"First line: {first_line[:200]!r}")

    # apybiomart expects 9 tab-separated columns per row.
    assert tab_count == 8, (
        f"BioMart ?type=datasets response has changed: expected 8 tabs (9 columns) per row "
        f"but found {tab_count} tabs in the first line.\n"
        f"Content-Type: {resp.headers.get('Content-Type', '(none)')!r}\n"
        f"First line: {first_line[:200]!r}\n"
        f"Full response prefix: {first_500!r}"
    )

    # Also confirm apybiomart.find_datasets() itself can parse without raising.
    df = find_datasets()
    print(f"\nfind_datasets() returned {len(df)} rows with columns: {list(df.columns)}")
    assert "Dataset_ID" in df.columns, f"Expected 'Dataset_ID' column, got: {list(df.columns)}"
    assert len(df) > 0, "find_datasets() returned an empty dataframe"
