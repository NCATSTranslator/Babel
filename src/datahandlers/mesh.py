import ftplib
import gzip
import hashlib
import json
import os
import warnings
from collections import defaultdict
from io import BytesIO
from xml.etree import ElementTree

import pyoxigraph

from src.babel_utils import make_local_name
from src.categories import ANATOMICAL_ENTITY, CELL, CELLULAR_COMPONENT
from src.prefixes import MESH
from src.util import ensure_parent_dir, get_logger

logger = get_logger(__name__)

MESH_IRI_PREFIX = "http://id.nlm.nih.gov/mesh/"


def get_mesh_id_from_iri(iri) -> str:
    """Extract a MeSH ID from a pyoxigraph IRI (e.g. <http://id.nlm.nih.gov/mesh/D009243>).

    Raises ValueError if the input is not a MeSH concept IRI.
    """
    s = str(iri)
    if s.startswith("<") and s.endswith(">"):
        s = s[1:-1]

    if not s.startswith(MESH_IRI_PREFIX):
        raise ValueError(f"Expected a MeSH IRI like <http://id.nlm.nih.gov/mesh/D009243>, got: '{s!r}'")
    return s[len(MESH_IRI_PREFIX) :]


MESH_FTP_SITE = "ftp.nlm.nih.gov"
MESH_RDF_DIR = "/online/mesh/rdf"


def mesh_rdf_location(mesh_year) -> tuple[str, str]:
    """Return the (FTP directory, filename) of the MeSH RDF N-Triples dump for ``mesh_year``.

    NLM publishes each MeSH release in its own year directory (e.g. /online/mesh/rdf/2026/mesh2026.nt.gz).
    The top-level /online/mesh/rdf/mesh.nt.gz stopped being updated after MeSH 2024, so we never use it.
    The per-year directory also has a mesh{year}-dups.nt, which is the same data before deduplication;
    mesh{year}.nt is the "combined, sorted, unique" file and is all we need.
    """
    return f"{MESH_RDF_DIR}/{mesh_year}", f"mesh{mesh_year}.nt.gz"


# A MeSH year's XML is in one of two places. While it is the current year it lives in MESH_XML_CURRENT_DIR, which
# NLM can update at any time and which holds no other year; once superseded, its final XML is archived in
# MESH_XML_ARCHIVE_DIR. Filenames carry the year in both. NLM publishes no checksums for either, so pull_mesh_xml()
# records the SHA-1 of what it downloaded instead.
MESH_XML_CURRENT_DIR = "/online/mesh/MESH_FILES/xmlmesh"
MESH_XML_ARCHIVE_DIR = "/online/mesh/{mesh_year}/xmlmesh"

# (file prefix, XML record element, record UI element). Each is published as {prefix}{year}.gz and saved
# as babel_downloads/MESH/{prefix}.xml.gz.
MESH_XML_FILES = [
    ("desc", "DescriptorRecord", "DescriptorUI"),
    ("supp", "SupplementalRecord", "SupplementalRecordUI"),
]


def _list_ftp_dir(ftp, ftpdir) -> set[str]:
    """Return the file names in ftpdir, or an empty set if NLM has no such directory.

    NLM answers a missing directory with "450 <dir>: No such file or directory", which ftplib raises as a
    *temporary* error. Only that reply means "absent"; any other error is re-raised, so a transient failure
    listing the archive cannot quietly send a build to the current directory instead.
    """
    try:
        return {os.path.basename(f) for f in ftp.nlst(ftpdir)}
    except (ftplib.error_perm, ftplib.error_temp) as e:
        if "No such file or directory" in str(e):
            return set()
        raise


