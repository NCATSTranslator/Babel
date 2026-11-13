"""Unit tests for building the Publication compendium from a pubmed2db NDJSON export.

The fixture in ``pubmed2db/`` is a three-shard miniature of a real export, laid out the way Babel's
download leaves one (shards, ``metadata.json`` and ``validation_report.json``). Every record is copied
verbatim from the 2026nov08 export (https://stars.renci.org/var/babel_outputs/pubmed2db/2026nov08/), the
first in pubmed2db's data model 1.0; the shard each came from is in brackets, as the ``N`` of
``pubmed_metadata_N.ndjson.gz``. To re-derive one, ``gzcat`` that shard and grep for ``^{"id":"PMID:<n>",``.

Fixture shard 0:

- ``PMID:5202740`` [5] — a PubMed Central id, ``PMC:PMC1712714``, and no DOI.
- ``PMID:7754983`` [1] — shares ``doi:10.1093/ajcn/61.6.1324S`` with ``PMID:7754980`` in fixture shard 1; the
  higher PMID is deliberately in the shard parsed first.
- ``PMID:17072568`` [4] — a DOI and an empty ``article_title``.
- ``PMID:26225670`` [3] — a title containing a backslash.
- ``PMID:30803192`` [0] — a DOI and a PubMed Central id; a title containing a newline.
- ``PMID:9245294`` [7] — a title with trailing whitespace.
- ``PMID:26214188`` [3] — ``doi:10.1039/c4bm00222a``, which ``PMID:26146547`` in fixture shard 1 spells
  ``doi:10.1039/C4BM00222A``; again the higher PMID is in the shard parsed first.

Fixture shard 1:

- ``PMID:7754980`` [1] — the lower PMID of the shared DOI.
- ``PMID:25303692`` [4] — no DOI or PubMed Central id; a title containing ``\x85``, a C1 control character
  (cp1252's ellipsis, mis-decoded).
- ``PMID:5202677`` [5] — no DOI or PubMed Central id.
- ``PMID:17124311`` [5] — a malformed DOI, ``doi:10.1126/science. 1134405``, which write_compendium() would
  reject and the repairs table (``input_data/pubmed_doi_repairs.tsv``) turns into
  ``doi:10.1126/science.1134405``.
- ``PMID:26146547`` [5] — the lower PMID of the DOI spelled in two cases.

Fixture shard 2:

- ``PMID:113`` [5] — a second record with only a PubMed Central id.
- ``PMID:16041191`` [0] — a malformed DOI that is in no repairs table, because nothing made of it is a
  registered DOI: ``doi:10.1097/01.mjt.00001= 32251.03275.3c``.
- ``PMID:23752222`` [0] — two DOIs in one value, ``doi:10.1001/archdermatol.2012.151a
  10.1001/archdermatol.2012.151b``, of which only the first is registered and so in the repairs table.

The tests read the committed repairs table, so that they exercise the repairs a build makes; the three
malformed DOIs above are real rows (or real absences) in it.

``metadata.json`` and ``validation_report.json`` are cut down to the fields the code reads, in the structure
of 2026nov08's; ``metadata.json``'s hashes are the real SHA-256s of the three fixture shards, so rebuilding
a shard means updating them.
"""

import gzip
import json
import os
import shutil

import pytest

import src.util
from src.categories import JOURNAL_ARTICLE, PUBLICATION
from src.createcompendia import publications
from src.util import ensure_parent_dir
from tests.conftest import assert_concordance_file_valid, assert_ids_file_valid

pytestmark = pytest.mark.unit

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "pubmed2db")
EXPORT_URL = "https://stars.renci.org/var/babel_outputs/pubmed2db/2026nov08/"
SHARED_DOI = "doi:10.1093/ajcn/61.6.1324S"
SHARED_CASE_DOI = "doi:10.1039/C4BM00222A"  # PMID:26146547's spelling; PMID:26214188 has it lower-cased.
RECORD_COUNT = 15


def copy_fixture(tmp_path):
    """A writable copy of the fixture export, for tests that damage it."""
    export = tmp_path / "export"
    shutil.copytree(FIXTURE_DIR, export)
    return export


def edit_report(report_file, edit):
    """Apply ``edit`` to a parsed validation report and write it back."""
    report = json.loads(report_file.read_text())
    edit(report)
    report_file.write_text(json.dumps(report))


def read_titles(titles_file):
    """titles.tsv as ``{pmid: escaped title}``, keeping each title's whitespace (read_tsv() strips it)."""
    with open(titles_file) as f:
        rows = [line.removesuffix("\n").split("\t") for line in f]
    assert all(len(row) == 2 for row in rows), "every titles.tsv row should have exactly two fields"
    return dict(rows)


