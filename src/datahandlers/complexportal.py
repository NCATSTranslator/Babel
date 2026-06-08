import contextlib
import os
import posixpath
import urllib.request
from html.parser import HTMLParser

from src.babel_utils import get_config, get_user_agent, pull_via_urllib
from src.categories import MACROMOLECULAR_COMPLEX
from src.metadata.provenance import write_metadata
from src.predicates import HAS_EXACT_SYNONYM
from src.prefixes import COMPLEXPORTAL

COMPLEXPORTAL_COMPLEXTAB_URL = "https://ftp.ebi.ac.uk/pub/databases/intact/complex/current/complextab/"
COMPLEXPORTAL_MANIFEST = "downloaded_tsv_files.txt"
COMPLEXPORTAL_DOWNLOAD_DONE = "download_done"


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


def fetch_complexportal_tsv_filenames(url=COMPLEXPORTAL_COMPLEXTAB_URL):
    """Fetch the list of available ComplexPortal TSV filenames by parsing the remote HTTP directory listing.

    Parses Apache autoindex HTML from `url` rather than using FTP NLST because HTTPS is more
    reliable for large file downloads. If EBI changes their listing format (e.g. switches to Nginx
    or a JS SPA) and this starts returning an empty list, switch to ftplib.FTP.nlst() for discovery
    while keeping pull_via_urllib for the actual download. See docs/sources/DownloadPatterns.md.
    """
    req = urllib.request.Request(url, headers={"User-Agent": get_user_agent()})
    with urllib.request.urlopen(req) as response:
        listing = response.read().decode("utf-8")

    parser = _DirectoryListingParser()
    parser.feed(listing)

    basenames = (posixpath.basename(h.rstrip("/")) for h in parser.hrefs)
    tsv_filenames = {f for f in basenames if f.endswith(".tsv")}

    if not tsv_filenames:
        raise RuntimeError(f"No ComplexPortal TSV files found at {url}")

    return sorted(tsv_filenames)


def _default_download_done_file():
    return os.path.join(get_config()["download_directory"], COMPLEXPORTAL, COMPLEXPORTAL_DOWNLOAD_DONE)


def pull_complexportal(download_done_file=None):
    if download_done_file is None:
        download_done_file = _default_download_done_file()

    download_dir = os.path.dirname(download_done_file)
    os.makedirs(download_dir, exist_ok=True)

    filenames = fetch_complexportal_tsv_filenames()
    for filename in filenames:
        pull_via_urllib(
            COMPLEXPORTAL_COMPLEXTAB_URL,
            filename,
            decompress=False,
            subpath=COMPLEXPORTAL,
        )

    manifest_file = os.path.join(download_dir, COMPLEXPORTAL_MANIFEST)
    with open(manifest_file, "w") as manifest:
        manifest.writelines(f"{fn}\n" for fn in filenames)

    # Written last so Snakemake only considers the download complete once both
    # the manifest and all TSV files are in place.
    with open(download_done_file, "w") as sentinel:
        sentinel.write(f"Downloaded {len(filenames)} ComplexPortal TSV files.\n")


def _read_manifest(manifest_file):
    with open(manifest_file) as manifest:
        return [line.strip() for line in manifest if line.strip()]


def make_labels_synonyms_and_taxa(
    manifest_file, download_dir, labelfile, synfile, taxafile, descfile, metadata_yaml, idsfile=None
):
    filenames = _read_manifest(manifest_file)
    used_identifiers = set()
    used_synonyms = set()
    used_taxa = set()
    used_descs = set()  # (identifier, description) pairs — same text from two files is written only once

    ids_ctx = open(idsfile, "w") if idsfile else contextlib.nullcontext()
    with (
        open(labelfile, "w") as outl,
        open(synfile, "w") as outsyn,
        open(taxafile, "w") as outt,
        open(descfile, "w") as outd,
        ids_ctx as outids,
    ):
        for filename in filenames:
            infile = os.path.join(download_dir, filename)
            if not os.path.exists(infile):
                raise RuntimeError(
                    f"{infile} is listed in the manifest but does not exist. "
                    f"Delete {os.path.join(download_dir, COMPLEXPORTAL_DOWNLOAD_DONE)} "
                    "and re-run the get_complexportal Snakemake rule to re-download all files."
                )
            with open(infile) as inf:
                next(inf)  # skip header
                for line in inf:
                    if not line.strip():
                        continue
                    sline = line.split("\t", 10)
                    if len(sline) < 10:
                        raise ValueError(f"Expected at least 10 columns in {infile}, found {len(sline)}")

                    identifier = f"{COMPLEXPORTAL}:{sline[0]}"
                    label = sline[1]  # recommended name
                    if identifier not in used_identifiers:
                        outl.write(f"{identifier}\t{label}\n")
                        if outids is not None:
                            outids.write(f"{identifier}\t{MACROMOLECULAR_COMPLEX}\n")
                        used_identifiers.add(identifier)

                    synonyms_str = sline[2]  # aliases for complex
                    if synonyms_str != "-":
                        for syn in synonyms_str.split("|"):
                            synonym_row = (identifier, syn)
                            if synonym_row not in used_synonyms:
                                outsyn.write(f"{identifier}\t{HAS_EXACT_SYNONYM}\t{syn}\n")
                                used_synonyms.add(synonym_row)

                    taxon_id = sline[3].strip()  # taxonomy identifier (NCBI taxon integer)
                    if taxon_id and taxon_id != "-":
                        if taxon_id.startswith("NCBITaxon:"):
                            raise ValueError(
                                f"Taxon ID {taxon_id!r} in {infile} is already prefixed; "
                                "expected a bare integer (e.g. '9606')"
                            )
                        taxa_row = (identifier, taxon_id)
                        if taxa_row not in used_taxa:
                            outt.write(f"{identifier}\tNCBITaxon:{taxon_id}\n")
                            used_taxa.add(taxa_row)

                    description = sline[9].strip()  # free-text description
                    if description and description != "-":
                        desc_row = (identifier, description)
                        if desc_row not in used_descs:
                            outd.write(f"{identifier}\t{description}\n")
                            used_descs.add(desc_row)

    write_metadata(
        metadata_yaml,
        typ="transform",
        name="ComplexPortal",
        description="Labels, synonyms, taxa, and descriptions extracted from ComplexPortal ComplexTAB downloads",
        sources=[
            {
                "type": "download",
                "name": f"ComplexPortal for organism {os.path.splitext(filename)[0]}",
                "url": f"{COMPLEXPORTAL_COMPLEXTAB_URL}{filename}",
            }
            for filename in filenames
        ],
    )