def fetch_mesh_xml_dir(mesh_year) -> str:
    """Return the FTP directory holding desc{year}.gz and supp{year}.gz for ``mesh_year``.

    The year's archive (MESH_XML_ARCHIVE_DIR) is preferred over MESH_XML_CURRENT_DIR whenever it exists, because
    archived files no longer change: a build of a past year then gets the same XML whatever day it runs. Only the
    current year comes from MESH_XML_CURRENT_DIR, and pull_mesh_xml() records the SHA-1 of what it got, so two
    builds that downloaded different versions of it can be told apart.

    Raises RuntimeError if neither directory has both files. Besides a mesh_year NLM has not published, that
    happens at NLM's year rollover if MESH_FILES has moved on to the next year before the old one is archived.
    """
    names = {f"{prefix}{mesh_year}.gz" for prefix, _, _ in MESH_XML_FILES}
    archive_dir = MESH_XML_ARCHIVE_DIR.format(mesh_year=mesh_year)
    ftp = ftplib.FTP(MESH_FTP_SITE)
    try:
        ftp.login()
        for xml_dir in (archive_dir, MESH_XML_CURRENT_DIR):
            if names <= _list_ftp_dir(ftp, xml_dir):
                ftp.quit()
                return xml_dir
        ftp.quit()
    finally:
        ftp.close()
    raise RuntimeError(
        f"Neither {archive_dir} nor {MESH_XML_CURRENT_DIR} on {MESH_FTP_SITE} has all of {sorted(names)}. "
        "Check that mesh_year in config.yaml names a year NLM has published. If it does, NLM may be part-way "
        f"through its year rollover, with {MESH_XML_CURRENT_DIR} moved on to the next year before this one is "
        "archived; retry once the archive appears."
    )


def _retrieve_ftp_file(ftp, ftpfile, out_path) -> str:
    """Download ftpfile (relative to ftp's working directory) to out_path, returning its SHA-1 hex digest.

    Writes to out_path.part and renames it to out_path only once the transfer completes, so an interrupted
    download never leaves a partial file under the name a later run checks for.
    """
    part_path = f"{out_path}.part"
    sha1 = hashlib.sha1()
    try:
        with open(part_path, "wb") as outf:

            def write_chunk(chunk):
                sha1.update(chunk)
                outf.write(chunk)

            ftp.retrbinary(f"RETR {ftpfile}", write_chunk)
        os.replace(part_path, out_path)
    finally:
        if os.path.exists(part_path):
            os.remove(part_path)
    return sha1.hexdigest()


def parse_sha1_file(content: bytes, url) -> str:
    """Return the lowercase SHA-1 from the contents of an NLM .sha1 file ("<hash>  <filename>").

    Raises RuntimeError if the file does not start with a 40-digit hex digest, e.g. because a transfer came
    back empty, rather than reporting a checksum mismatch for a download that may be fine.
    """
    fields = content.decode("ascii", errors="replace").split()
    digest = fields[0].lower() if fields else ""
    if len(digest) != 40 or any(c not in "0123456789abcdef" for c in digest):
        raise RuntimeError(f"{url} should start with a 40-digit hex SHA-1, but reads {content[:100]!r}.")
    return digest


def normalize_mesh_nt(gz_path, out_path, mesh_year):
    """Decompress a per-year MeSH dump into out_path, rewriting its year-versioned IRIs to unversioned ones.

    The per-year dumps name records as <http://id.nlm.nih.gov/mesh/2026/D000001>, while everything that
    reads mesh.nt (the SPARQL in Mesh, get_mesh_id_from_iri()) expects <http://id.nlm.nih.gov/mesh/D000001>,
    which is how the old top-level dump and the id.nlm.nih.gov "current" IRIs name them. The vocabulary
    namespace (<http://id.nlm.nih.gov/mesh/vocab#>) is not versioned and passes through untouched.

    Writes to out_path.part and renames it to out_path only on success, so a failed or interrupted run never
    leaves a truncated mesh.nt behind for a later run (or measure_skew.py, which reuses any existing dump) to
    mistake for a complete one.

    Raises ValueError if no line carries the expected versioned prefix: that means the dump is not for
    mesh_year or NLM has changed its IRI scheme, and the file would otherwise be silently unusable.
    """
    versioned = f"<{MESH_IRI_PREFIX}{mesh_year}/"
    unversioned = f"<{MESH_IRI_PREFIX}"
    rewritten_lines = 0
    part_path = f"{out_path}.part"
    try:
        with gzip.open(gz_path, "rt", encoding="utf-8") as inf, open(part_path, "w", encoding="utf-8") as outf:
            for line in inf:
                if versioned in line:
                    line = line.replace(versioned, unversioned)
                    rewritten_lines += 1
                outf.write(line)
        if rewritten_lines == 0:
            raise ValueError(f"{gz_path} contains no {versioned}...> IRIs; is it really the MeSH {mesh_year} RDF dump?")
        os.replace(part_path, out_path)
    finally:
        if os.path.exists(part_path):
            os.remove(part_path)
    return rewritten_lines