@pytest.fixture
def parsed(tmp_path):
    """Run parse_pubmed2db_into_tsvs() over the fixture export and return the output paths."""
    out = {
        "titles_file": str(tmp_path / "titles.tsv"),
        "pmid_id_file": str(tmp_path / "ids" / "PMID"),
        "concord_file": str(tmp_path / "concords" / "PMID_DOI"),
        "shared_ids_file": str(tmp_path / "concords" / "shared_identifiers.tsv"),
        "metadata_yaml": str(tmp_path / "concords" / "metadata.yaml"),
    }
    publications.parse_pubmed2db_into_tsvs(FIXTURE_DIR, **out, url=EXPORT_URL, workers=2)
    return out


def parse_into(tmp_path, export):
    """Run parse_pubmed2db_into_tsvs() over ``export`` with throwaway outputs."""
    publications.parse_pubmed2db_into_tsvs(
        str(export),
        str(tmp_path / "titles.tsv"),
        str(tmp_path / "PMID"),
        str(tmp_path / "PMID_DOI"),
        str(tmp_path / "shared.tsv"),
        str(tmp_path / "metadata.yaml"),
        EXPORT_URL,
        workers=1,
    )


# PARSING


def test_ids_titles_and_concords(parsed):
    """Every record should yield a JournalArticle id row, a concord row per DOI/PMC id with the bare `eq`
    relation, and a title row unless the title is empty, in shard order."""
    ids = assert_ids_file_valid(parsed["pmid_id_file"])
    assert [row[1] for row in ids] == [JOURNAL_ARTICLE] * RECORD_COUNT
    assert [row[0] for row in ids][:2] == ["PMID:5202740", "PMID:7754983"]
    assert ids[-1][0] == "PMID:23752222"

    concords = assert_concordance_file_valid(parsed["concord_file"])
    assert {relation for _, relation, _ in concords} == {"eq"}
    # PubMed Central ids are PMC:PMC123, as data model 1 exports them (see PUBMED2DB_DATA_MODEL_MAJOR).
    assert ["PMID:5202740", "eq", "PMC:PMC1712714"] in concords
    assert ["PMID:30803192", "eq", "doi:10.31557/APJCP.2019.20.2.345"] in concords
    assert ["PMID:113", "eq", "PMC:PMC1666769"] in concords
    assert not any(pmid == "PMID:5202677" for pmid, _, _ in concords)

    titles = read_titles(parsed["titles_file"])
    assert "PMID:17072568" not in titles, "an empty title should not be written"
    assert titles["PMID:5202740"] == "Renal tubular acidosis: an immunopathological study on four patients."


def test_titles_are_escaped_losslessly(parsed):
    """Newlines and backslashes in titles should be escaped in titles.tsv, so that every row is exactly
    `PMID<TAB>title`; other characters, including surrounding whitespace, should be kept as they are."""
    titles = read_titles(parsed["titles_file"])
    assert "Genotypes and\\nHaplotype" in titles["PMID:30803192"]
    assert "for \\\\Preoperative" in titles["PMID:26225670"]
    assert titles["PMID:9245294"] == "Identity as adaptation to social, cultural, and historical context "
    assert titles["PMID:25303692"] == "New challenges\x85."


@pytest.mark.parametrize(
    "title,escaped",
    [
        ("plain", "plain"),
        ("a\nb", "a\\nb"),
        ("a\tb\rc", "a\\tb\\rc"),
        # The backslash is escaped first, so a literal backslash-n stays distinguishable from a newline.
        ("a\\nb", "a\\\\nb"),
    ],
)
def test_escape_tsv_field(title, escaped):
    """escape_tsv_field() should escape backslash, tab, newline and carriage return, and nothing else."""
    assert publications.escape_tsv_field(title) == escaped


def test_shared_identifier_is_assigned_to_the_lowest_pmid(parsed):
    """A DOI carried by two PMIDs should be listed once in shared_identifiers.tsv with the lowest PMID as
    its winner, even though the higher PMID's shard was parsed first -- including a DOI the two records spell
    in different cases. Every DOI is listed lower-cased, as its shared_identifier_key()."""
    with open(parsed["shared_ids_file"]) as f:
        assert f.read() == (f"{SHARED_CASE_DOI.lower()}\tPMID:26146547\t2\n{SHARED_DOI.lower()}\tPMID:7754980\t2\n")


