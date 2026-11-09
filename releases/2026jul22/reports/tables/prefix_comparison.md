# Prefix comparison: 2026jul15 vs 2025sep1

Compared release `2026jul15` against baseline `2025sep1` (`releases/prefix_reports/2025sep1.json`). One or more releases may have been skipped between them; this report always compares against the `previous_release` pinned in `config.yaml`.

CURIE occurrence counts are exact; clique counts (and any distinct counts) are approximate (HyperLogLog, ~2% error), so treat small clique-count changes as noise.

## Overall changes

| Metric | Previous | Current | Absolute change | Percent change |
| --- | ---: | ---: | ---: | ---: |
| All CURIEs | 688,983,999 | 605,864,191 | -83,119,808 | -12.1% |
| All cliques (approx) | 490,293,340 | 388,490,111 | -101,803,229 | -20.8% |
| AnatomicalEntity CURIEs | 249,584 | 252,287 | +2,703 | +1.1% |
| BiologicalProcess CURIEs | 67,929 | 65,256 | -2,673 | -3.9% |
| Cell CURIEs | 13,175 | 13,952 | +777 | +5.9% |
| CellLine CURIEs | 38,810 | 38,896 | +86 | +0.2% |
| CellularComponent CURIEs | 14,696 | 14,818 | +122 | +0.8% |
| ChemicalEntity CURIEs | 4,046,131 | 518,554 | -3,527,577 | -87.2% |
| ChemicalMixture CURIEs | 530 | 609 | +79 | +14.9% |
| ComplexMolecularMixture CURIEs | 276 | 1,470 | +1,194 | +432.6% |
| Disease CURIEs | 632,330 | 639,398 | +7,068 | +1.1% |
| Drug CURIEs | 360,925 | 358,459 | -2,466 | -0.7% |
| Food CURIEs | 0 | 932 | +932 | NEW |
| Gene CURIEs | 79,427,652 | 88,740,328 | +9,312,676 | +11.7% |
| GeneFamily CURIEs | 28,050 | 28,463 | +413 | +1.5% |
| GrossAnatomicalStructure CURIEs | 15,709 | 25,867 | +10,158 | +64.7% |
| MacromolecularComplex CURIEs | 1,258 | 20,579 | +19,321 | +1535.9% |
| MolecularActivity CURIEs | 206,636 | 213,714 | +7,078 | +3.4% |
| MolecularMixture CURIEs | 21,879,355 | 23,892,388 | +2,013,033 | +9.2% |
| OrganismTaxon CURIEs | 3,543,867 | 3,745,133 | +201,266 | +5.7% |
| Pathway CURIEs | 53,125 | 53,772 | +647 | +1.2% |
| PhenotypicFeature CURIEs | 483,108 | 103,707 | -379,401 | -78.5% |
| Polypeptide CURIEs | 166 | 5 | -161 | -97.0% |
| Protein CURIEs | 275,514,857 | 170,218,499 | -105,296,358 | -38.2% |
| Publication CURIEs | 79,773,973 | 83,969,833 | +4,195,860 | +5.3% |
| SmallMolecule CURIEs | 221,734,011 | 231,673,258 | +9,939,247 | +4.5% |
| umls CURIEs | 897,846 | 1,274,014 | +376,168 | +41.9% |

## Notable changes

Rows removed entirely, or with an absolute change >= 100,000 or a percentage change >= 25%, largest absolute change first.