def fetch_mesh_nt(mesh_year, out_path) -> dict:
    """Download the MeSH RDF dump for ``mesh_year``, check it against NLM's SHA-1 and normalize it into out_path.

    The SHA-1 is computed while the dump downloads, so the ~120 MB file is read only once more, to decompress
    it (see normalize_mesh_nt()). Fails if NLM has no dump for that year; there is deliberately no fallback to
    the stale top-level file. The compressed download is kept beside out_path only until it is normalized, and
    is removed whether or not that succeeds. out_path itself only ever appears complete.

    Returns a record of what was downloaded ({"mesh_year", "url", "sha1"}), which pull_mesh() saves for
    mesh_registry_sources().
    """
    ftpdir, ftpfile = mesh_rdf_location(mesh_year)
    url = f"ftp://{MESH_FTP_SITE}{ftpdir}/{ftpfile}"
    gz_path = f"{out_path}.gz"
    ensure_parent_dir(gz_path)
    sha1_file = BytesIO()
    try:
        ftp = ftplib.FTP(MESH_FTP_SITE)
        try:
            ftp.login()
            try:
                ftp.cwd(ftpdir)
                sha1 = _retrieve_ftp_file(ftp, ftpfile, gz_path)
            except ftplib.error_perm as e:
                raise RuntimeError(
                    f"Could not download MeSH {mesh_year} from {url} ({e}). "
                    "Check that mesh_year in config.yaml names a year NLM has published."
                ) from e
            try:
                ftp.retrbinary(f"RETR {ftpfile}.sha1", sha1_file.write)
            except ftplib.error_perm as e:
                # The dump itself downloaded, so the year is published: NLM has moved or renamed its checksum file.
                raise RuntimeError(
                    f"Downloaded {url}, but could not download its checksum file {url}.sha1 ({e})."
                ) from e
            ftp.quit()
        finally:
            ftp.close()

        expected_sha1 = parse_sha1_file(sha1_file.getvalue(), f"{url}.sha1")
        if sha1 != expected_sha1:
            raise RuntimeError(f"{url} downloaded with SHA-1 {sha1}, but NLM publishes {expected_sha1}.")

        normalize_mesh_nt(gz_path, out_path, mesh_year)
    finally:
        if os.path.exists(gz_path):
            os.remove(gz_path)
    return {"mesh_year": str(mesh_year), "url": url, "sha1": sha1}


def pull_mesh(mesh_year, rdf_source_file):
    """Download the MeSH RDF dump for ``mesh_year`` to babel_downloads/MESH/mesh.nt (see fetch_mesh_nt()).

    Records what was downloaded in rdf_source_file (JSON), so that provenance names the dump this build actually
    has rather than whatever mesh_year config.yaml says when a later rule runs.
    """
    source = fetch_mesh_nt(mesh_year, make_local_name("mesh.nt", subpath="MESH"))
    with open(rdf_source_file, "w", encoding="utf-8") as outf:
        json.dump(source, outf, indent=2)
        outf.write("\n")


def _ftp_modified_time(ftp, ftpfile):
    """Return ftpfile's modification time on the FTP server as an ISO 8601 UTC string, or None if not reported."""
    try:
        response = ftp.sendcmd(f"MDTM {ftpfile}")  # "213 YYYYMMDDHHMMSS", in UTC (RFC 3659)
    except ftplib.all_errors:
        return None
    stamp = response.split()[-1]
    if not (response.startswith("213") and len(stamp) >= 14 and stamp[:14].isdigit()):
        return None
    return f"{stamp[0:4]}-{stamp[4:6]}-{stamp[6:8]}T{stamp[8:10]}:{stamp[10:12]}:{stamp[12:14]}Z"