@pytest.mark.parametrize(
    ("curie", "key"),
    [
        ("doi:10.1039/C4BM00222A", "doi:10.1039/c4bm00222a"),
        ("doi:10.1039/c4bm00222a", "doi:10.1039/c4bm00222a"),
        ("PMC:PMC1712714", "PMC:PMC1712714"),
    ],
)
def test_shared_identifier_key_ignores_case_only_for_dois(curie, key):
    """shared_identifier_key() should lower-case a DOI, which is case-insensitive, and leave a PMC id alone."""
    assert publications.shared_identifier_key(curie) == key


def test_metadata_records_the_export_url_and_counts(parsed):
    """The metadata YAML should name the pubmed2db URL as its source and carry the record counts."""
    import yaml

    with open(parsed["metadata_yaml"]) as f:
        metadata = yaml.safe_load(f)
    assert metadata["sources"][0]["url"] == EXPORT_URL
    assert metadata["counts"]["pmid_count"] == RECORD_COUNT
    # Which export and data model the concords came from, read from the export's metadata.json.
    assert "Export 2026nov08, pubmed2db data model 1.0.0" in metadata["description"]
    assert metadata["counts"]["shard_count"] == 3
    assert metadata["counts"]["shared_identifier_count"] == 2
    assert metadata["counts"]["repaired_malformed_article_ids"] == 2
    assert metadata["counts"]["skipped_malformed_article_ids"] == 1


def test_malformed_doi_in_the_repairs_table_is_repaired(parsed):
    """A DOI that write_compendium() would reject (here, with an embedded space) should be written to the
    concords as the registered DOI the repairs table gives for it (#1112), and never as exported."""
    concords = assert_concordance_file_valid(parsed["concord_file"])
    assert not any(src.util.curie_format_problem(other) for _, _, other in concords)
    # PMID:17124311 exports doi:10.1126/science. 1134405.
    assert ["PMID:17124311", "eq", "doi:10.1126/science.1134405"] in concords
    assert read_titles(parsed["titles_file"])["PMID:17124311"] == "Neuroscience. The brain's dark energy."


def test_value_holding_two_dois_keeps_only_the_registered_one(parsed):
    """A value holding two DOIs should be repaired to the ones in the repairs table only: for PMID:23752222
    doi.org knows 10.1001/archdermatol.2012.151a but not ...151b, so the second is not invented."""
    concords = assert_concordance_file_valid(parsed["concord_file"])
    assert [other for pmid, _, other in concords if pmid == "PMID:23752222"] == ["doi:10.1001/archdermatol.2012.151a"]


def test_malformed_doi_with_no_repair_is_skipped_but_its_pmid_kept(parsed):
    """A malformed DOI the repairs table doesn't list (PMID:16041191's, which has a quoted-printable line
    break in it and no registered reading) should be left out of the concords, while its record still gets an
    id row and a title."""
    concords = assert_concordance_file_valid(parsed["concord_file"])
    assert not any(pmid == "PMID:16041191" for pmid, _, _ in concords)
    assert "PMID:16041191" in [row[0] for row in assert_ids_file_valid(parsed["pmid_id_file"])]
    assert "PMID:16041191" in read_titles(parsed["titles_file"])


def test_without_a_repairs_table_every_malformed_doi_is_skipped(tmp_path):
    """With an empty repairs table, all three malformed DOIs in the fixture should be skipped and counted, and
    none repaired -- the repairs come from the table and nowhere else."""
    import yaml

    empty = tmp_path / "no_repairs.tsv"
    empty.write_text("# no repairs\n")
    publications.parse_pubmed2db_into_tsvs(
        FIXTURE_DIR,
        str(tmp_path / "titles.tsv"),
        str(tmp_path / "PMID"),
        str(tmp_path / "PMID_DOI"),
        str(tmp_path / "shared.tsv"),
        str(tmp_path / "metadata.yaml"),
        EXPORT_URL,
        workers=1,
        doi_repairs_file=str(empty),
    )
    concords = assert_concordance_file_valid(str(tmp_path / "PMID_DOI"))
    assert not {"PMID:17124311", "PMID:16041191", "PMID:23752222"} & {pmid for pmid, _, _ in concords}
    with open(tmp_path / "metadata.yaml") as f:
        counts = yaml.safe_load(f)["counts"]
    assert counts["repaired_malformed_article_ids"] == 0
    assert counts["skipped_malformed_article_ids"] == 3


# THE DOI REPAIRS TABLE


def test_committed_repairs_table_loads_and_only_repairs_malformed_dois_to_well_formed_ones():
    """input_data/pubmed_doi_repairs.tsv should load -- load_doi_repairs() raises on a row that isn't a
    malformed CURIE and a well-formed doi: one -- and no repair should be a no-op or leave whitespace behind."""
    repairs = publications.load_doi_repairs(publications.PUBMED_DOI_REPAIRS)
    assert len(repairs) > 200
    for malformed, repaired in repairs.items():
        assert src.util.curie_format_problem(malformed)
        assert repaired and malformed not in repaired
        assert all(r.startswith("doi:10.") and not src.util.curie_format_problem(r) for r in repaired)


