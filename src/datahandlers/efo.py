import logging

import pyoxigraph

from src.babel_utils import parse_rdf_literal, pull_via_urllib
from src.metadata.provenance import write_concord_metadata
from src.prefixes import EFO, ORPHANET
from src.util import LoggingUtil, Text

logger = LoggingUtil.init_logging(__name__, level=logging.WARNING)


def pull_efo():
    _ = pull_via_urllib("http://www.ebi.ac.uk/efo/", "efo.owl", subpath="EFO", decompress=False)


class EFOgraph:
    """Load the mesh rdf file for querying"""

    def __init__(self, efo_owl_file_path):
        """There is a problem with enzyme.rdf.  As pulled from expasy, it includes this:

        <owl:Ontology rdf:about="">
        <owl:imports rdf:resource="http://purl.uniprot.org/core/"/>
        </owl:Ontology>

        That about='' really makes pyoxigraph annoyed. So we have to give it a base_iri on load, then its ok"""
        from datetime import datetime as dt

        logger.info(f"Loading EFO from {efo_owl_file_path}.")
        start = dt.now()
        self.m = pyoxigraph.Store()
        with open(efo_owl_file_path) as inf:
            self.m.bulk_load(input=inf, format=pyoxigraph.RdfFormat.RDF_XML, base_iri="http://example.org/")
        end = dt.now()
        logger.info(f"EFO loading complete in {end - start}.")

    def pull_EFO_labels_and_synonyms(self, lname, sname):
        with open(lname, "w") as labelfile, open(sname, "w") as synfile:
            # for labeltype in ['skos:prefLabel','skos:altLabel','rdfs:label']:
            for labeltype in ["skos:prefLabel", "skos:altLabel", "rdfs:label"]:
                s = f"""   PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

                        SELECT DISTINCT ?x ?label
                        WHERE {{ ?x {labeltype} ?label }}
                """
                qres = self.m.query(s)
                for row in list(qres):
                    iterm = str(row["x"])
                    label = parse_rdf_literal(str(row["label"]))
                    efoid = iterm[:-1].split("/")[-1]
                    if not efoid.startswith("EFO_"):
                        continue
                    efo_id = efoid.split("_")[-1]
                    synfile.write(f"{EFO}:{efo_id}\t{labeltype}\t{label}\n")
                    if not labeltype == "skos:altLabel":
                        labelfile.write(f"{EFO}:{efo_id}\t{label}\n")

    def pull_EFO_ids(self, roots, idfname):
        with open(idfname, "w") as idfile:
            for root, rtype in roots:
                s = f""" PREFIX EFO: <http://www.ebi.ac.uk/efo/EFO_>
                       PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

                       SELECT DISTINCT ?x
                       WHERE {{ ?x rdfs:subClassOf* {root} }}
                """
                qres = self.m.query(s)
                for row in list(qres):
                    iterm = str(row["x"])
                    efoid = iterm[:-1].split("/")[-1]
                    if efoid.startswith("EFO_"):
                        efo_id = efoid.split("_")[-1]
                        idfile.write(f"{EFO}:{efo_id}\t{rtype}\n")

    @staticmethod
    def _upper_prefixes(excluded_target_prefixes):
        """Upper-case a caller's prefix collection once, for comparison against upper-cased CURIE
        prefixes in _is_excluded_target(). Callers do this once per query rather than once per
        result row, and it lets a caller pass a lower-case constant (e.g. prefixes.ORPHANET, which
        is "orphanet") without it silently never matching."""
        return {prefix.upper() for prefix in excluded_target_prefixes}

    @staticmethod
    def _is_excluded_target(otherid, excluded_upper):
        """True if otherid should be dropped from a concord: either it's Orphanet (excluded
        unconditionally -- Orphanet xrefs/exactMatches out of EFO have proven unreliable, see the
        callers below) or its CURIE prefix is in ``excluded_upper``, the caller's already
        upper-cased excluded_target_prefixes (e.g. MP, passed by
        diseasephenotype.EFO_EXCLUDED_XREF_PREFIXES to keep MP disjoint from EFO -- see
        docs/sources/MP/disjointness.md). Orphanet is enforced here rather than via
        excluded_target_prefixes' default value so a caller that passes its own list (as
        diseasephenotype.py does) can't accidentally drop the Orphanet exclusion.

        ponytail: prefix compared with a raw split, not Text.get_prefix(), which raises on a
        colonless string -- otherid can be colonless here (see callers).
        """
        if otherid.upper().startswith(ORPHANET.upper()):
            return True
        return otherid.split(":", 1)[0].upper() in excluded_upper

    def get_exacts(self, iri, outfile, excluded_target_prefixes=()):
        query = f"""
         prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
         prefix UBERON: <http://purl.obolibrary.org/obo/UBERON_>
         prefix CL: <http://purl.obolibrary.org/obo/CL_>
         prefix GO: <http://purl.obolibrary.org/obo/GO_>
         prefix CHEBI: <http://purl.obolibrary.org/obo/CHEBI_>
         prefix MONDO: <http://purl.obolibrary.org/obo/MONDO_>
         prefix MONDOH: <http://purl.obolibrary.org/obo/mondo#>
         prefix HP: <http://purl.obolibrary.org/obo/HP_>
         prefix EFO: <http://www.ebi.ac.uk/efo/EFO_>
         prefix NCIT: <http://purl.obolibrary.org/obo/NCIT_>
         prefix SKOS: <http://www.w3.org/2004/02/skos/core#>
         prefix icd11.foundation: <http://id.who.int/icd/entity/>
         SELECT DISTINCT ?match
         WHERE {{
             {{ {iri} SKOS:exactMatch ?match. }}
             UNION
             {{ {iri} MONDOH:exactMatch ?match. }}
         }}
         """
        qres = self.m.query(query)
        excluded_upper = self._upper_prefixes(excluded_target_prefixes)
        nwrite = 0
        for row in list(qres):
            other = str(row["match"])
            try:
                otherid = Text.opt_to_curie(other[1:-1])
            except ValueError as verr:
                logger.error(f"Could not translate {other[1:-1]} into a CURIE, will be used as-is: {verr}")
                otherid = other[1:-1]

            if self._is_excluded_target(otherid, excluded_upper):
                logger.warning(f"Skipping excluded exactMatch '{otherid}' in EFOgraph.get_exacts({iri})")
                continue
            outfile.write(f"{iri}\tskos:exactMatch\t{otherid}\n")
            nwrite += 1
        return nwrite

    def get_xrefs(self, iri, outfile, excluded_target_prefixes=()):
        query = f"""
         prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
         prefix EFO: <http://www.ebi.ac.uk/efo/EFO_>
         prefix oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
         SELECT DISTINCT ?match
         WHERE {{
             {{ {iri} oboInOwl:hasDbXref ?match. }}
         }}
         """
        qres = self.m.query(query)
        excluded_upper = self._upper_prefixes(excluded_target_prefixes)
        for row in list(qres):
            other = str(row["match"])
            other_without_brackets = other[1:-1]
            try:
                other_id = Text.opt_to_curie(other_without_brackets)
            except ValueError as verr:
                logger.warning(
                    f"Could not translate '{other_without_brackets}' into a CURIE in "
                    + f"EFOgraph.get_xrefs({iri}), skipping: {verr}"
                )
                continue
            if self._is_excluded_target(other_id, excluded_upper):
                logger.warning(f"Skipping excluded xref '{other_id}' in EFOgraph.get_xrefs({iri})")
                continue
            # EFO occasionally has xrefs that are just strings, not IRIs or CURIEs
            if ":" in other_id and not other_id.startswith(":"):
                outfile.write(f"{iri}\toboInOwl:hasDbXref\t{other_id}\n")
            else:
                logger.warning(
                    f"Skipping xref '{other_without_brackets}' in EFOgraph.get_xrefs({iri}): " + "not a valid CURIE"
                )