def pull_mesh_xml(mesh_year, xml_sources_file):
    """Download the MeSH XML descriptor and SCR files for ``mesh_year`` to babel_downloads/MESH.

    Only needed for registry numbers (see pull_mesh_registry()). Fails if NLM has no XML for that year.
    Writes a JSON list to xml_sources_file with each file's URL, SHA-1, size and NLM modification time, for
    mesh_registry_sources(). Which directory a file came from is only known at download time (see
    fetch_mesh_xml_dir()), and the SHA-1 is the only way to tell two downloads of the current year apart.
    """
    xml_dir = fetch_mesh_xml_dir(mesh_year)
    sources = []
    ftp = ftplib.FTP(MESH_FTP_SITE)
    try:
        ftp.login()
        ftp.cwd(xml_dir)
        for prefix, _, _ in MESH_XML_FILES:
            ftpfile = f"{prefix}{mesh_year}.gz"
            url = f"ftp://{MESH_FTP_SITE}{xml_dir}/{ftpfile}"
            out_path = make_local_name(f"{prefix}.xml.gz", subpath="MESH")
            ensure_parent_dir(out_path)
            try:
                sha1 = _retrieve_ftp_file(ftp, ftpfile, out_path)
            except ftplib.error_perm as e:
                # fetch_mesh_xml_dir() just listed the file, so this is not a mesh_year problem.
                raise RuntimeError(f"Could not download MeSH {mesh_year} XML from {url} ({e}).") from e
            sources.append(
                {
                    "mesh_year": str(mesh_year),
                    "url": url,
                    "sha1": sha1,
                    "size": os.path.getsize(out_path),
                    "modified": _ftp_modified_time(ftp, ftpfile),
                }
            )
        ftp.quit()
    finally:
        ftp.close()
    with open(xml_sources_file, "w", encoding="utf-8") as outf:
        json.dump(sources, outf, indent=2)
        outf.write("\n")


