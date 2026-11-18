from collections import Counter, defaultdict

import src.datahandlers.mesh as mesh
import src.datahandlers.ncbitaxon as ncbitaxon
import src.datahandlers.umls as umls
from src.babel_utils import glom, read_identifier_file, unique_prefixes_from_config, write_compendium
from src.categories import ORGANISM_TAXON
from src.metadata.provenance import write_concord_metadata
from src.model.intermediates import read_concord_pairs, read_concords
from src.prefixes import MESH, NCBITAXON
from src.util import get_logger

logger = get_logger(__name__)

NCBI_TAXONOMY_SOURCE = {
    "type": "NCBITaxon",
    "name": "NCBI Taxonomy merged.dmp and delnodes.dmp",
    "url": "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz",
}


def write_mesh_ids(outfile):
    # Get the B tree,
    # B01	Eukaryota
    # B02	Archaea
    # B03	Bacteria
    # B04	Viruses
    # B05	Organism Forms
    meshmap = {f"B{str(i).zfill(2)}": ORGANISM_TAXON for i in range(1, 6)}
    # Also add anything from SCR_Chemical, if it doesn't have a tree map
    mesh.write_ids(meshmap, outfile, order=[ORGANISM_TAXON], extra_vocab={"SCR_Organism": ORGANISM_TAXON})


def write_umls_ids(mrsty, outfile, *, mesh_ownership=None):
    """Select the UMLS CUIs the taxon pipeline claims by semantic type.

    ``mesh_ownership`` (the umls_mesh_ownership rule's output) makes a CUI follow its MeSH descriptor
    (umls.apply_mesh_ownership): a CUI another pipeline owns is dropped here and a CUI this pipeline owns is added.
    A plant or virus CUI whose descriptor is an anatomy A-tree or SCR_Chemical record leaves taxon this way
    (https://github.com/NCATSTranslator/Babel/issues/1123).
    """
    # UMLS categories that should be classified as taxa:
    # - A1.1.3: Eukaryote (https://uts.nlm.nih.gov/uts/umls/semantic-network/T204)
    # - A1.1.2: Bacterium (https://uts.nlm.nih.gov/uts/umls/semantic-network/T007)
    # - A1.1.3.3: Plant (https://uts.nlm.nih.gov/uts/umls/semantic-network/T002)
    # - A1.1.3.2: Fungus (https://uts.nlm.nih.gov/uts/umls/semantic-network/T004)
    # - A1.1.3.1.1.3: Fish (https://uts.nlm.nih.gov/uts/umls/semantic-network/T013)
    # - A1.1.3.1.1.2: Bird (https://uts.nlm.nih.gov/uts/umls/semantic-network/T012)
    # - A1.1.4: Virus (https://uts.nlm.nih.gov/uts/umls/semantic-network/T005)
    # - A1.1.3.1.1.4: Mammal (https://uts.nlm.nih.gov/uts/umls/semantic-network/T015)
    # - A1.1.3.1.1.5: Reptile (https://uts.nlm.nih.gov/uts/umls/semantic-network/T014)
    # - A1.1.3.1.1.1: Amphibian (https://uts.nlm.nih.gov/uts/umls/semantic-network/T011)
    # - A1.1.1: Archaeon (https://uts.nlm.nih.gov/uts/umls/semantic-network/T194)
    # - A1.1.3.1: Animal (https://uts.nlm.nih.gov/uts/umls/semantic-network/T008)
    # - A1.1: Organism (https://uts.nlm.nih.gov/uts/umls/semantic-network/T001)
    # - A1.1.3.1.1: Vertebrate (https://uts.nlm.nih.gov/uts/umls/semantic-network/T010)
    #
    # Not clear if these should be included, so left out for now:
    # - A1.1.3.1.1.4.1: Human (https://uts.nlm.nih.gov/uts/umls/semantic-network/T016)
    #   (presumably the human taxon is represented as _Homo sapiens_, which is http://id.nlm.nih.gov/mesh/D006801)

    umlsmap = {
        x: ORGANISM_TAXON
        for x in [
            "A1.1.3",
            "A1.1.2",
            "A1.1.3.3",
            "A1.1.3.2",
            "A1.1.3.1.1.3",
            "A1.1.3.1.1.2",
            "A1.1.4",
            "A1.1.3.1.1.4",
            "A1.1.3.1.1.5",
            "A1.1.3.1.1.1",
            "A1.1.1",
            "A1.1.3.1",
            "A1.1",
            "A1.1.3.1.1",
        ]
    }
    umls.write_umls_ids(
        mrsty,
        umlsmap,
        outfile,
        mesh_ownership=mesh_ownership,
        pipeline="taxon",
    )


