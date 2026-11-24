"""Bucket every live Sequence Ontology (SO) term by what it is relative to the Biolink Model.

Regenerates the evidence behind ``docs/sources/SO/README.md``, which explains why Babel does not
ingest SO. Each live SO term is assigned to the nearest ancestor (by ``is_a``, itself included)
that a Biolink class maps to. Terms whose nearest mapped ancestor is only the SO root
``sequence_feature``, or that have none, are split further by SO's own top-level branches
(``sequence_variant``, ``sequence_attribute``, ``sequence_collection``) and by the
``sequence_feature`` sub-branches that separate biology from lab artefacts.

The Biolink mappings are read from the Biolink Model version in ``config.yaml``, not hard-coded, so
a Biolink release that adds or fixes an SO mapping changes the output.

Usage::

    curl -sL -o data/so-analysis/so.obo http://purl.obolibrary.org/obo/so.obo
    uv run python docs/sources/SO/scripts/bucket_so_terms.py \
        --so-obo data/so-analysis/so.obo \
        --buckets-out docs/sources/SO/so-term-buckets.csv \
        --mappings-out docs/sources/SO/biolink-so-mappings.csv
"""

import argparse
import csv
from collections import defaultdict
from functools import cache

from src.util import get_biolink_model_toolkit, get_config

MAPPING_KINDS = ("exact_mappings", "close_mappings", "narrow_mappings", "broad_mappings", "related_mappings")

# SO's own branches, checked in this order for terms with no Biolink-mapped ancestor below the root.
# experimental_feature and biomaterial_region are lab and assay artefacts (reads, contigs, clones,
# PCR products); sequence_alteration is kinds of variant (deletion, insertion); junction is
# zero-length boundaries; biological_region is everything that is a feature of a real molecule.
SO_BRANCHES = {
    "SO:0001060": "sequence_variant",
    "SO:0000400": "sequence_attribute",
    "SO:0001260": "sequence_collection",
    "SO:0000703": "experimental_feature",
    "SO:0001409": "biomaterial_region",
    "SO:0001059": "sequence_alteration",
    "SO:0000699": "junction",
    "SO:0001411": "biological_region",
}
SO_ROOT = "SO:0000110"  # sequence_feature, mapped to biolink:NucleicAcidEntity


def parse_obo(path):
    """Return {id: {"name", "is_a", "obsolete", "has_spaced_synonym"}} for every [Term] stanza."""
    terms = {}
    cur = None
    in_term = False
    with open(path, encoding="utf8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("["):
                in_term = line == "[Term]"
                cur = None
            elif not in_term:
                continue
            elif line.startswith("id: "):
                cur = {"name": "", "is_a": [], "obsolete": False, "has_spaced_synonym": False}
                terms[line[4:]] = cur
            elif cur is None:
                continue
            elif line.startswith("name: "):
                cur["name"] = line[6:]
            elif line.startswith("is_a: "):
                cur["is_a"].append(line[6:].split(" ")[0])
            elif line == "is_obsolete: true":
                cur["obsolete"] = True
            elif line.startswith("synonym: ") and " EXACT" in line and " " in line.split('"')[1]:
                cur["has_spaced_synonym"] = True
    return terms


def biolink_so_mappings(version):
    """Return a list of (biolink element, element kind, mapping kind, SO CURIE)."""
    tk = get_biolink_model_toolkit(version)
    out = []
    for kind, names in (("class", tk.get_all_classes(formatted=True)), ("slot", tk.get_all_slots(formatted=True))):
        for name in names:
            element = tk.get_element(name)
            for mapping_kind in MAPPING_KINDS:
                for m in getattr(element, mapping_kind, None) or []:
                    if str(m).startswith("SO:"):
                        out.append((name, kind, mapping_kind, str(m)))
    return sorted(set(out))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--so-obo", required=True)
    parser.add_argument("--buckets-out", required=True)
    parser.add_argument("--mappings-out", required=True)
    args = parser.parse_args()

    terms = parse_obo(args.so_obo)
    live = {k: v for k, v in terms.items() if k.startswith("SO:") and not v["obsolete"]}
    mappings = biolink_so_mappings(get_config()["biolink_version"])
    class_for_so = {
        so: f"{name} ({mk.removesuffix('_mappings')})" for name, kind, mk, so in mappings if kind == "class"
    }

    @cache
    def distances(tid):
        """Return {ancestor: shortest is_a distance}, the term itself at distance 0."""
        out = {tid: 0}
        for parent in terms.get(tid, {}).get("is_a", []):
            for anc, d in distances(parent).items():
                if anc not in out or d + 1 < out[anc]:
                    out[anc] = d + 1
        return out

    buckets = defaultdict(list)
    for tid in sorted(live):
        dist = distances(tid)
        mapped = [a for a in dist if a in class_for_so and a != SO_ROOT]
        if mapped:
            nearest = min(mapped, key=lambda a: (dist[a], a))
            key = (class_for_so[nearest], live.get(nearest, {}).get("name", "?"))
        else:
            branch = next((label for so_id, label in SO_BRANCHES.items() if so_id in dist), "sequence_feature")
            key = ("(none below the root)", branch)
        buckets[key].append(tid)

    with open(args.buckets_out, "w", newline="", encoding="utf8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["nearest_biolink_class", "so_branch", "terms", "no_spaced_synonym", "examples"])
        for (cls, branch), ids in sorted(buckets.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            unspaced = sum(1 for t in ids if "_" in live[t]["name"] and not live[t]["has_spaced_synonym"])
            examples = "; ".join(live[t]["name"] for t in ids[:8])
            w.writerow([cls, branch, len(ids), unspaced, examples])

    with open(args.mappings_out, "w", newline="", encoding="utf8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["biolink_element", "element_kind", "mapping_kind", "so_curie", "so_label", "so_obsolete"])
        for name, kind, mk, so in mappings:
            t = terms.get(so)
            w.writerow([name, kind, mk, so, t["name"] if t else "", t["obsolete"] if t else ""])

    print(f"{len(live)} live SO terms in {len(buckets)} buckets; {len(mappings)} Biolink mappings to SO")


if __name__ == "__main__":
    main()