class Mesh:
    """Load the mesh rdf file for querying"""

    # Tracks how many Mesh instances currently hold mesh.nt in memory.
    # mesh.nt occupies ~2 GB in pyoxigraph's in-memory store; running two at the
    # same time on a 16 GB machine causes severe swapping or OOM failures.
    _active_instances: int = 0

    def __init__(self):
        if Mesh._active_instances > 0:
            warnings.warn(
                f"{Mesh._active_instances} Mesh instance(s) are already loaded in this "
                "process. Each instance holds mesh.nt in an in-memory pyoxigraph store "
                "(~2 GB); running multiple simultaneously can exhaust RAM on machines "
                "with ≤16 GB and cause severe slowdowns or OOM failures.",
                ResourceWarning,
                stacklevel=2,
            )
        ifname = make_local_name("mesh.nt", subpath="MESH")
        from datetime import datetime as dt

        print("loading mesh.nt")
        start = dt.now()
        self.m = pyoxigraph.Store()
        with open(ifname, "rb") as inf:
            self.m.bulk_load(input=inf, format=pyoxigraph.RdfFormat.N_TRIPLES)
        end = dt.now()
        print("loading complete")
        print(f"took {end - start}")
        Mesh._active_instances += 1  # only after successful load

    def __del__(self):
        if hasattr(self, "m"):  # only if __init__ completed successfully
            Mesh._active_instances = max(0, Mesh._active_instances - 1)

    def get_terms_in_tree(self, top_treenum):
        s = f"""   PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>
                PREFIX mesh: <http://id.nlm.nih.gov/mesh/>

                SELECT DISTINCT ?term
                WHERE {{ ?term meshv:treeNumber ?treenum .
                         ?treenum meshv:parentTreeNumber* mesh:{top_treenum}
                }}
                ORDER BY ?term
        """
        qres = self.m.query(s)
        meshes = []
        for row in qres:
            meshes.append(f"{MESH}:{get_mesh_id_from_iri(row['term'])}")
        return meshes

    def get_scr_terms_mapped_to_trees(self, top_treenums):
        """Get Supplementary Concept Record terms that are mapped to descriptors under any of the given tree numbers.

        SCR terms don't have tree numbers themselves, but they have meshv:mappedTo and/or
        meshv:preferredMappedTo relationships to descriptor terms that do. This method finds
        SCR terms whose mapped descriptors fall under the specified trees.

        Returns an empty set if top_treenums is empty."""
        if not top_treenums:
            return set()
        values_clause = " ".join(f"mesh:{t}" for t in top_treenums)
        s = f"""PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>
                PREFIX mesh: <http://id.nlm.nih.gov/mesh/>

                SELECT DISTINCT ?term
                WHERE {{ VALUES ?mappingPred {{ meshv:mappedTo meshv:preferredMappedTo }}
                         VALUES ?topTree {{ {values_clause} }}
                         ?term ?mappingPred ?descriptor .
                         ?descriptor meshv:treeNumber ?treenum .
                         ?treenum meshv:parentTreeNumber* ?topTree
                }}
                ORDER BY ?term
        """
        terms = set()
        for row in self.m.query(s):
            terms.add(f"{MESH}:{get_mesh_id_from_iri(row['term'])}")
        return terms

    def get_terms_with_type(self, termtype):
        s = f"""  PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX rdfns: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>
                PREFIX mesh: <http://id.nlm.nih.gov/mesh/>

                SELECT DISTINCT ?term
                WHERE {{ ?term rdfns:type meshv:{termtype} }}
                ORDER BY ?term
        """
        qres = self.m.query(s)
        meshes = []
        for row in qres:
            meshes.append(f"{MESH}:{get_mesh_id_from_iri(row['term'])}")
        return meshes

    def get_tree_numbers(self, mesh_id: str) -> list[str]:
        """Return the tree-number strings for a MeSH descriptor.

        Accepts "D009243" or "MESH:D009243". Returns strings like
        ["D08.211.589", "D03.633.100.759.646.138.694"] sorted alphabetically.
        Returns an empty list for SCR terms, which have no tree numbers of their own.
        """
        raw_id = mesh_id.split(":")[-1]
        s = f"""PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>
                PREFIX mesh: <http://id.nlm.nih.gov/mesh/>

                SELECT DISTINCT ?treenum
                WHERE {{ mesh:{raw_id} meshv:treeNumber ?treenum }}
                ORDER BY ?treenum
        """
        return [get_mesh_id_from_iri(row["treenum"]) for row in self.m.query(s)]

    def get_scr_mappings(self, scr_id: str) -> list[dict]:
        """Return mapping info for an SCR (Supplementary Concept Record) term.

        Accepts "C100843" or "MESH:C100843". Returns one dict per
        (predicate, descriptor) pair with keys:
          - "predicate":    "mappedTo" or "preferredMappedTo"
          - "descriptor":   CURIE, e.g. "MESH:D004338"
          - "label":        descriptor rdfs:label, or "" if absent
          - "tree_numbers": sorted list of tree-number strings for that descriptor
        """
        raw_id = scr_id.split(":")[-1]
        s = f"""PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>
                PREFIX mesh: <http://id.nlm.nih.gov/mesh/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

                SELECT DISTINCT ?mappingPred ?descriptor ?descLabel ?treenum
                WHERE {{
                    VALUES ?mappingPred {{ meshv:mappedTo meshv:preferredMappedTo }}
                    mesh:{raw_id} ?mappingPred ?descriptor .
                    OPTIONAL {{ ?descriptor rdfs:label ?descLabel }}
                    OPTIONAL {{ ?descriptor meshv:treeNumber ?treenum }}
                }}
                ORDER BY ?mappingPred ?descriptor ?treenum
        """
        mappings: dict[tuple, dict] = {}
        for row in self.m.query(s):
            pred = str(row["mappingPred"])[:-1].split("#")[-1]
            desc_id = f"{MESH}:{get_mesh_id_from_iri(row['descriptor'])}"
            key = (pred, desc_id)
            if key not in mappings:
                label = ""
                try:
                    desc_label = row["descLabel"]
                    if desc_label is not None:
                        label = desc_label.value
                except (KeyError, AttributeError):
                    pass
                mappings[key] = {"predicate": pred, "descriptor": desc_id, "label": label, "tree_numbers": []}
            treenum_val = row["treenum"]
            if treenum_val is not None:
                tree_id = get_mesh_id_from_iri(treenum_val)
                if tree_id not in mappings[key]["tree_numbers"]:
                    mappings[key]["tree_numbers"].append(tree_id)
        for info in mappings.values():
            info["tree_numbers"].sort()
        return list(mappings.values())

    def print_tree_labels(self):
        s = """   PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>
                PREFIX mesh: <http://id.nlm.nih.gov/mesh/>

                SELECT DISTINCT ?label ?treenum
                WHERE { ?term meshv:treeNumber ?treenum .
                    ?term rdfs:label ?label
                }
                ORDER BY ?treenum
        """
        qres = self.m.query(s)
        with open("mesh_tree_labels", "w", encoding="utf8") as outf:
            for row in qres:
                outf.write(f"{get_mesh_id_from_iri(row['treenum'])}\t{row['label'].value}\n")

    def pull_mesh_labels(self):
        s = """   PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>
                PREFIX mesh: <http://id.nlm.nih.gov/mesh/>

                SELECT DISTINCT ?term ?label
                WHERE { ?term rdfs:label ?label }
                ORDER BY ?term
        """
        ofname = make_local_name("labels", subpath="MESH")
        qres = self.m.query(s)
        with open(ofname, "w", encoding="utf8") as outf:
            for row in qres:
                outf.write(f"{MESH}:{get_mesh_id_from_iri(row['term'])}\t{row['label'].value}\n")