# Name classes in NCBI Taxonomy's names.dmp that say a name is only part of a taxon, not the taxon itself:
# "includes" names a group the taxon contains, and "in-part" one that overlaps it. When NCBI merges a taxon
# into a broader one, the old name is usually kept under one of these (Pancrustacea "includes" Crustacea).
#
# A record matching one of these is not linked to the taxon even if another of its names matches one of
# the taxon's synonyms. Those mixed matches are almost always a group sunk into a broader one, whose old
# name NCBI keeps as a nomenclatural synonym: UMLS "Emex" has both "Emex" and "Rumex subgen. Emex" as
# names, and NCBI lists the first as a synonym of Rumex and the second as a name Rumex "includes", but the
# record is the subgenus, not all of Rumex.
NCBITAXON_PARTIAL_NAME_CLASSES = {"includes", "in-part"}

# What update_obsolete_ncbitaxon_ids() decided about each row pointing at a merged NCBITaxon ID. These are
# also the keys of the counts recorded under "obsolete_ncbitaxon" in the concord metadata YAMLs.
REMAPPED_MERGED = "remapped_merged"
DROPPED_MERGED_ALREADY_LINKED = "dropped_merged_already_linked"
DROPPED_MERGED_INTO_BROADER_TAXON = "dropped_merged_into_broader_taxon"
DROPPED_MERGED_SUPERSEDED_BY_DIRECT = "dropped_merged_superseded_by_direct"
DROPPED_MERGED_AMBIGUOUS = "dropped_merged_ambiguous"
DROPPED_DELETED = "dropped_deleted"

# How each taxon concord is described in its metadata YAML.
TAXON_CONCORD_METADATA = {
    "UMLS": {
        "name": "build_taxon_umls_relationships()",
        "description": "umls.build_sets() using UMLS MRCONSO to link taxon CUIs to MeSH (MSH) and NCBI Taxonomy "
        "(NCBI), then update_obsolete_ncbitaxon_ids() to update merged and remove deleted NCBITaxon IDs.",
        "sources": [{"type": "UMLS", "name": "MRCONSO"}, NCBI_TAXONOMY_SOURCE],
    },
    "NCBI_MESH": {
        "name": "build_relationships()",
        "description": "Links MeSH to NCBI Taxonomy through txid registry numbers in the MeSH registry, then "
        "update_obsolete_ncbitaxon_ids() to update merged and remove deleted NCBITaxon IDs.",
        "sources": [
            {"type": "MeSH", "name": "MeSH Registry", "url": "ftp://ftp.nlm.nih.gov/online/mesh/rdf/mesh.nt.gz"},
            NCBI_TAXONOMY_SOURCE,
        ],
    },
}


def ncbitaxon_link(row):
    """Return (other CURIE, NCBITaxon CURIE) for a row linking a non-NCBITaxon CURIE to NCBITaxon, else None."""
    subject, _, obj = row
    subject_is_taxon = subject.startswith(f"{NCBITAXON}:")
    obj_is_taxon = obj.startswith(f"{NCBITAXON}:")
    if obj_is_taxon and not subject_is_taxon:
        return subject, obj
    if subject_is_taxon and not obj_is_taxon:
        return obj, subject
    return None


def partner_map(concords):
    """Map each non-NCBITaxon CURIE to the non-NCBITaxon CURIEs it is linked to (e.g. UMLS <-> MeSH)."""
    partners = defaultdict(set)
    for rows in concords.values():
        for subject, _, obj in rows:
            if not subject.startswith(f"{NCBITAXON}:") and not obj.startswith(f"{NCBITAXON}:"):
                partners[subject].add(obj)
                partners[obj].add(subject)
    return partners