- 103,824,844 fewer UniProtKB identifiers in Protein cliques led by UniProtKB (-103,824,844, -40.9%)
- 8,235,629 more NCBIGene identifiers in Gene cliques led by NCBIGene (+8,235,629, +13.3%)
- 7,399,934 more INCHIKEY identifiers in SmallMolecule cliques led by PUBCHEM.COMPOUND (+7,399,934, +7.1%)
- 2,928,753 fewer ENSEMBL identifiers in Protein cliques led by UniProtKB (-2,928,753, -14.9%)
- 1,769,205 more INCHIKEY identifiers in MolecularMixture cliques led by PUBCHEM.COMPOUND (+1,769,205, +18.0%)
- 1,654,118 more PMID identifiers in Publication cliques led by PMID (+1,654,118, +4.2%)
- 1,639,442 more doi identifiers in Publication cliques led by PMID (+1,639,442, +5.4%)
- 1,633,321 fewer PUBCHEM.COMPOUND identifiers in ChemicalEntity cliques led by PUBCHEM.COMPOUND (-1,633,321, -99.1%)
- 1,631,194 fewer INCHIKEY identifiers in ChemicalEntity cliques led by PUBCHEM.COMPOUND (-1,631,194, -99.1%)
- 1,531,140 more PUBCHEM.COMPOUND identifiers in SmallMolecule cliques led by PUBCHEM.COMPOUND (+1,531,140, +1.4%)
- 1,438,821 more ENSEMBL identifiers in Protein cliques led by ENSEMBL (+1,438,821, +89.1%)
- 902,300 more PMC identifiers in Publication cliques led by PMID (+902,300, +8.7%)
- 537,947 more MGI identifiers in Gene cliques led by MGI (+537,947, +1351.7%)
- 416,316 more CHEMBL.COMPOUND identifiers in SmallMolecule cliques led by PUBCHEM.COMPOUND (+416,316, +19.1%)
- 387,028 more ENSEMBL identifiers in Gene cliques led by NCBIGene (+387,028, +2.9%)
- 376,168 more UMLS identifiers in umls cliques led by UMLS (+376,168, +41.9%)
- 313,521 fewer UMLS identifiers in PhenotypicFeature cliques led by UMLS (-313,521, -95.5%)
- 302,169 more CAS identifiers in SmallMolecule cliques led by PUBCHEM.COMPOUND (+302,169, +8.2%)
- 196,697 more PUBCHEM.COMPOUND identifiers in MolecularMixture cliques led by PUBCHEM.COMPOUND (+196,697, +1.7%)
- 167,711 more NCBITaxon identifiers in OrganismTaxon cliques led by NCBITaxon (+167,711, +6.2%)
- 96,557 fewer INCHIKEY identifiers in ChemicalEntity cliques led by CHEMBL.COMPOUND (-96,557, -74.9%)
- 90,877 more CHEMBL.COMPOUND identifiers in SmallMolecule cliques led by CHEMBL.COMPOUND (+90,877, +13443.3%)
- 90,059 more INCHIKEY identifiers in SmallMolecule cliques led by CHEMBL.COMPOUND (+90,059, +13624.7%)
- 83,625 fewer MESH identifiers in ChemicalEntity cliques led by MESH (-83,625, -49.6%)
- 79,779 fewer CHEMBL.COMPOUND identifiers in ChemicalEntity cliques led by CHEMBL.COMPOUND (-79,779, -59.3%)
- 41,291 fewer SNOMEDCT identifiers in PhenotypicFeature cliques led by UMLS (-41,291, -94.7%)
- 34,081 more CAS identifiers in SmallMolecule cliques led by UNII (+34,081, +58.8%)
- 30,662 fewer UNII identifiers in ChemicalEntity cliques led by UNII (-30,662, -56.1%)
- 27,474 more PUBCHEM.COMPOUND identifiers in SmallMolecule cliques led by UNII (+27,474, +56.1%)
- 27,143 more INCHIKEY identifiers in SmallMolecule cliques led by UNII (+27,143, +56.2%)
- 27,132 more UNII identifiers in SmallMolecule cliques led by UNII (+27,132, +56.1%)
- 19,321 more ComplexPortal identifiers in MacromolecularComplex cliques led by ComplexPortal (+19,321, +1535.9%)
- 19,172 fewer UMLS identifiers in PhenotypicFeature cliques led by NCIT (-19,172, -98.3%)
- 17,567 more CHEBI identifiers in ChemicalEntity cliques led by CHEBI (+17,567, +152.4%)
- 14,212 fewer MEDDRA identifiers in PhenotypicFeature cliques led by UMLS (-14,212, -86.0%)
- 6,491 more PUBCHEM.COMPOUND identifiers in MolecularMixture cliques led by UNII (+6,491, +33.7%)
- 6,188 more INCHIKEY identifiers in ChemicalEntity cliques led by CHEBI (+6,188, +3363.0%)
- 5,646 more CHEMBL.COMPOUND identifiers in SmallMolecule cliques led by UNII (+5,646, +37.1%)
- 5,216 more CAS identifiers in MolecularMixture cliques led by UNII (+5,216, +30.8%)
- 4,472 more INCHIKEY identifiers in MolecularMixture cliques led by UNII (+4,472, +30.0%)
- 4,468 more UNII identifiers in MolecularMixture cliques led by UNII (+4,468, +30.0%)
- 4,386 more RXCUI identifiers in ChemicalEntity cliques led by UMLS (+4,386, +44.0%)
- 4,056 removed icd11.foundation identifiers in Disease cliques led by MONDO (-4,056, -100.0%)
- 3,592 more CHEMBL.COMPOUND identifiers in MolecularMixture cliques led by CHEMBL.COMPOUND (+3,592, +5131.4%)
- 3,561 more INCHIKEY identifiers in MolecularMixture cliques led by CHEMBL.COMPOUND (+3,561, +5314.9%)
- 2,455 fewer CAS identifiers in ChemicalEntity cliques led by MESH (-2,455, -36.1%)
- 2,233 more GTOPDB identifiers in SmallMolecule cliques led by PUBCHEM.COMPOUND (+2,233, +45.8%)
- 2,055 more DRUGBANK identifiers in SmallMolecule cliques led by UNII (+2,055, +79.3%)
- 1,590 fewer MEDDRA identifiers in PhenotypicFeature cliques led by HP (-1,590, -29.9%)
- 1,515 removed CAS identifiers in ChemicalEntity cliques led by PUBCHEM.COMPOUND (-1,515, -100.0%)

...and 91 more (see the CSV).

## Full detail

- `prefix_comparison_overall.csv`
- `prefix_comparison_by_clique_prefix.csv`