def pull_mesh_labels():
    m = Mesh()
    m.pull_mesh_labels()


def read_mesh_xml_registry(xml_gz_path, record_tag, ui_tag):
    """Yield (MESH:ID, registry number) for each record's preferred concept in a gzipped MeSH XML file.

    record_tag/ui_tag are DescriptorRecord/DescriptorUI for desc{year}.gz and
    SupplementalRecord/SupplementalRecordUI for supp{year}.gz. Only the preferred concept's
    RegistryNumber is used (not RelatedRegistryNumber), and MeSH's "0" placeholder for
    "no registry number" is skipped.
    """
    with gzip.open(xml_gz_path, "rb") as inf:
        for _, elem in ElementTree.iterparse(inf, events=("end",)):
            if elem.tag != record_tag:
                continue
            ui = elem.findtext(ui_tag)
            if not ui:
                raise ValueError(f"{record_tag} without a {ui_tag} in {xml_gz_path}")
            for concept in elem.iterfind("ConceptList/Concept[@PreferredConceptYN='Y']"):
                for reg in concept.iterfind("RegistryNumberList/RegistryNumber"):
                    regnum = (reg.text or "").strip()
                    if regnum and regnum != "0":
                        yield f"{MESH}:{ui}", regnum
            elem.clear()


def pull_mesh_registry(desc_xml, supp_xml, mesh_labels):
    """Return sorted, unique (MESH:ID, registry number) pairs for the MeSH descriptors and SCRs in the RDF dump.

    Registry numbers are CAS numbers, UNIIs, EC numbers and NCBI Taxon IDs ("txid..."). They come from the
    MeSH XML (desc_xml and supp_xml, i.e. desc{year}.gz and supp{year}.gz) rather than the RDF dump because
    NLM's per-year RDF dumps stopped including meshv:registryNumber from MeSH 2025 onward.

    The current year's XML can be updated after the RDF dump is published, so it can name records the dump
    does not have (100 SCRs on 2026-10-21). Pairs are kept only for records with a label in mesh_labels
    (babel_downloads/MESH/labels, read from the dump), so that a registry number never brings in a MeSH ID
    that has no label or type anywhere else in the build: a concord alone can put a CURIE into a compendium.

    That matters most for taxon: taxon.write_mesh_ids() adds every record with an NCBI Taxon registry number to
    its ids/MESH (#1240), so a record missing from the dump would otherwise become a taxon identifier.

    Raises ValueError if none are found, since every caller (the chemical CAS/UNII concords and the
    MeSH-NCBITaxon concord) would otherwise silently come out empty.
    """
    with open(mesh_labels, encoding="utf-8") as inf:
        labeled_ids = {line.split("\t", 1)[0] for line in inf}
    registry = set()
    not_in_dump = set()
    for (_, record_tag, ui_tag), xml_gz_path in zip(MESH_XML_FILES, (desc_xml, supp_xml), strict=True):
        for meshid, regnum in read_mesh_xml_registry(xml_gz_path, record_tag, ui_tag):
            if meshid in labeled_ids:
                registry.add((meshid, regnum))
            else:
                not_in_dump.add(meshid)
    if not_in_dump:
        logger.info(
            f"Skipped registry numbers for {len(not_in_dump):,} MeSH records in the XML but not in {mesh_labels}, "
            f"e.g. {', '.join(sorted(not_in_dump)[:5])}."
        )
    if not registry:
        raise ValueError("No registry numbers found in the MeSH XML files; has the MeSH XML format changed?")
    return sorted(registry)


