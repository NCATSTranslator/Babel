# NCBITaxon

NCBI Taxonomy is the backbone of the `OrganismTaxon` compendium (`src/createcompendia/taxon.py`).
Its identifiers come from the `names.dmp` in `taxdump.tar` (`src/datahandlers/ncbitaxon.py`), and
two other sources link to it:

- **MeSH**, through registry numbers of the form `txid<N>` (the `NCBI_MESH` concord).
- **UMLS**, through NCBI atoms in MRCONSO (the `UMLS` concord, which also links UMLS to MeSH).

NCBITaxon, MESH and UMLS are all unique prefixes in `glom()`, so a taxon clique holds at most one of
each. A bad link therefore never grows a large clique. It shows up instead as an identifier that
loses, or swaps, its NCBITaxon partner. That is what the checks in
[`umls-and-obsolete-ids/`](./umls-and-obsolete-ids/) measure.

## UMLS calls NCBI Taxonomy "NCBI"

`umls.build_sets()` matches on the MRCONSO source abbreviation (SAB). For NCBI Taxonomy that is
`NCBI`, and the CODE column is the bare taxon ID. Until this was fixed, the taxon pipeline asked for
`NCBITaxon`, which matched nothing. The UMLS concord held only UMLS → MeSH links, and roughly
745,000 UMLS taxa shipped as single-identifier cliques beside their NCBITaxon twins. For example,
[`NCBITaxon:3704`](http://purl.obolibrary.org/obo/NCBITaxon_3704) "Armoracia rusticana" and
`UMLS:C1110641` "Armoracia rusticana" were separate cliques.

## Merged and deleted taxon IDs

NCBI regularly merges taxa (often two species names found to be one species) and deletes others,
recording these in `merged.dmp` and `delnodes.dmp`. MeSH and UMLS lag behind and still cite the old
IDs: 1,874 merged and 36 deleted IDs reached the compendium before this was handled, each as an
unlabeled NCBITaxon identifier.

`get_taxon_umls_relationships` and `get_taxon_relationships` write the concords as their sources
have them, into `taxon/raw_concords/`. Rule `taxon_update_obsolete_ncbitaxon_ids` then runs
`taxon.update_obsolete_ncbitaxon_ids()` over both at once. They have to be finished together,
because a MeSH record can reach a taxon through its UMLS CUI and the other way around. Each row
citing an obsolete ID gets one of these outcomes, checked in this order:

- **Rows with deleted IDs are dropped.** There is no current taxon to point at.
- **A merged ID the record already reaches directly is dropped.** It adds nothing. This is common
  for MeSH: 609 MeSH rows cite a merged ID while the record's UMLS CUI cites the current one.
- **A merge into a broader taxon is not followed.** NCBI's `names.dmp` gives every name a class, and
  when it merges a taxon into a broader one it usually keeps the old name under the new taxon as
  `includes` (or `in-part`). If any of the record's names (its MeSH label, or its UMLS label and
  synonyms) has one of those classes under the merge target, the row is dropped. Example: UMLS and
  MeSH "Crustacea" cite `NCBITaxon:6657`, which NCBI merged into
  [`NCBITaxon:197562`](http://purl.obolibrary.org/obo/NCBITaxon_197562) "Pancrustacea". That taxon
  also contains the insects, and it lists "Crustacea" as a name it includes. Most of the others are
  subspecies merged into their species, or sections and subgenera merged into their genus. A record
  is dropped even if another of its names is a synonym of the target. UMLS "Emex" is also called
  "Rumex subgen. Emex", and NCBI lists "Emex" as a synonym of
  [`NCBITaxon:3618`](http://purl.obolibrary.org/obo/NCBITaxon_3618) "Rumex" only because the genus
  was sunk into it.
- **A merged ID loses to a direct link.** When NCBI merges two names, MeSH and UMLS usually keep a
  record for each, so after remapping both records point at the same taxon and only one can join it.
  If another record of the same prefix already reaches that taxon directly, the remapped row is
  dropped. "Reaches" includes going through its partner in the other concord. Example: MeSH registry
  `MESH:C000668355` "Collybia dryophila" → merged `NCBITaxon:71877` →
  [`NCBITaxon:206318`](http://purl.obolibrary.org/obo/NCBITaxon_206318) "Gymnopus dryophilus", which
  `MESH:C000672803` "Gymnopus dryophilus" links to directly. Without this rule the choice fell to
  row order, and a full build lost 1,329 correct direct links.
- **Competing merged IDs are dropped unless one record is named after the taxon.** When several
  records of one prefix still reach a taxon only through merged IDs, the record whose label or
  synonym is the taxon's scientific name keeps its link. If no single record is, none of them do.
  Most such taxa are several species or genera lumped into one (UMLS "Eucarida" and "Syncarida" into
  "Stomatocarida"), where no record is the whole taxon.
- **Otherwise, the merged ID is replaced** with the ID it was merged into
  (`ncbitaxon.read_obsolete_taxa()`, which fails if NCBI ever stops flattening merge chains).

None of these outcomes depend on concord row order. Counts of each are recorded under
`obsolete_ncbitaxon` in the concord metadata YAMLs. They are tabulated, with every broader-taxon and
competing-ID drop, in
[`obsolete-id-decisions.md`](./umls-and-obsolete-ids/obsolete-id-decisions.md). In the 2026-11-17
local build, the UMLS concord replaces 992 merged IDs and drops 976 superseded, 40 broader and 24
competing rows; the MeSH concord replaces 54 and drops 1,231 superseded, 609 already linked, 14
broader and 2 competing ones.

## Effect on the compendium

Measured by building `taxon` locally on main (`bb882867`) and on this change merged with it
(`37e01618`), from the same downloads (UMLS 2026AA; MeSH `mesh.nt` and the NCBI taxdump downloaded
2026-11-17) and the same upstream ids files, so the comparison isolates this change. Artifacts are
in
[`umls-and-obsolete-ids/`](./umls-and-obsolete-ids/).

- **Cliques:** 3,785,393 → 3,072,393 (`clique-diff.summary.json`). Almost all of the difference is
  UMLS-only cliques joining NCBITaxon cliques. UMLS-only cliques went from 745,560 to 33,189
  ([`clique-shapes.md`](./umls-and-obsolete-ids/clique-shapes.md)).
- **No clique holds two identifiers with the same prefix.** The largest clique is still three
  identifiers.
- **Dropped identifiers:** 1,947. These are the 1,910 merged and 36 deleted NCBITaxon IDs, plus
  `MESH:C000731772`, which is no longer in MeSH and only reached the build through UMLS: its CUI now
  joins [`NCBITaxon:1193015`](http://purl.obolibrary.org/obo/NCBITaxon_1193015) "Westerdykella
  aurantiaca" together with the current MeSH record for that species.
- **Partner changes** ([`partner-changes.md`](./umls-and-obsolete-ids/partner-changes.md)): 712,486
  UMLS identifiers gained an NCBITaxon partner, and 1,204 MeSH/UMLS identifiers had an obsolete
  partner replaced by the current one. 86 UMLS identifiers lost or swapped a current partner. Almost
  all of these are a second CUI for the same organism, reaching NCBITaxon only through its MeSH
  heading, giving way to the CUI that carries NCBI's own atom: a MeSH-spelled species name
  (`UMLS:C5434345` "Colletotrichum caudasporum" vs `UMLS:C3747940` "Colletotrichum caudisporum"),
  or an extract or food ("Garlic", "Betula alba extract") versus the organism itself.
- **Labels** ([`clique-shapes.md`](./umls-and-obsolete-ids/clique-shapes.md)): of the 780,474
  cliques holding both an NCBITaxon and a UMLS identifier, 721,650 have the same label on both. Of
  the other 58,824, 48,981 have the UMLS label among NCBITaxon's own synonyms (usually an older
  name). A sample of the rest is mostly UMLS formatting ("Genus Moschus", "Stevia <Eupatorieae>").

## Known remaining disagreements

47 UMLS CUIs reach one NCBITaxon directly and a different one through their MeSH heading
([`path-disagreements.md`](./umls-and-obsolete-ids/path-disagreements.md)). Only one link can win.
In the sample the direct link is more often right (`UMLS:C0993566` "Daboia" directly reaches the
genus, while MeSH's registry number points at the species *Daboia russelii*), but not always: MeSH
lists Oncothecales as an entry term of Magnoliopsida, and UMLS attached NCBI's Oncothecales atom to
its Magnoliopsida CUI. These are left to `glom()` and listed rather than handled by another rule.

Some separate-looking pairs are correct as they are. MeSH "Plants" (`MESH:D010944`) is linked by
UMLS to Viridiplantae, not to [`NCBITaxon:3193`](http://purl.obolibrary.org/obo/NCBITaxon_3193)
"Embryophyta". `UMLS:C0591833` "Murine" is the eye-drop brand, not
[`NCBITaxon:39107`](http://purl.obolibrary.org/obo/NCBITaxon_39107) "Murinae". Others, such as
`UMLS:C1704307` "Fly (organism)" (SNOMED CT only), have no source link to NCBI Taxonomy at all.

## Regenerating

Build both sides of the comparison, then run `partner_changes.py`, `path_disagreements.py` and
`clique_shapes.py` in
[`umls-and-obsolete-ids/scripts/`](./umls-and-obsolete-ids/scripts/) (usage is in each docstring)
and `babel-clique-diff` (see [`docs/tools/CliqueDiff.md`](../../tools/CliqueDiff.md)).
`obsolete_id_decisions.py` needs only the inputs of rule `taxon_update_obsolete_ncbitaxon_ids`.
`tests/pipeline/test_taxon.py` checks three invariants over a real build: the UMLS concord links to
NCBITaxon, every NCBITaxon ID in the taxon concords is current, and neither "Crustacea" is linked
to Pancrustacea.