def test_repairs_table_collects_every_repair_of_a_value(tmp_path):
    """A malformed value with two rows should load as both repairs, in file order, skipping comments and
    blank lines."""
    table = tmp_path / "repairs.tsv"
    table.write_text("# comment\n\ndoi:10.1/a 10.1/b\tdoi:10.1/a\ndoi:10.1/a 10.1/b\tdoi:10.1/b\n")
    assert publications.load_doi_repairs(str(table)) == {"doi:10.1/a 10.1/b": ("doi:10.1/a", "doi:10.1/b")}


@pytest.mark.parametrize(
    ("row", "message"),
    [
        pytest.param("doi:10.1/a b doi:10.1/ab", "tab-separated fields", id="space-instead-of-tab"),
        pytest.param("doi:10.1/a b\tdoi:10.1/ab\textra", "tab-separated fields", id="three-fields"),
        pytest.param("doi:10.1/ab\tdoi:10.1/ab", "is not malformed", id="key-is-well-formed"),
        pytest.param("doi:10.1/a b\tdoi:10.1/a b", "not a well-formed doi", id="repair-still-malformed"),
        pytest.param("doi:10.1/a b\tPMC:PMC1", "not a well-formed doi", id="repair-is-not-a-doi"),
    ],
)
def test_hand_edited_repairs_table_is_refused(tmp_path, row, message):
    """A row that could not do what it appears to -- wrong separator, a key that is never looked up, a repair
    that would itself fail the build -- should raise naming the file and line, not be skipped."""
    table = tmp_path / "repairs.tsv"
    table.write_text(row + "\n")
    with pytest.raises(ValueError, match=rf"repairs\.tsv:1.*{message}"):
        publications.load_doi_repairs(str(table))


def test_malformed_doi_carried_twice_is_repaired_or_skipped_once(tmp_path):
    """A record carrying the same malformed DOI twice -- exactly, or in two cases -- should have it repaired
    (or skipped) once, in the spelling that comes first, so neither count is inflated. No record of 2026nov08
    does this, so the record is made up: it pins what the reader does, not a shape seen in the export."""
    table = tmp_path / "repairs.tsv"
    table.write_text("doi:10.1/A B\tdoi:10.1/AB\n")
    shard = tmp_path / "pubmed_metadata_0.ndjson.gz"
    record = {
        "id": "PMID:1",
        "identifiers": ["PMID:1", "doi:10.1/A B", "doi:10.1/X Y", "doi:10.1/a b", "doi:10.1/x y", "doi:10.1/x y"],
        "article_title": "",
    }
    with gzip.open(shard, "wt") as f:
        f.write(json.dumps(record) + "\n")

    repairs_made = []
    [(_, _, others, malformed)] = publications._read_shard(
        str(shard), publications.load_doi_repairs(str(table)), repairs_made
    )
    assert others == ["doi:10.1/AB"]
    assert malformed == ["doi:10.1/X Y"]
    assert repairs_made == [("PMID:1", "doi:10.1/A B", ("doi:10.1/AB",))]


def test_record_without_identifiers_raises_naming_the_shard(tmp_path):
    """A record whose `identifiers` list is empty should raise a ValueError naming its shard and PMID, not a
    bare IndexError."""
    export = copy_fixture(tmp_path)
    shard = export / "pubmed_metadata_2.ndjson.gz"
    with gzip.open(shard, "rt") as f:
        record = json.loads(f.readline())
    record["identifiers"] = []
    with gzip.open(shard, "wt") as f:
        f.write(json.dumps(record) + "\n")
    with pytest.raises(ValueError, match=r"pubmed_metadata_2\.ndjson\.gz: record PMID:113"):
        parse_into(tmp_path, export)


def _flip_crc(path):
    """Corrupt the CRC32 in a gzip file's trailer, as a damaged download would fail it."""
    data = bytearray(path.read_bytes())
    data[-8] ^= 0xFF
    path.write_bytes(bytes(data))


def _truncate(path):
    """Cut the end off a gzip file, as an interrupted download would."""
    path.write_bytes(path.read_bytes()[:-20])


def _write_lines(lines):
    def write(path):
        with gzip.open(path, "wt") as f:
            f.writelines(line + "\n" for line in lines)

    return write