def write_mesh_registry(desc_xml, supp_xml, mesh_labels, outfile):
    """Write pull_mesh_registry()'s pairs to outfile as "MESH:ID<tab>registry number" lines.

    The MeSH XML is parsed once here (rule get_mesh_registry) rather than in each rule that needs registry
    numbers, and the TSV lets anyone check which registry numbers a build used.
    """
    registry = pull_mesh_registry(desc_xml, supp_xml, mesh_labels)
    with open(outfile, "w", encoding="utf-8") as outf:
        outf.writelines(f"{meshid}\t{regnum}\n" for meshid, regnum in registry)


def read_mesh_registry(registry_file) -> list[tuple[str, str]]:
    """Read the (MESH:ID, registry number) pairs that write_mesh_registry() wrote.

    Raises ValueError on a row that is not two non-empty tab-separated fields, or if the file is empty: both
    mean it was not written by write_mesh_registry(), which never writes an empty registry.
    """
    registry = []
    with open(registry_file, encoding="utf-8") as inf:
        for lineno, line in enumerate(inf, start=1):
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 2 or not all(fields):
                raise ValueError(f"{registry_file} line {lineno} is not 'MESH:ID<tab>registry number': {line!r}")
            registry.append((fields[0], fields[1]))
    if not registry:
        raise ValueError(f"{registry_file} has no registry numbers.")
    return registry


def read_mesh_ids_with_ncbitaxon(registry_file) -> set[str]:
    """Return the MeSH IDs that write_mesh_registry() gave an NCBI Taxon registry number ("txid...").

    NLM gives a record an NCBI Taxon registry number only when it names an organism, so these records belong to
    the taxon pipeline whatever their MeSH record class: taxon.write_mesh_ids() claims them, and every other
    MeSH-owning pipeline must leave them alone (chemicals.write_mesh_ids() excludes them, and
    taxon.build_relationships() fails if any other pipeline claims one). See
    https://github.com/NCATSTranslator/Babel/issues/1240.
    """
    return {meshid for meshid, regnum in read_mesh_registry(registry_file) if regnum.startswith("txid")}


def mesh_registry_sources(rdf_source_file, xml_sources_file) -> list[dict]:
    """Return write_concord_metadata() sources for a concord built from the MeSH registry.

    Both files are written at download time: rdf_source_file by pull_mesh() and xml_sources_file by
    pull_mesh_xml(). Reading them here, rather than config.yaml's mesh_year, means the sources name what was
    actually downloaded even if mesh_year has changed since.

    Raises ValueError if the two downloads are for different MeSH years, which would mean the registry numbers
    were filtered against another year's records.
    """
    with open(rdf_source_file, encoding="utf-8") as inf:
        rdf = json.load(inf)
    with open(xml_sources_file, encoding="utf-8") as inf:
        xml = json.load(inf)
    xml_years = {source["mesh_year"] for source in xml}
    if xml_years != {rdf["mesh_year"]}:
        raise ValueError(
            f"{xml_sources_file} is for MeSH {sorted(xml_years)} but {rdf_source_file} is for MeSH "
            f"{rdf['mesh_year']}; rerun rules get_mesh and get_mesh_xml with the same mesh_year."
        )
    return [
        {
            "type": "MeSH",
            "name": f"MeSH {source['mesh_year']} XML (registry numbers)",
            "url": source["url"],
            "sha1": source["sha1"],
            "modified": source["modified"],
        }
        for source in xml
    ] + [
        {
            "type": "MeSH",
            "name": f"MeSH {rdf['mesh_year']} RDF (records kept)",
            "url": rdf["url"],
            "sha1": rdf["sha1"],
        }
    ]