def read_record_names(identifiers, label_files, synonym_files):
    """
    Read the labels and synonyms of the given MeSH/UMLS identifiers, casefolded for matching.

    :param identifiers: The CURIEs to read names for; all others are skipped.
    :param label_files: Label files (CURIE\tlabel).
    :param synonym_files: Synonym files (CURIE\tpredicate\tsynonym).
    :return: A dict mapping each CURIE to a set of casefolded names.
    """
    names = defaultdict(set)
    for filename, name_column in [(f, 1) for f in label_files] + [(f, 2) for f in synonym_files]:
        with open(filename) as inf:
            for line in inf:
                parts = line.rstrip("\n").split("\t")
                if parts[0] in identifiers:
                    names[parts[0]].add(parts[name_column].strip().casefold())
    return names


def resolve_obsolete_ncbitaxon_ids(concords, merged, deleted, record_names, taxon_names):
    """
    Decide what to do with every row in the taxon concords that refers to an obsolete NCBITaxon ID.

    This is the logic behind update_obsolete_ncbitaxon_ids(); see its docstring for why each rule exists. It
    looks at all the concords together, because the taxon cliques are built from all of them: a MeSH
    record can reach a taxon through its UMLS partner, and the other way around.

    A record "reaches" a taxon through a row if the row links the record or one of its partners (the
    non-NCBITaxon CURIEs it shares a concord row with) to that taxon. A row with a merged NCBITaxon ID is
    checked in this order:

    1. DROPPED_MERGED_ALREADY_LINKED: the record already reaches the current taxon directly, so the
       remapped row adds nothing.
    2. DROPPED_MERGED_INTO_BROADER_TAXON: NCBI lists one of the record's names under the current taxon with a
       class in NCBITAXON_PARTIAL_NAME_CLASSES, i.e. the merge made the record part of a broader taxon.
    3. DROPPED_MERGED_SUPERSEDED_BY_DIRECT: a different record with the same prefix as the record or one of
       its partners reaches the current taxon directly, and only one of each prefix can join its clique.
    4. DROPPED_MERGED_AMBIGUOUS: after the rules above, several records of one prefix would reach the
       current taxon only through remapped rows. If exactly one of them has the taxon's scientific name as
       a label or synonym, it keeps its row; otherwise none do, as there is nothing to choose between them.
    5. REMAPPED_MERGED: otherwise, the row is kept with the merged ID replaced.

    Rows with a deleted NCBITaxon ID are dropped (DROPPED_DELETED).

    :param concords: A dict mapping each concord name to its (subject, predicate, object) rows.
    :param merged: A dict mapping merged NCBITaxon CURIEs to their replacements (read_obsolete_taxa()).
    :param deleted: A set of deleted NCBITaxon CURIEs (read_obsolete_taxa()).
    :param record_names: A dict mapping MeSH/UMLS CURIEs to casefolded names (read_record_names()). It must
        cover every record with a merged NCBITaxon ID, and their partners.
    :param taxon_names: A dict mapping each merge target to {name: set of name classes} (read_taxon_names()).
    :return: A tuple (rows, decisions). `rows` maps each concord name to the rows to write, in their
        original order with merged IDs replaced and duplicates removed. `decisions` is a list of dicts, one
        per row with an obsolete ID, with keys concord, identifier, obsolete, current and decision.
    """
    decisions = []
    live = {}
    for name, rows in concords.items():
        live[name] = []
        for row in rows:
            link = ncbitaxon_link(row)
            if any(curie in deleted for curie in row):
                identifier, taxon = link if link else (row[0], row[2])
                decisions.append(
                    {
                        "concord": name,
                        "identifier": identifier,
                        "obsolete": taxon,
                        "current": "",
                        "decision": DROPPED_DELETED,
                    }
                )
            else:
                live[name].append(row)

    partners = partner_map(live)

    def with_partners(identifier):
        return {identifier} | partners[identifier]

    def prefix(curie):
        return curie.split(":")[0]

    def folded(taxon):
        result = defaultdict(set)
        for taxon_name, classes in taxon_names.get(taxon, {}).items():
            result[taxon_name.strip().casefold()] |= classes
        return result

    # Who reaches each current taxon through a row that doesn't involve a merged ID.
    direct = defaultdict(set)
    remapped = []
    for name, rows in live.items():
        for index, row in enumerate(rows):
            link = ncbitaxon_link(row)
            if link is None:
                continue
            identifier, taxon = link
            if taxon in merged:
                remapped.append((name, index, identifier, taxon, merged[taxon]))
            else:
                direct[taxon] |= with_partners(identifier)

    decided = {}
    candidates = []
    for name, index, identifier, obsolete, current in remapped:
        target_names = folded(current)
        matched_classes = set()
        for record_name in record_names.get(identifier, ()):
            matched_classes |= target_names.get(record_name, set())
        reaching = with_partners(identifier)
        if identifier in direct[current]:
            decided[(name, index)] = DROPPED_MERGED_ALREADY_LINKED
        elif matched_classes & NCBITAXON_PARTIAL_NAME_CLASSES:
            decided[(name, index)] = DROPPED_MERGED_INTO_BROADER_TAXON
        elif any(prefix(r) == prefix(d) and r != d for r in reaching for d in direct[current]):
            decided[(name, index)] = DROPPED_MERGED_SUPERSEDED_BY_DIRECT
        else:
            candidates.append((name, index, identifier, obsolete, current))

    # Records that would reach each (prefix, current taxon) only through remapped rows.
    claimants = defaultdict(set)
    for name, index, identifier, obsolete, current in candidates:
        for curie in with_partners(identifier):
            claimants[(prefix(curie), current)].add(curie)
    losers = set()
    for (_, current), curies in claimants.items():
        if len(curies) < 2:
            continue
        scientific_names = {n for n, classes in folded(current).items() if "scientific name" in classes}
        named = {curie for curie in curies if record_names.get(curie, set()) & scientific_names}
        winners = named if len(named) == 1 else set()
        losers |= {(curie, current) for curie in curies - winners}
    for name, index, identifier, obsolete, current in candidates:
        ambiguous = any((curie, current) in losers for curie in with_partners(identifier))
        decided[(name, index)] = DROPPED_MERGED_AMBIGUOUS if ambiguous else REMAPPED_MERGED

    for name, index, identifier, obsolete, current in remapped:
        decisions.append(
            {
                "concord": name,
                "identifier": identifier,
                "obsolete": obsolete,
                "current": current,
                "decision": decided[(name, index)],
            }
        )

    output = {}
    for name, rows in live.items():
        output[name] = []
        seen = set()
        for index, row in enumerate(rows):
            if decided.get((name, index), REMAPPED_MERGED) != REMAPPED_MERGED:
                continue
            new_row = tuple(merged.get(curie, curie) for curie in row)
            # Two merged IDs can be remapped to the same current ID, so dedupe after remapping.
            if new_row in seen:
                continue
            seen.add(new_row)
            output[name].append(new_row)
    return output, decisions