@pytest.mark.parametrize(
    "damage",
    [
        pytest.param(_flip_crc, id="crc-mismatch"),
        pytest.param(_truncate, id="truncated-gzip"),
        pytest.param(_write_lines(["not json"]), id="unparseable-line"),
        pytest.param(_write_lines(['{"id": "PMID:1", "identifiers": ["PMID:1"]}']), id="missing-field"),
    ],
)
def test_damaged_shard_raises_naming_the_shard(tmp_path, damage):
    """A shard that fails its gzip CRC, is cut short, or holds a record that won't parse should raise a
    RuntimeError naming the shard and saying to re-download it, rather than a bare low-level error."""
    export = copy_fixture(tmp_path)
    damage(export / "pubmed_metadata_0.ndjson.gz")
    with pytest.raises(RuntimeError, match=r"pubmed_metadata_0\.ndjson\.gz is corrupt or truncated.*re-run download"):
        parse_into(tmp_path, export)


# VALIDATION REPORT


def test_expected_shard_counts_reads_the_structured_counts():
    """expected_shard_counts() should return each shard's record count from checks.structure, sorted."""
    counts = publications.expected_shard_counts(FIXTURE_DIR)
    assert list(counts) == [f"pubmed_metadata_{i}.ndjson.gz" for i in range(3)]
    assert sum(counts.values()) == RECORD_COUNT


def test_truncated_shard_is_refused_and_named(tmp_path):
    """A shard holding fewer records than the validation report says should be refused, naming the shard —
    that is the only signal of a truncated download."""
    export = copy_fixture(tmp_path)
    shard = export / "pubmed_metadata_1.ndjson.gz"
    with gzip.open(shard, "rt") as f:
        first_line = f.readline()
    with gzip.open(shard, "wt") as f:
        f.write(first_line)
    with pytest.raises(RuntimeError, match=r"pubmed_metadata_1\.ndjson\.gz: parsed 1, report says"):
        parse_into(tmp_path, export)


def test_failed_validation_report_raises(tmp_path):
    """An export whose own validator reported `fail` should be refused outright."""
    export = copy_fixture(tmp_path)
    edit_report(export / publications.VALIDATION_REPORT, lambda report: report.update(status="fail", errors=["boom"]))
    with pytest.raises(RuntimeError, match="status 'fail'"):
        publications.expected_shard_counts(str(export))


def test_report_without_structured_counts_raises(tmp_path):
    """A report missing checks.structure.records_by_shard (a format change) should raise a clear error rather
    than a KeyError."""
    export = copy_fixture(tmp_path)
    edit_report(
        export / publications.VALIDATION_REPORT, lambda report: report["checks"]["structure"].pop("records_by_shard")
    )
    with pytest.raises(RuntimeError, match="report format has changed"):
        publications.expected_shard_counts(str(export))


def test_report_whose_shard_counts_disagree_with_its_total_raises(tmp_path):
    """records_by_shard summing to something other than records_total means the report can't be trusted."""
    export = copy_fixture(tmp_path)
    edit_report(
        export / publications.VALIDATION_REPORT,
        lambda report: report["checks"]["structure"].update(records_total=RECORD_COUNT + 1),
    )
    with pytest.raises(RuntimeError, match="records_total"):
        publications.expected_shard_counts(str(export))


@pytest.mark.parametrize("name", ["../pubmed_metadata_0.ndjson.gz", "pubmed_metadata_0.ndjson", "pubmed.duckdb"])
def test_report_listing_an_unexpected_shard_name_raises(tmp_path, name):
    """A shard name that isn't a bare *.ndjson.gz filename should be refused, since it becomes both a URL and a
    local path."""
    export = copy_fixture(tmp_path)
    edit_report(
        export / publications.VALIDATION_REPORT,
        lambda report: report["checks"]["structure"]["records_by_shard"].update({name: 0}),
    )
    with pytest.raises(RuntimeError, match="unexpected shard name"):
        publications.expected_shard_counts(str(export))


# EXPORT METADATA


def edit_metadata(export, edit):
    """Apply ``edit`` to an export's parsed metadata.json and write it back."""
    edit_report(export / publications.EXPORT_METADATA, edit)


def test_read_export_metadata_accepts_the_fixture():
    """read_export_metadata() should return the fixture's metadata.json, which is in data model 1.0.0 and
    lists the same shards and record total as the validation report."""
    metadata = publications.read_export_metadata(FIXTURE_DIR)
    assert metadata["data_model_version"] == "1.0.0"
    assert [entry["name"] for entry in metadata["files"]] == list(publications.expected_shard_counts(FIXTURE_DIR))
    assert metadata["records"] == RECORD_COUNT


