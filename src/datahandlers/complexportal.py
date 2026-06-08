import os
import posixpath
import urllib.request
from html.parser import HTMLParser

from src.babel_utils import get_config, get_user_agent, pull_via_urllib
from src.metadata.provenance import write_metadata
from src.predicates import HAS_EXACT_SYNONYM
from src.prefixes import COMPLEXPORTAL

COMPLEXPORTAL_COMPLEXTAB_URL = "https://ftp.ebi.ac.uk/pub/databases/intact/complex/current/complextab/"
COMPLEXPORTAL_MANIFEST = "downloaded_tsv_files.txt"


class _DirectoryListingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href":
                self.hrefs.append(value)


def get_complexportal_tsv_filenames(url=COMPLEXPORTAL_COMPLEXTAB_URL):
    req = urllib.request.Request(url, headers={"User-Agent": get_user_agent()})
    with urllib.request.urlopen(req) as response:
        listing = response.read().decode("utf-8")

    parser = _DirectoryListingParser()
    parser.feed(listing)

    tsv_filenames = set()
    for href in parser.hrefs:
        filename = posixpath.basename(href.rstrip("/"))
        if filename.endswith(".tsv"):
            tsv_filenames.add(filename)

    if not tsv_filenames:
        raise RuntimeError(f"No ComplexPortal TSV files found at {url}")

    return sorted(tsv_filenames)


def _default_manifest_file():
    return os.path.join(get_config()["download_directory"], COMPLEXPORTAL, COMPLEXPORTAL_MANIFEST)


def pull_complexportal(manifest_file=None):
    if manifest_file is None:
        manifest_file = _default_manifest_file()

    filenames = get_complexportal_tsv_filenames()
    for filename in filenames:
        pull_via_urllib(
            COMPLEXPORTAL_COMPLEXTAB_URL,
            filename,
            decompress=False,
            subpath=COMPLEXPORTAL,
        )

    os.makedirs(os.path.dirname(manifest_file), exist_ok=True)
    with open(manifest_file, "w") as manifest:
        for filename in filenames:
            manifest.write(f"{filename}\n")


def _read_manifest(manifest_file):
    with open(manifest_file) as manifest:
        return [line.strip() for line in manifest if line.strip()]


def make_labels_and_synonyms(manifest_file, labelfile, synfile, metadata_yaml):
    filenames = _read_manifest(manifest_file)
    download_dir = os.path.dirname(manifest_file)
    used_labels = set()
    used_synonyms = set()

    with open(labelfile, "w") as outl, open(synfile, "w") as outsyn:
        for filename in filenames:
            infile = os.path.join(download_dir, filename)
            with open(infile) as inf:
                next(inf)  # skip header
                for line in inf:
                    sline = line.split("\t")
                    if len(sline) < 3:
                        raise ValueError(f"Expected at least 3 columns in {infile}, found {len(sline)}")

                    identifier = f"{COMPLEXPORTAL}:{sline[0]}"
                    label = sline[1]  # recommended name
                    if identifier not in used_labels:
                        outl.write(f"{identifier}\t{label}\n")
                        used_labels.add(identifier)

                    synonyms_str = sline[2]  # aliases
                    if synonyms_str != "-":
                        for syn in synonyms_str.split("|"):
                            synonym_row = (identifier, HAS_EXACT_SYNONYM, syn)
                            if synonym_row not in used_synonyms:
                                outsyn.write(f"{identifier}\t{HAS_EXACT_SYNONYM}\t{syn}\n")
                                used_synonyms.add(synonym_row)

    write_metadata(
        metadata_yaml,
        typ="transform",
        name="ComplexPortal",
        description="Labels and synonyms extracted from ComplexPortal ComplexTAB downloads",
        sources=[
            {
                "type": "download",
                "name": f"ComplexPortal for organism {os.path.splitext(filename)[0]}",
                "url": f"{COMPLEXPORTAL_COMPLEXTAB_URL}{filename}",
            }
            for filename in filenames
        ],
    )
