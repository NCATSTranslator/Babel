# Canonical RDF predicate URI constants. Keeps full predicate strings in one place
# so that synonym/label TSV files use consistent values.
#
# SPARQL PREFIX declarations inside query strings are left as inline literals
# since the SPARQL syntax requires it and they don't benefit from centralisation.

# oboInOwl predicates
OBO_IN_OWL = "http://www.geneontology.org/formats/oboInOwl#"
HAS_EXACT_SYNONYM = OBO_IN_OWL + "hasExactSynonym"
HAS_RELATED_SYNONYM = OBO_IN_OWL + "hasRelatedSynonym"
HAS_ALTERNATIVE_ID = OBO_IN_OWL + "hasAlternativeId"
HAS_DB_XREF = OBO_IN_OWL + "hasDbXref"
HAS_SYNONYM = OBO_IN_OWL + "hasSynonym"
OBO_ID = OBO_IN_OWL + "id"

# SKOS predicates
SKOS = "http://www.w3.org/2004/02/skos/core#"
EXACT_MATCH = SKOS + "exactMatch"
CLOSE_MATCH = SKOS + "closeMatch"
ALT_LABEL = SKOS + "altLabel"
PREF_LABEL = SKOS + "prefLabel"

# RDF predicates
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

# RDFS predicates
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
RDFS_LABEL = RDFS + "label"
RDFS_SUBCLASSOF = RDFS + "subClassOf"

# OWL predicates
OWL = "http://www.w3.org/2002/07/owl#"
OWL_EQUIVALENT_CLASS = OWL + "equivalentClass"
OWL_CLASS = OWL + "Class"
OWL_ONTOLOGY = OWL + "Ontology"