def write_ids(
    meshmap,
    outfile,
    order=[CELLULAR_COMPONENT, CELL, ANATOMICAL_ENTITY],
    extra_vocab={},
    scr_exclude_trees=None,
    scr_include_trees=None,
    extra_terms=None,
    exclude_terms=None,
):
    """Write the mesh identifiers from a particular set of hierarchies to an output directory.
    This might be a mixed list of types (for instance anatomy and cell).  Also, the same term
    may appear in multiple trees, perhaps with different types.

    scr_exclude_trees: optional list of tree numbers. SCR terms (from extra_vocab) that are
    mapped to descriptors under these trees will be marked as EXCLUDE.
    scr_include_trees: optional list of tree numbers. If set, only SCR terms (from extra_vocab)
    that are mapped to descriptors under these trees will be kept; all other SCR terms will be
    removed. Cannot be used together with scr_exclude_trees.
    extra_terms: optional dict of MeSH CURIE -> type, added whatever their tree or record class. Each type must be
    in ``order``.
    exclude_terms: optional collection of MeSH CURIEs never written, whatever selected them (extra_terms
    included). Used to leave a record to the pipeline that owns it."""
    if scr_exclude_trees is not None and scr_include_trees is not None:
        raise ValueError("scr_exclude_trees and scr_include_trees cannot both be set")
    m = Mesh()
    terms2type = defaultdict(set)
    for treenum, category in meshmap.items():
        mesh_terms = m.get_terms_in_tree(treenum)
        for mt in mesh_terms:
            terms2type[mt].add(category)
    if scr_include_trees:
        # Only add extra_vocab terms that are mapped to descriptors under the included trees.
        # This is the inverse of scr_exclude_trees: instead of adding all SCR terms and then
        # marking some as EXCLUDE, we only add SCR terms that match the included trees.
        included_scr_terms = m.get_scr_terms_mapped_to_trees(scr_include_trees)
        for k, v in extra_vocab.items():
            mesh_terms = m.get_terms_with_type(k)
            for mt in mesh_terms:
                if mt in included_scr_terms:
                    terms2type[mt].add(v)
    else:
        for k, v in extra_vocab.items():
            mesh_terms = m.get_terms_with_type(k)
            for mt in mesh_terms:
                terms2type[mt].add(v)
        if scr_exclude_trees:
            excluded_scr_terms = m.get_scr_terms_mapped_to_trees(scr_exclude_trees)
            for mt in excluded_scr_terms:
                terms2type[mt].add("EXCLUDE")
    for term, category in (extra_terms or {}).items():
        terms2type[term].add(category)
    for term in exclude_terms or ():
        terms2type.pop(term, None)
    with open(outfile, "w") as idfile:
        for term, typeset in terms2type.items():
            list_typeset = list(typeset)
            list_typeset.sort(key=lambda x: order.index(x))
            if list_typeset[0] == "EXCLUDE":
                continue
            idfile.write(f"{term}\t{list_typeset[0]}\n")


#    ifname = make_local_name('mesh.nt', subpath='MESH')
#    ofname = make_local_name('labels', subpath='MESH')
#    badlines = 0
#    with open(ofname, 'w') as outf, open(ifname,'r') as data:
#        for line in data:
#            if line.startswith('#'):
#                continue
#            triple = line[:-1].strip().split('\t')
#            try:
#                s,v,o = triple
#                if v == '<http://www.w3.org/2000/01/rdf-schema#label>':
#                    meshid = s[:-1].split('/')[-1]
#                    label = o.strip().split('"')[1]
#                    outf.write(f'MESH:{meshid}\t{label}\n')
#            except ValueError:
#                badlines += 1
#    print(f'{badlines} lines were bad')

if __name__ == "__main__":
    mesh = Mesh()
    mesh.print_tree_labels()
    # mesh.pull_mesh_labels()