def test_newer_minor_data_model_is_accepted(tmp_path):
    """A newer minor version of data model 1 only adds fields, so it should be read without complaint."""
    export = copy_fixture(tmp_path)
    edit_metadata(export, lambda metadata: metadata.update(data_model_version="1.7.0"))
    assert publications.read_export_metadata(str(export))["data_model_version"] == "1.7.0"
    parse_into(tmp_path, export)


@pytest.mark.parametrize("version", ["2.0.0", "0.9.0", "10.0.0", "", None])
def test_other_major_data_model_is_refused(tmp_path, version):
    """An export in another major version of the data model (or naming none) may have renamed or redefined
    the fields Babel reads, so both reading its metadata and parsing it should raise."""
    export = copy_fixture(tmp_path)

    def set_version(metadata):
        if version is None:
            del metadata["data_model_version"]
        else:
            metadata["data_model_version"] = version

    edit_metadata(export, set_version)
    with pytest.raises(RuntimeError, match="reads major version 1"):
        publications.read_export_metadata(str(export))
    with pytest.raises(RuntimeError, match="reads major version 1"):
        parse_into(tmp_path, export)


def test_missing_export_metadata_raises_saying_what_to_do(tmp_path):
    """A download directory with no metadata.json (a pre-1.0 export, or one preloaded from an older Babel
    build) should raise a RuntimeError that says to re-run the download, not a bare FileNotFoundError."""
    export = copy_fixture(tmp_path)
    (export / publications.EXPORT_METADATA).unlink()
    with pytest.raises(RuntimeError, match=r"metadata\.json is missing.*re-run download_pubmed2db"):
        parse_into(tmp_path, export)


@pytest.mark.parametrize(
    "edit",
    [
        pytest.param(lambda metadata: metadata["files"].pop(), id="fewer-shards"),
        pytest.param(lambda metadata: metadata.update(records=RECORD_COUNT + 1), id="another-record-total"),
    ],
)
def test_metadata_disagreeing_with_the_validation_report_raises(tmp_path, edit):
    """metadata.json and the validation report come from different pubmed2db steps, so if they list different
    shards or record totals they describe different exports, and the export should be refused."""
    export = copy_fixture(tmp_path)
    edit_metadata(export, edit)
    with pytest.raises(RuntimeError, match="describe different exports"):
        publications.read_export_metadata(str(export))


def test_metadata_without_file_hashes_raises(tmp_path):
    """A metadata.json whose files lack a sha256 (a format change) should raise a clear error rather than a
    KeyError."""
    export = copy_fixture(tmp_path)
    edit_metadata(export, lambda metadata: [entry.pop("sha256") for entry in metadata["files"]])
    with pytest.raises(RuntimeError, match="no usable files"):
        publications.read_export_metadata(str(export))


def _recompress(shard):
    """Rewrite a gzip file with the same records but different bytes (another timestamp in its header): an
    intact shard with the right record count that is nonetheless not the published one."""
    with gzip.open(shard, "rb") as f:
        records = f.read()
    with open(shard, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=1) as f:
        f.write(records)


def test_verify_shard_checksums_passes_the_fixture_and_names_every_bad_shard(tmp_path):
    """verify_shard_checksums() should accept shards matching metadata.json, and raise naming both a shard
    whose bytes differ -- though it is intact and has the right record count, so nothing else would catch
    it -- and one that is missing."""
    export = copy_fixture(tmp_path)
    metadata = publications.read_export_metadata(str(export))
    publications.verify_shard_checksums(str(export), metadata)

    _recompress(export / "pubmed_metadata_1.ndjson.gz")
    (export / "pubmed_metadata_2.ndjson.gz").unlink()
    with pytest.raises(RuntimeError) as excinfo:
        publications.verify_shard_checksums(str(export), metadata)
    assert "pubmed_metadata_1.ndjson.gz has SHA-256" in str(excinfo.value)
    assert "pubmed_metadata_2.ndjson.gz is missing" in str(excinfo.value)
    assert "pubmed_metadata_0" not in str(excinfo.value)


# DOWNLOADING