def update_obsolete_ncbitaxon_ids(concords, taxdump, label_files, synonym_files):
    """
    Write the taxon concords so that they only refer to current NCBITaxon IDs.

    MeSH and UMLS both cross-reference NCBI Taxonomy IDs that have since been merged into another taxon or
    deleted. Left alone, these become unlabeled NCBITaxon identifiers that compete with the current ID for
    the same MeSH or UMLS identifier (we only allow one of each prefix per clique), and whichever concord
    row glom() sees first wins. So we replace merged IDs with the ID they were merged into, and drop rows
    pointing at deleted IDs.

    Following a merge is not always right, and resolve_obsolete_ncbitaxon_ids() drops a remapped row when:

    - NCBI says the current taxon only includes the record: "Crustacea" (NCBITaxon:6657) was merged into
      NCBITaxon:197562 "Pancrustacea", which also contains insects, and Pancrustacea lists "Crustacea" as a
      name it "includes". Following the merge would make UMLS and MeSH "Crustacea" mean Pancrustacea.
    - Another record of the same prefix links to the current taxon directly. NCBI often merges two species
      names into one taxon while MeSH and UMLS keep a record for each, so a remapped row can point at a
      taxon another record already links to (MESH:C000668355 "Collybia dryophila" -> merged NCBITaxon:71877
      -> NCBITaxon:206318, which MESH:C000672803 "Gymnopus dryophilus" links to directly). Only one of them
      can join that clique, and the direct link is the better evidence. This is checked across both
      concords, since a MeSH record can link to a taxon through its UMLS CUI and vice versa.
    - Several records would reach the current taxon only through merged IDs. Unless exactly one of them is
      named after the taxon, we can't tell which is right, so none of them are linked to it.

    In each case, leaving both rows in would let concord row order decide which record joins the taxon.

    :param concords: A dict mapping each concord name (a key of TAXON_CONCORD_METADATA) to a tuple of
        (input concord file, output concord file).
    :param taxdump: taxdump.tar, from which merged.dmp, delnodes.dmp and names.dmp are read.
    :param label_files: Label files (CURIE\tlabel) for the MeSH and UMLS records in the concords.
    :param synonym_files: Synonym files (CURIE\tpredicate\tsynonym) for the same records.
    :return: A tuple (counts, decisions): `counts` maps each concord name to its counts for the concord
        metadata, and `decisions` lists what was decided for every row with an obsolete ID (see
        resolve_obsolete_ncbitaxon_ids()).
    """
    merged, deleted = ncbitaxon.read_obsolete_taxa(taxdump)
    rows = {name: list(read_concords(infile)) for name, (infile, _) in concords.items()}

    partners = partner_map(rows)
    obsolete_records = set()
    for concord_rows in rows.values():
        for row in concord_rows:
            link = ncbitaxon_link(row)
            if link and link[1] in merged:
                obsolete_records |= {link[0]} | partners[link[0]]
    record_names = read_record_names(obsolete_records, label_files, synonym_files)
    taxon_names = ncbitaxon.read_taxon_names(taxdump, set(merged.values()))

    output, decisions = resolve_obsolete_ncbitaxon_ids(rows, merged, deleted, record_names, taxon_names)

    counts = {}
    for name, (_, outfile) in concords.items():
        with open(outfile, "w") as outf:
            for row in output[name]:
                outf.write("\t".join(row) + "\n")
        decided = Counter(d["decision"] for d in decisions if d["concord"] == name)
        counts[name] = {
            "obsolete_ncbitaxon": {
                key: decided[key]
                for key in [
                    REMAPPED_MERGED,
                    DROPPED_MERGED_ALREADY_LINKED,
                    DROPPED_MERGED_INTO_BROADER_TAXON,
                    DROPPED_MERGED_SUPERSEDED_BY_DIRECT,
                    DROPPED_MERGED_AMBIGUOUS,
                    DROPPED_DELETED,
                ]
            }
        }
        logger.info(f"Updated obsolete NCBITaxon IDs in {outfile}: {counts[name]['obsolete_ncbitaxon']}")
    return counts, decisions