def make_labels(owlfile, labelfile, synfile):
    m = EFOgraph(owlfile)
    m.pull_EFO_labels_and_synonyms(labelfile, synfile)


def make_ids(roots, owlfile, idfname):
    m = EFOgraph(owlfile)
    m.pull_EFO_ids(roots, idfname)


def make_concords(owlfile, idfilename, outfilename, provenance_metadata=None, excluded_target_prefixes=()):
    """Given a list of identifiers, find out all of the equivalent identifiers from the owl.

    :param excluded_target_prefixes: xref/exactMatch targets whose CURIE prefix is in this
        collection are dropped. The disease/phenotype build passes ``[MP]`` here so EFO's
        (untrusted) direct xrefs to Mammalian Phenotype terms never enter the concord — see
        diseasephenotype.EFO_EXCLUDED_XREF_PREFIXES and docs/sources/MP/disjointness.md.
    """
    m = EFOgraph(owlfile)
    with open(idfilename) as inf, open(outfilename, "w") as concfile:
        for line in inf:
            efo_id = line.split("\t")[0]
            nexacts = m.get_exacts(efo_id, concfile, excluded_target_prefixes=excluded_target_prefixes)
            if nexacts == 0:
                m.get_xrefs(efo_id, concfile, excluded_target_prefixes=excluded_target_prefixes)

    if provenance_metadata is not None:
        excluded_note = (
            f" Xref targets with these prefixes were excluded: {sorted(excluded_target_prefixes)}."
            if excluded_target_prefixes
            else ""
        )
        write_concord_metadata(
            provenance_metadata,
            name="Experimental Factor Ontology (EFO) cross-references",
            description=f"Cross-references from the Experimental Factor Ontology (EFO) for the EFO IDs in {idfilename}.{excluded_note}",
            sources=[
                {
                    "name": "Experimental Factor Ontology",
                    "url": "http://www.ebi.ac.uk/efo/efo.owl",
                }
            ],
            concord_filename=outfilename,
        )