@pytest.fixture
def fake_export(tmp_path, monkeypatch):
    """Lay the fixture out like a published export (shards and metadata.json, the report under manifests/,
    and pubmed2db's own database as a decoy), and swap pull_via_wget() for a copy from it. Yields
    (remote_dir, calls)."""
    remote = tmp_path / "remote"
    (remote / "manifests").mkdir(parents=True)
    shutil.copy(os.path.join(FIXTURE_DIR, publications.EXPORT_METADATA), remote / publications.EXPORT_METADATA)
    for shard in publications.expected_shard_counts(FIXTURE_DIR):
        shutil.copy(os.path.join(FIXTURE_DIR, shard), remote / shard)
    shutil.copy(os.path.join(FIXTURE_DIR, publications.VALIDATION_REPORT), remote / "manifests" / "report.json")
    with gzip.open(remote / "manifests" / "report.json.gz", "wb") as f:
        f.write((remote / "manifests" / "report.json").read_bytes())
    (remote / "pubmed.duckdb").write_text("never download me")

    calls = []

    def fake_pull_via_wget(url_prefix, in_file_name, decompress, outpath, continue_incomplete):
        assert url_prefix == EXPORT_URL
        calls.append((in_file_name, continue_incomplete))
        ensure_parent_dir(outpath)
        shutil.copy(remote / in_file_name, outpath)
        if decompress:
            with gzip.open(outpath, "rb") as inf, open(outpath.removesuffix(".gz"), "wb") as outf:
                shutil.copyfileobj(inf, outf)
            os.remove(outpath)

    monkeypatch.setattr(publications, "pull_via_wget", fake_pull_via_wget)
    yield remote, calls


@pytest.mark.parametrize("report_path", ["manifests/report.json", "manifests/report.json.gz"])
def test_download_fetches_the_report_then_exactly_the_shards_it_lists(fake_export, tmp_path, report_path):
    """download_pubmed2db() should fetch metadata.json and the validation report (fresh, gunzipping the report
    if needed), then each shard they list (resumably) -- and nothing else in the export directory -- then
    touch the marker."""
    _, calls = fake_export
    download_dir = tmp_path / "PubMed2DB" / "2026nov08"
    done_file = download_dir / "downloaded"

    publications.download_pubmed2db(EXPORT_URL, report_path, str(download_dir), str(done_file))

    shards = list(publications.expected_shard_counts(FIXTURE_DIR))
    assert calls == [("metadata.json", False), (report_path, False)] + [(shard, True) for shard in shards]
    assert done_file.exists()
    assert publications.expected_shard_counts(str(download_dir)) == publications.expected_shard_counts(FIXTURE_DIR)
    assert not (download_dir / "pubmed.duckdb").exists()


def test_download_can_be_rerun_over_an_existing_download(fake_export, tmp_path):
    """Re-running download_pubmed2db() over a finished download (a retry, or a preloaded directory) should
    replace the report rather than fail on the old copy."""
    download_dir = tmp_path / "PubMed2DB" / "2026nov08"
    done_file = download_dir / "downloaded"
    for _ in range(2):
        publications.download_pubmed2db(EXPORT_URL, "manifests/report.json.gz", str(download_dir), str(done_file))
    assert publications.expected_shard_counts(str(download_dir)) == publications.expected_shard_counts(FIXTURE_DIR)


def test_download_of_a_failed_export_stops_before_the_shards(fake_export, tmp_path):
    """An export whose validation report says `fail` should not be downloaded, nor marked done."""
    remote, calls = fake_export
    edit_report(remote / "manifests" / "report.json", lambda report: report.update(status="fail"))
    download_dir = tmp_path / "PubMed2DB" / "2026nov08"
    with pytest.raises(RuntimeError, match="status 'fail'"):
        publications.download_pubmed2db(
            EXPORT_URL, "manifests/report.json", str(download_dir), str(download_dir / "downloaded")
        )
    assert calls == [("metadata.json", False), ("manifests/report.json", False)]
    assert not (download_dir / "downloaded").exists()


def test_download_of_another_data_model_stops_at_the_metadata(fake_export, tmp_path):
    """An export in a data model Babel doesn't read should be refused from its metadata.json alone, before the
    report or any shard is fetched."""
    remote, calls = fake_export
    edit_metadata(remote, lambda metadata: metadata.update(data_model_version="2.0.0"))
    download_dir = tmp_path / "PubMed2DB" / "2026nov08"
    with pytest.raises(RuntimeError, match="reads major version 1"):
        publications.download_pubmed2db(
            EXPORT_URL, "manifests/report.json", str(download_dir), str(download_dir / "downloaded")
        )
    assert calls == [("metadata.json", False)]
    assert not (download_dir / "downloaded").exists()


def test_download_over_another_exports_shard_is_refused(fake_export, tmp_path):
    """A download directory left holding a complete shard that is not the published one -- which
    `wget --continue` leaves alone -- should fail the SHA-256 check, naming the shard, and not be marked done."""
    remote, _ = fake_export
    download_dir = tmp_path / "PubMed2DB" / "2026nov08"
    done_file = download_dir / "downloaded"
    # The fake wget always copies from `remote`, so changing the shard there puts in download_dir what a
    # real wget would have left alone.
    _recompress(remote / "pubmed_metadata_0.ndjson.gz")
    with pytest.raises(RuntimeError, match=r"pubmed_metadata_0\.ndjson\.gz has SHA-256"):
        publications.download_pubmed2db(EXPORT_URL, "manifests/report.json", str(download_dir), str(done_file))
    assert not done_file.exists()