def write_taxon_concords(concords, taxdump, label_files, synonym_files):
    """
    Write the final taxon concords and their metadata from the raw concords.

    The raw concords come from build_taxon_umls_relationships() and build_relationships(); this replaces
    or drops their obsolete NCBITaxon IDs (update_obsolete_ncbitaxon_ids()) and records what it did in each
    concord's metadata YAML.

    :param concords: A dict mapping each concord name (a key of TAXON_CONCORD_METADATA) to a tuple of
        (raw concord file, output concord file, output metadata YAML).
    :param taxdump: taxdump.tar.
    :param label_files: Label files for the MeSH and UMLS records in the concords.
    :param synonym_files: Synonym files for the same records.
    """
    counts, _ = update_obsolete_ncbitaxon_ids(
        {name: (raw, outfile) for name, (raw, outfile, _) in concords.items()}, taxdump, label_files, synonym_files
    )
    for name, (_, outfile, metadata_yaml) in concords.items():
        write_concord_metadata(
            metadata_yaml, concord_filename=outfile, counts=counts[name], **TAXON_CONCORD_METADATA[name]
        )


def build_taxon_umls_relationships(mrconso, idfile, outfile):
    """
    Write the raw UMLS taxon concord: taxon CUIs linked to MeSH and NCBI Taxonomy through MRCONSO.

    The NCBITaxon IDs in it are as UMLS has them, including merged and deleted ones; write_taxon_concords()
    turns it into the concord the compendium is built from.

    :param mrconso: MRCONSO.RRF.
    :param idfile: The UMLS taxon IDs file (write_umls_ids()); CUIs not in it are skipped.
    :param outfile: The raw concord file to write.
    """
    # The keys are UMLS source abbreviations (the MRCONSO SAB column): NCBI Taxonomy is "NCBI" in UMLS, not "NCBITaxon".
    other_prefixes = {"MSH": MESH, "NCBI": NCBITAXON}
    umls.build_sets(mrconso, idfile, outfile, other_prefixes)


