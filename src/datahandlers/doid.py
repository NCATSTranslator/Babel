import json

from src.babel_utils import norm, pull_via_urllib
from src.prefixes import DOID, OIO


def pull_doid():
    pull_via_urllib(
        "https://raw.githubusercontent.com/DiseaseOntology/HumanDiseaseOntology/main/src/ontology/",
        "doid.json",
        subpath="DOID",
        decompress=False,
    )


def pull_doid_labels_and_synonyms(infile, labelfile, synonymfile):
    # Everything in DOID is a disease.
    with open(infile) as inf:
        j = json.load(inf)
    with open(labelfile, "w") as labels, open(synonymfile, "w") as syns:
        for entry in j["graphs"][0]["nodes"]:
            if ("meta" in entry) and ("deprecated" in entry["meta"]) and (entry["meta"]["deprecated"]):
                continue
            doid_id = entry["id"]
            if not doid_id.startswith("http://purl.obolibrary.org/obo/DOID_"):
                continue
            doid_curie = f"{DOID}:{doid_id.split('_')[-1]}"
            if "lbl" in entry:
                label = entry["lbl"]
                labels.write(f"{doid_curie}\t{label}\n")
                syns.write(f"{doid_curie}\t{OIO}:hasExactSynonym\t{label}\n")
            if ("meta" in entry) and ("synonyms" in entry["meta"]):
                for s in entry["meta"]["synonyms"]:
                    syns.write(f"{doid_curie}\t{OIO}:hasExactSynonym\t{s['val']}\n")


def build_xrefs(infile, xreffile, other_prefixes={}, excluded_target_prefixes=()):
    """Write DOID's hasDbXref rows to a concord as ``DOID:x<TAB>xref<TAB>target``.

    :param other_prefixes: source-prefix renames handed to ``norm()`` (e.g. ICD10CM -> ICD10).
    :param excluded_target_prefixes: targets whose CURIE prefix is in this collection are dropped.
        The disease build passes the ICD families: an ICD code names a disease *family*, not a
        disease, so no DOID->ICD xref is an equivalence, and feeding them to glom() as one fuses
        every subtype citing a code into a single clique. Matched **after** ``norm()``, i.e.
        against the renamed prefix (``ICD10``, not ``ICD10CM``), case-insensitively, using a raw
        split rather than ``Text.get_prefix()`` because a DOID xref value can be colonless.
        See ``diseasephenotype.DOID_EXCLUDED_XREF_PREFIXES`` and docs/sources/DOID/mappings.md.
    """
    excluded_upper = {prefix.upper() for prefix in excluded_target_prefixes}
    # Everything in DOID is a disease.
    with open(infile) as inf:
        j = json.load(inf)
    with open(xreffile, "w") as xrefs:
        for entry in j["graphs"][0]["nodes"]:
            if ("meta" in entry) and ("deprecated" in entry["meta"]) and (entry["meta"]["deprecated"]):
                continue
            doid_id = entry["id"]
            if not doid_id.startswith("http://purl.obolibrary.org/obo/DOID_"):
                continue
            doid_curie = f"{DOID}:{doid_id.split('_')[-1]}"
            if ("meta" in entry) and ("xrefs" in entry["meta"]):
                for xref in entry["meta"]["xrefs"]:
                    other = norm(xref["val"], other_prefixes)
                    if other.split(":", 1)[0].upper() in excluded_upper:
                        continue
                    xrefs.write(f"{doid_curie}\txref\t{other}\n")
