"""Tests for the helpers shared across the Snakemake files (src/snakefiles/util.py)."""

import pathlib
import re

import pytest

from src.snakefiles.util import common_download_files, duckdb_memory_limit_mb


@pytest.mark.unit
@pytest.mark.parametrize(
    "mem_mb,expected",
    [
        # Snakemake parses a rule's mem= with decimal suffixes, so mem="128G" reaches us as
        # mem_mb=128000, not 131072. These are the values the pipeline actually passes in.
        (128000, 96000),  # mem="128G" * 0.75
        (512000, 384000),  # mem="512G" * 0.75
        (1001, 750),  # a non-round allocation truncates rather than rounding up
    ],
)
def test_duckdb_memory_limit_mb(mem_mb, expected):
    """Should take resources.mem_mb (a plain int) and return `fraction` of it in MB, truncated.

    Not resources.mem: Snakemake stores every sized resource as mem_mb internally and re-exposes
    `mem` through humanfriendly formatting for display, so our "512G" rule setting comes back as
    the string "512 GB". mem_mb sidesteps that round-trip entirely.
    """
    assert duckdb_memory_limit_mb(mem_mb) == expected


# COMMON DOWNLOAD FILES

SNAKEFILES = sorted((pathlib.Path(__file__).parent.parent / "src" / "snakefiles").glob("*.snakefile"))

# Rules that declare icRDF.tsv but never read the common label/synonym/description files, with the reason.
ICRDF_WITHOUT_COMMON_FILES = {
    # build_conflation() reads icRDF.tsv only through InformationContentFactory, not write_compendium().
    "drugchemical_conflation",
}


def rule_blocks(snakefile):
    """Yield (rule name, rule text) for every rule in a Snakefile."""
    text = snakefile.read_text()
    matches = list(re.finditer(r"^(?:rule|localrule|checkpoint) (\w+):", text, re.MULTILINE))
    for match, following in zip(matches, matches[1:] + [None]):
        yield match.group(1), text[match.start() : following.start() if following else len(text)]


@pytest.mark.unit
def test_common_download_files_lists_every_common_file():
    """Should return the labels, synonyms and descriptions files from config["common"], under common/."""
    config = {
        "download_directory": "babel_downloads",
        "common": {
            "labels": ["ubergraph/labels"],
            "synonyms": ["ubergraph/synonyms.jsonl"],
            "descriptions": ["ubergraph/descriptions.jsonl"],
        },
    }
    assert common_download_files(config) == [
        "babel_downloads/common/ubergraph/labels",
        "babel_downloads/common/ubergraph/synonyms.jsonl",
        "babel_downloads/common/ubergraph/descriptions.jsonl",
    ]


@pytest.mark.unit
def test_rules_declaring_icrdf_declare_common_files():
    """Every rule declaring icRDF.tsv should also declare the common files, unless it is listed as not reading them.

    write_compendium() requires icrdf_filename and reads all the common files, so declaring icRDF.tsv marks
    the rules that need them. Relying on icRDF.tsv to pull them in transitively (as get_icrdf's inputs) let
    a taxon-only build fail with FileNotFoundError when icRDF.tsv was copied from a published build.
    """
    icrdf_rules = {
        f"{snakefile.name}: {name}": block
        for snakefile in SNAKEFILES
        for name, block in rule_blocks(snakefile)
        if 'icrdf_filename=config["download_directory"] + "/icRDF.tsv"' in block
    }
    # Guards the match itself: if the icRDF.tsv declaration were ever spelled differently, nothing would be checked.
    assert len(icrdf_rules) >= 13, f"only found {len(icrdf_rules)} rules declaring icRDF.tsv"
    missing = [
        rule
        for rule, block in icrdf_rules.items()
        if "util.common_download_files(config)" not in block and rule.split(": ")[1] not in ICRDF_WITHOUT_COMMON_FILES
    ]
    assert not missing, f"rules reading icRDF.tsv without declaring the common files: {missing}"