def build_relationships(outfile, mesh_ids):
    """
    Write the raw MeSH -> NCBI Taxonomy concord from the txid registry numbers in the MeSH registry.

    The NCBITaxon IDs in it are as MeSH has them, including merged and deleted ones; write_taxon_concords()
    turns it into the concord the compendium is built from.

    :param outfile: The raw concord file to write.
    :param mesh_ids: The MeSH taxon IDs file. Currently unused: every MeSH record with a txid registry
        number is written, whatever its tree.
    """
    regis = mesh.pull_mesh_registry()
    # with open(mesh_ids) as inf:
    # lines = inf.read().strip().split("\n")
    # all_mesh_taxa = set([x.split("\t")[0] for x in lines])
    with open(outfile, "w") as outf:
        for meshid, reg in regis:
            # The mesh->ncbi are in mesh as registration numbers that start with a "tx"
            if reg.startswith("txid"):
                ncbi_id = f"{NCBITAXON}:{reg[4:]}"
                outf.write(f"{meshid}\txref\t{ncbi_id}\n")
        # June 7, 2021.  We have previously found that not all mesh/ncbi links are in the mesh.nt
        # but as of today, it appears that they ARE all in there, so we are not hitting eutil any more (thank goodness)
        # left = list(all_mesh_taxa.difference( set([x[0] for x in regis]) ))
        # eutil.lookup(left)


def build_compendia(concordances, metadata_yamls, identifiers, icrdf_filename, mesh_ownership=None):
    """:concordances: a list of files from which to read relationships
    :identifiers: a list of files from which to read identifiers and optional categories
    :mesh_ownership: the umls_mesh_ownership rule's file; concord pairs naming a CUI another pipeline owns are
        skipped (umls.read_cuis_owned_elsewhere). None skips nothing."""
    owned_elsewhere = umls.read_cuis_owned_elsewhere(mesh_ownership, "taxon")
    dicts = {}
    types = {}
    unique_prefixes = unique_prefixes_from_config("taxon_unique_prefixes")
    for ifile in identifiers:
        print("loading", ifile)
        new_identifiers, new_types = read_identifier_file(ifile)
        glom(dicts, new_identifiers, unique_prefixes=unique_prefixes)
        types.update(new_types)
    for infile in concordances:
        print(infile)
        print("loading", infile)
        # Streamed straight into glom(), without holding the file's pairs: see read_concord_pairs().
        glom(
            dicts,
            umls.skip_pairs_owned_elsewhere(read_concord_pairs(infile), owned_elsewhere),
            unique_prefixes=unique_prefixes,
        )
    gene_sets = set([frozenset(x) for x in dicts.values()])
    baretype = ORGANISM_TAXON.split(":")[-1]
    # We need to use extra_prefixes since UMLS is not listed as an identifier prefix at
    # https://biolink.github.io/biolink-model/docs/OrganismTaxon.html
    write_compendium(metadata_yamls, gene_sets, f"{baretype}.txt", ORGANISM_TAXON, {}, icrdf_filename=icrdf_filename)
