"""Unit tests for the babel-check-concords CLI wrapper.

The parser and the tally are tested in tests/model/test_intermediates.py; these cover finding the
files and the exit status. The HTTP crawl is exercised against a fake listing, not the network.
"""

import pytest

from src.tools.check_concords import cli

# CLI


def _intermediate_tree(root, bad_row=""):
    concords = root / "intermediate" / "protein" / "concords"
    concords.mkdir(parents=True)
    (concords / "NCIT_UniProtKB").write_text("NCIT:C150023\teq\tUniProtKB:Q9C0C9\n" + bad_row)
    (concords / "metadata-NCIT_UniProtKB.yaml").write_text("name: not a concord\n")
    (root / "intermediate" / "protein" / "ids").mkdir()
    (root / "intermediate" / "protein" / "ids" / "PR").write_text("PR:000000001\n")
    return root / "intermediate"


@pytest.mark.unit
def test_clean_concords_exit_zero(tmp_path, capsys):
    """Should check only files under concords/ (not metadata or ids) and exit 0 when all parse."""
    assert cli.main([str(_intermediate_tree(tmp_path))]) == 0
    out = capsys.readouterr().out
    assert "NCIT_UniProtKB\t1\t0\t" in out
    assert "metadata-" not in out
    assert "ids/PR" not in out


@pytest.mark.unit
def test_a_rejected_row_exits_one_and_is_shown(tmp_path, capsys):
    """Should exit 1 and print the first rejected line of each kind."""
    assert cli.main([str(_intermediate_tree(tmp_path, bad_row="NCIT:C179160\teq\t\n"))]) == 1
    out = capsys.readouterr().out
    assert "NCIT_UniProtKB\t2\t1\tempty column: 1" in out
    assert "first 'empty column' at line 2" in out


@pytest.mark.unit
def test_no_concords_found_raises(tmp_path):
    """Should raise rather than report a clean result when there was nothing to check."""
    with pytest.raises(RuntimeError, match="No concord files found"):
        cli.main([str(tmp_path)])


@pytest.mark.unit
def test_remote_listing_is_crawled_for_concords(monkeypatch):
    """Should follow subdirectories in an autoindex listing and keep only files under concords/."""
    base = "https://example.org/build/intermediate/"
    listings = {
        base: '<a href="../">../</a><a href="?C=M">sort</a><a href="protein/">protein/</a>',
        base + "protein/": '<a href="concords/">concords/</a><a href="ids/">ids/</a>',
        base + "protein/ids/": '<a href="PR">PR</a>',
        base + "protein/concords/": '<a href="UniProtKB">UniProtKB</a><a href="metadata-UniProtKB.yaml">m</a>',
    }

    class _Response:
        def __init__(self, body):
            self.body = body

        def read(self):
            return self.body.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(cli.urllib.request, "urlopen", lambda url, timeout: _Response(listings[url]))
    assert cli.find_remote_concords(base) == [base + "protein/concords/UniProtKB"]
