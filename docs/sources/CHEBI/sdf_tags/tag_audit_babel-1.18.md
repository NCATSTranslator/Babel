# ChEBI SDF tag audit

Source file: `data/babel-1.18/babel_downloads/CHEBI/ChEBI_complete.sdf`

## Keys requested by make_chebi_relations()

| Requested key | Present? | Tag in SDF | Entries |
| --- | --- | --- | --- |
| `chebiid` | yes | `> <ChEBI ID>` | 199342 |
| `chebiname` | yes | `> <ChEBI NAME>` | 199342 |
| `inchikey` | yes | `> <INCHIKEY>` | 187896 |
| `keggcompounddatabaselinks` | yes | `> <KEGG COMPOUND Database Links>` | 16196 |
| `pubchemcompounddatabaselinks` | yes | `> <PubChem Compound Database Links>` | 180991 |
| `secondary_id` | yes | `> <SECONDARY_ID>` | 6905 |
| `smiles` | yes | `> <SMILES>` | 199308 |

## All tags present in the SDF

| Tag | Normalized key | Entries | Requested? |
| --- | --- | --- | --- |
| `> <ChEBI ID>` | `chebiid` | 199342 | yes |
| `> <ChEBI NAME>` | `chebiname` | 199342 | yes |
| `> <STAR>` | `star` | 199342 |  |
| `> <SMILES>` | `smiles` | 199308 | yes |
| `> <FORMULA>` | `formula` | 199238 |  |
| `> <MONOISOTOPIC_MASS>` | `monoisotopic_mass` | 199117 |  |
| `> <MASS>` | `mass` | 199110 |  |
| `> <PubChem Substance Database Links>` | `pubchemsubstancedatabaselinks` | 191573 |  |
| `> <INCHI>` | `inchi` | 187896 |  |
| `> <INCHIKEY>` | `inchikey` | 187896 | yes |
| `> <PubChem Compound Database Links>` | `pubchemcompounddatabaselinks` | 180991 | yes |
| `> <IUPAC_NAME>` | `iupac_name` | 113390 |  |
| `> <SYNONYM>` | `synonym` | 76729 |  |
| `> <MetaboLights Database Links>` | `metabolightsdatabaselinks` | 56409 |  |
| `> <ChemSpider Database Links>` | `chemspiderdatabaselinks` | 53184 |  |
| `> <DEFINITION>` | `definition` | 48330 |  |
| `> <LINCS Database Links>` | `lincsdatabaselinks` | 41330 |  |
| `> <SureChEMBL Database Links>` | `surechembldatabaselinks` | 38468 |  |
| `> <PubMed Database Links>` | `pubmeddatabaselinks` | 36579 |  |
| `> <ChEMBL Database Links>` | `chembldatabaselinks` | 35939 |  |
| `> <CAS Registry Numbers>` | `casregistrynumbers` | 29009 |  |
| `> <CompTox Database Links>` | `comptoxdatabaselinks` | 22556 |  |
| `> <NMRShiftDB Database Links>` | `nmrshiftdbdatabaselinks` | 22103 |  |
| `> <HMDB Database Links>` | `hmdbdatabaselinks` | 19699 |  |
| `> <BKMS-react Database Links>` | `bkms-reactdatabaselinks` | 17684 |  |
| `> <BRENDA Ligand Database Links>` | `brendaliganddatabaselinks` | 17684 |  |
| `> <Reaxys Registry Numbers>` | `reaxysregistrynumbers` | 17296 |  |
| `> <KEGG COMPOUND Database Links>` | `keggcompounddatabaselinks` | 16196 | yes |
| `> <CHARGE>` | `charge` | 15868 |  |
| `> <BRENDA Database Links>` | `brendadatabaselinks` | 14499 |  |
| `> <LIPID MAPS Database Links>` | `lipidmapsdatabaselinks` | 12638 |  |
| `> <BindingDB Database Links>` | `bindingdbdatabaselinks` | 12336 |  |
| `> <Rhea Database Links>` | `rheadatabaselinks` | 11603 |  |
| `> <WURCS>` | `wurcs` | 11431 |  |
| `> <GlyTouCan Database Links>` | `glytoucandatabaselinks` | 10485 |  |
| `> <GlyGen Database Links>` | `glygendatabaselinks` | 9786 |  |
| `> <UniProt Database Links>` | `uniprotdatabaselinks` | 9389 |  |
| `> <MetaCyc Database Links>` | `metacycdatabaselinks` | 7131 |  |
| `> <SECONDARY_ID>` | `secondary_id` | 6905 | yes |
| `> <SABIO-RK Database Links>` | `sabio-rkdatabaselinks` | 6486 |  |
| `> <Patent Database Links>` | `patentdatabaselinks` | 5967 |  |
| `> <PDB Database Links>` | `pdbdatabaselinks` | 5958 |  |
| `> <Wikipedia Database Links>` | `wikipediadatabaselinks` | 5538 |  |
| `> <Beilstein Registry Numbers>` | `beilsteinregistrynumbers` | 5489 |  |
| `> <GeneOntology Database Links>` | `geneontologydatabaselinks` | 5080 |  |
| `> <KNApSAcK Database Links>` | `knapsackdatabaselinks` | 4884 |  |
| `> <SwissLipids Database Links>` | `swisslipidsdatabaselinks` | 4853 |  |
| `> <KEGG DRUG Database Links>` | `keggdrugdatabaselinks` | 4290 |  |
| `> <PDBeChem Database Links>` | `pdbechemdatabaselinks` | 3801 |  |
| `> <DrugCentral Database Links>` | `drugcentraldatabaselinks` | 3761 |  |
| `> <DrugBank Database Links>` | `drugbankdatabaselinks` | 3499 |  |
| `> <Gmelin Registry Numbers>` | `gmelinregistrynumbers` | 3312 |  |
| `> <Reactome Database Links>` | `reactomedatabaselinks` | 2803 |  |
| `> <Virtual Metabolic Human Database Links>` | `virtualmetabolichumandatabaselinks` | 1258 |  |
| `> <PPDB Database Links>` | `ppdbdatabaselinks` | 1115 |  |
| `> <KEGG GLYCAN Database Links>` | `keggglycandatabaselinks` | 799 |  |
| `> <Agricola Database Links>` | `agricoladatabaselinks` | 735 |  |
| `> <BioModels Database Links>` | `biomodelsdatabaselinks` | 722 |  |
| `> <Golm Database Links>` | `golmdatabaselinks` | 687 |  |
| `> <FooDB Database Links>` | `foodbdatabaselinks` | 679 |  |
| `> <UM-BBD Database Links>` | `um-bbddatabaselinks` | 620 |  |
| `> <IEDB Database Links>` | `iedbdatabaselinks` | 609 |  |
| `> <Alan Wood's Pesticides Database Links>` | `alanwood'spesticidesdatabaselinks` | 530 |  |
| `> <Expression Atlas Database Links>` | `expressionatlasdatabaselinks` | 473 |  |
| `> <MolBase Database Links>` | `molbasedatabaselinks` | 290 |  |
| `> <VSDB Database Links>` | `vsdbdatabaselinks` | 248 |  |
| `> <MassBank Database Links>` | `massbankdatabaselinks` | 232 |  |
| `> <Carotenoids Database Database Links>` | `carotenoidsdatabasedatabaselinks` | 226 |  |
| `> <PubMed Central Database Links>` | `pubmedcentraldatabaselinks` | 195 |  |
| `> <SMID Database Links>` | `smiddatabaselinks` | 150 |  |
| `> <Chinese Abstracts Database Links>` | `chineseabstractsdatabaselinks` | 111 |  |
| `> <WebElements Database Links>` | `webelementsdatabaselinks` | 111 |  |
| `> <YMDB Database Links>` | `ymdbdatabaselinks` | 102 |  |
| `> <ECMDB Database Links>` | `ecmdbdatabaselinks` | 98 |  |
| `> <RESID Database Links>` | `residdatabaselinks` | 95 |  |
| `> <BPDB Database Links>` | `bpdbdatabaselinks` | 92 |  |
| `> <The Signaling Pathways Project Database Links>` | `thesignalingpathwaysprojectdatabaselinks` | 68 |  |
| `> <IntAct Database Links>` | `intactdatabaselinks` | 37 |  |
| `> <ChemIDplus Database Links>` | `chemidplusdatabaselinks` | 34 |  |
| `> <LIPID MAPS class Database Links>` | `lipidmapsclassdatabaselinks` | 11 |  |
| `> <CiteXplore Database Links>` | `citexploredatabaselinks` | 3 |  |
| `> <DrugBank Metabolite Database Links>` | `drugbankmetabolitedatabaselinks` | 3 |  |
| `> <DrugBank Salts Database Links>` | `drugbanksaltsdatabaselinks` | 2 |  |
| `> <PPR Database Links>` | `pprdatabaselinks` | 2 |  |
| `> <CAS Database Links>` | `casdatabaselinks` | 2 |  |
| `> <FAO/WHO standards Database Links>` | `fao/whostandardsdatabaselinks` | 1 |  |

All 7 requested keys are present in this SDF.