# BUILDING THE COMPENDIUM


@pytest.fixture
def babel_config(tmp_path):
    """Point Babel's download and output directories at a temporary tree, with empty common-label files so
    write_compendium()'s factories need no UberGraph download."""
    config = dict(src.util.get_config())
    config["download_directory"] = str(tmp_path / "babel_downloads")
    config["output_directory"] = str(tmp_path / "babel_outputs")
    for common_files in config["common"].values():
        for common_file in common_files:
            path = os.path.join(config["download_directory"], "common", common_file)
            ensure_parent_dir(path)
            open(path, "w").close()
    original = src.util.config_yaml
    src.util.config_yaml = config
    yield config
    src.util.config_yaml = original


def test_compendium_streams_one_clique_per_record(parsed, babel_config, tmp_path):
    """generate_compendium() should write one Publication clique per record, with the title as the PMID's
    label, PubMed Central ids kept, and a shared DOI present only in its winning clique."""
    icrdf = tmp_path / "icRDF.tsv"
    icrdf.write_text("")
    compendium = os.path.join(babel_config["output_directory"], "compendia", "Publication.txt")

    publications.generate_compendium(
        FIXTURE_DIR, parsed["shared_ids_file"], [parsed["metadata_yaml"]], compendium, str(icrdf)
    )

    with open(compendium) as f:
        cliques = [json.loads(line) for line in f]
    by_pmid = {clique["identifiers"][0]["i"]: clique for clique in cliques}
    assert len(cliques) == RECORD_COUNT and len(by_pmid) == RECORD_COUNT
    assert {clique["type"] for clique in cliques} == {PUBLICATION}

    def curies(pmid):
        return [identifier["i"] for identifier in by_pmid[pmid]["identifiers"]]

    def label(pmid):
        # write_compendium() writes an unlabeled identifier with an empty "l" (pre-existing behaviour).
        return by_pmid[pmid]["identifiers"][0].get("l", "")

    assert curies("PMID:5202740") == ["PMID:5202740", "PMC:PMC1712714"]
    assert label("PMID:5202740") == "Renal tubular acidosis: an immunopathological study on four patients."
    assert curies("PMID:5202677") == ["PMID:5202677"]
    # Malformed DOIs are repaired or skipped here exactly as in the concords, or write_compendium() would
    # fail the build on them.
    assert curies("PMID:17124311") == ["PMID:17124311", "doi:10.1126/science.1134405"]
    assert curies("PMID:23752222") == ["PMID:23752222", "doi:10.1001/archdermatol.2012.151a"]
    assert curies("PMID:16041191") == ["PMID:16041191"]
    assert curies("PMID:17072568") == ["PMID:17072568", "doi:10.1007/s00115-006-2195-7"]
    assert label("PMID:17072568") == ""

    # Labels are the exported titles exactly: the newline is a real character rather than `\n`, and
    # surrounding whitespace and control characters are kept (docs/sources/PubMed/README.md, "Titles").
    assert "Genotypes and\nHaplotype" in label("PMID:30803192")
    assert by_pmid["PMID:30803192"]["preferred_name"] == label("PMID:30803192")
    assert label("PMID:9245294") == "Identity as adaptation to social, cultural, and historical context "
    assert label("PMID:25303692") == "New challenges\x85."

    # biolink:Publication registers PMC ahead of doi, so the PubMed Central id sorts first (see #1044).
    assert curies("PMID:30803192") == ["PMID:30803192", "PMC:PMC6897020", "doi:10.31557/APJCP.2019.20.2.345"]
    assert curies("PMID:113") == ["PMID:113", "PMC:PMC1666769"]

    # The shared DOI lands on the lowest PMID only, so no identifier appears in two cliques.
    assert curies("PMID:7754980") == ["PMID:7754980", SHARED_DOI]
    assert curies("PMID:7754983") == ["PMID:7754983"]
    # The same for a DOI the two records spell in different cases; the winner keeps its own spelling.
    assert curies("PMID:26146547") == ["PMID:26146547", "PMC:PMC4486365", SHARED_CASE_DOI]
    assert curies("PMID:26214188") == ["PMID:26214188"]
    all_curies = [identifier["i"] for clique in cliques for identifier in clique["identifiers"]]
    assert len(all_curies) == len(set(all_curies))
