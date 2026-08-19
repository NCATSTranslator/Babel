import json

from src.babel_utils import norm, pull_via_urllib
from src.datahandlers.gard import normalize_gard_curie
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
    :param excluded_target_prefixes: targets whose CURIE prefix is in this collection are dropped
        outright. Matched **after** ``norm()``, i.e. against the renamed prefix (``ICD10``, not
        ``ICD10CM``), case-insensitively, using a raw split rather than ``Text.get_prefix()``
        because a DOID xref value can be colonless.

        The disease build passes nothing here. Its ICD problem -- an ICD code names a disease
        *family*, so one code fuses every subtype citing it -- is handled at glom time instead, by
        scoping ``remove_overused_xrefs`` to the ICD prefixes
        (``diseasephenotype.OVERUSE_FILTERED_CONCORDS``), which drops only the codes claimed by 2+
        DOID terms and keeps the 4,841 that are 1:1. A categorical exclusion remains the right
        instrument when *no* row of a namespace can be an equivalence; compare
        ``efo.make_concords(excluded_target_prefixes=EFO_EXCLUDED_XREF_PREFIXES)``, which drops MP
        outright to keep phenotype and disease apart. See docs/sources/DOID/mappings.md.
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
                    # DOID emits GARD ids in both the unpadded (GARD:6038) and the registry's
                    # zero-padded (GARD:0006038, 28 xrefs) form. Babel standardizes on the
                    # unpadded one, so unpad here too or the same rare disease lands in two
                    # cliques -- see the "Local-id form" note in src/datahandlers/gard.py. The one
                    # leading-zero xref that is NOT padding (GARD:0418, a typo for GARD:10418 on
                    # DOID:0061030) unpads to a real but unrelated id and is dropped downstream by
                    # input_data/doid_badxrefs.txt.
                    other = normalize_gard_curie(norm(xref["val"], other_prefixes))
                    if other.split(":", 1)[0].upper() in excluded_upper:
                        continue
                    xrefs.write(f"{doid_curie}\txref\t{other}\n")
