from src.prefixes import RXCUI
from src.babel_utils import glom
from collections import defaultdict
import os,json

import logging
from src.util import LoggingUtil
logger = LoggingUtil.init_logging(__name__, level=logging.ERROR)

# RXNORM has lots of relationships.
# RXNREL contains both directions of each relationship, just to make the file bigger
# Here's the list:
#   54 reformulated_to
#   54 reformulation_of
#  132 entry_version_of
#  132 has_entry_version
#  255 has_sort_version
#  255 sort_version_of
# 1551 has_product_monograph_title
# 1551 product_monograph_title_of
# 1667 mapped_to
# 1668 mapped_from
# 1932 has_modification
# 1932 is_modification_of
# 2886 has_permuted_term
# 2886 permuted_term_of
# 3367 form_of
# 3367 has_form
# 5372 has_member
# 5372 member_of
# 5894 contained_in
# 5894 contains
# 5937 has_quantified_form
# 5937 quantified_form_of
# 6215 included_in
# 6215 includes
# 9112 basis_of_strength_substance_of
# 9112 has_basis_of_strength_substance
# 9112 has_precise_active_ingredient
# 9112 precise_active_ingredient_of
# 10389 has_part
# 10389 part_of
# 11323 has_precise_ingredient
# 11323 precise_ingredient_of
# 11562 has_ingredients
# 11562 ingredients_of
# 29427 has_print_name
# 29427 print_name_of
# 35466 doseformgroup_of
# 35466 has_doseformgroup
# 101449 has_tradename
# 101449 tradename_of
# 111137 consists_of
# 111137 constitutes
# 128330 dose_form_of
# 128330 has_dose_form
# 251454 inverse_isa
# 251454 isa
# 335789 has_ingredient
# 335789 ingredient_of
# 352829 active_moiety_of
# 352829 has_active_moiety
# 374599 active_ingredient_of
# 374599 has_active_ingredient
# 561937
# 1640618 has_inactive_ingredient
# 1640618 inactive_ingredient_of

# Note that there are a bunch that are blank
# There's a reasonable picture explaining a lot of these here:
# https://www.nlm.nih.gov/research/umls/rxnorm/RxNorm_Drug_Relationships.png

# We're going to choose one of the two directions for each relationship from that picture.
# We're going to ignore the others because they seem freaky - for instance reformulation seems to have
# a bunch (all?) where the subject is not in RXNCONSO anywhere...

useful_relationships = [
"has_form",
"has_precise_active_ingredient",
"has_precise_ingredient",
"has_tradename",
"consists_of",
"has_ingredient",
"has_active_ingredient"]

def get_aui_to_cui():
    """Get a mapping from AUI to CUI"""
    aui_to_cui = {}
    sdui_to_cui = defaultdict(set)
    consofile = os.path.join('input_data', 'private', "RXNCONSO.RRF")
    with open(consofile, 'r') as inf:
        for line in inf:
            x = line.strip().split('|')
            aui = x[7]
            cui = x[0]
            sdui = (x[11],x[7])
            if aui in aui_to_cui:
                print("What the all time fuck?")
                print(aui,cui)
                print(aui_to_cui[aui])
                exit()
            aui_to_cui[aui] = cui
            if sdui[1]=="":
                continue
            sdui_to_cui[sdui].add(cui)
    return aui_to_cui, sdui_to_cui

def get_cui(x,indicator_column,cui_column,aui_column,aui_to_cui,sdui_to_cui):
    relation_column = 7
    source_column = 10
    if x[relation_column] in useful_relationships:
        if x[indicator_column] == "CUI":
            return x[cui_column]
        elif x[indicator_column] == "AUI":
            return aui_to_cui[x[aui_column]]
        elif x[indicator_column] == "SDUI":
            cuis = sdui_to_cui[(x[source_column],x[aui_column])]
            if len(cuis) == 1:
                return list(cuis)[0]
            print("sdui garbage hell")
            print(x)
            print(cuis)
            exit()
        print("cmon man")
        print(x)
        exit()

def build_rxnorm_relationships(outfile):
    """RXNREL is a lousy file.
    The subject and object can sometimes be a CUI and sometimes an AUI and you have to use
    CONSO to figure out how to go back and forth.
    Some of them are using SDUIs are you joking?

    Another issue: there are things like this:
    RXCUI:214199	has_active_ingredient	RXCUI:435
    RXCUI:214199	has_active_ingredient	RXCUI:7213
    In this case, what we have is a single drug that has two active ingredients.
    We don't want to glom in this case, because it unifies the two ingredients at the conflation level,
    which leads to everything is everything.
    So we're going to need to collect has_active_ingredients as we go and only export ones that are singular

    What's more, the same thing happens with has_precise_active_ingredient, and maybe has_ingredient.
    Also, the same subject and object will have the more general term as well.  so both a has_precise_active_ingredient
    and a has_ingredient will be between the same set of subject and object.  Also there's consists of, which will hav
    similar issues. So, we're going to do a lot of catching here
    """
    aui_to_cui, sdui_to_cui = get_aui_to_cui()
    relfile = os.path.join('input_data', 'private', "RXNREL.RRF")
    single_use_relations = {"has_active_ingredient": defaultdict(list),
                            "has_precise_active_ingredient": defaultdict(list),
                            "has_precise_ingredient": defaultdict(list),
                            "has_ingredient": defaultdict(list),
                            "has_tradename": defaultdict(list),
                            "consists_of": defaultdict(list)}
    with open(relfile, 'r') as inf, open(outfile, 'w') as outf:
        for line in inf:
            x = line.strip().split('|')
            object = get_cui(x,2,0,1,aui_to_cui,sdui_to_cui)
            subject = get_cui(x,6,4,5,aui_to_cui,sdui_to_cui)
            if subject is not None:
                if subject == object:
                    continue
                predicate = x[7]
                if predicate in single_use_relations:
                    single_use_relations[predicate][subject].append(object)
                else:
                    outf.write(f"{RXCUI}:{subject}\t{predicate}\t{RXCUI}:{object}\n")
        for predicate in single_use_relations:
            for subject,objects in single_use_relations[predicate].items():
                if len(objects) > 1:
                    continue
                outf.write(f"{RXCUI}:{subject}\t{predicate}\t{RXCUI}:{objects[0]}\n")


def load_cliques(compendium):
    rx_to_clique = {}
    with open(compendium,"r") as infile:
        for line in infile:
            if RXCUI not in line:
                continue
            j = json.loads(line)
            clique = j["identifiers"][0]["i"]
            for terms in j["identifiers"]:
               if terms["i"].startswith(RXCUI):
                   rx_to_clique[terms["i"]] = clique
    return rx_to_clique

def build_conflation(rxn_concord,drug_compendium,chemical_compendia,outfilename):
    """RXN_concord contains relationshps between rxcuis that can be used to conflate
    Now we don't want all of them.  We want the ones that are between drugs and chemicals,
    and the ones between drugs and drugs.
    To determine which those are, we're going to have to dig around in all the compendia.
    We also want to get all the clique leaders as well.  For those, we only need to worry if there are RXCUIs
    in the clique."""
    print("load drugs")
    drug_rxcui_to_clique = load_cliques(drug_compendium)
    chemical_rxcui_to_clique = {}
    for chemical_compendium in chemical_compendia:
        if chemical_compendium == drug_compendium:
            continue
        print(f"load {chemical_compendium}")
        chemical_rxcui_to_clique.update(load_cliques(chemical_compendium))
    pairs = []
    print("load concord")
    with open(rxn_concord,"r") as infile:
        for line in infile:
            x = line.strip().split('\t')
            subject = x[0]
            object = x[2]
            if subject in drug_rxcui_to_clique and object in chemical_rxcui_to_clique:
                subject = drug_rxcui_to_clique[subject]
                object = chemical_rxcui_to_clique[object]
                pairs.append( (subject,object) )
            elif subject in chemical_rxcui_to_clique and object in drug_rxcui_to_clique:
                subject = chemical_rxcui_to_clique[subject]
                object = drug_rxcui_to_clique[object]
                pairs.append( (subject,object) )
            # OK, this is possible, and it's OK, as long as we get real clique leaders
            elif subject in drug_rxcui_to_clique and object in drug_rxcui_to_clique:
                subject = drug_rxcui_to_clique[subject]
                object = drug_rxcui_to_clique[object]
                pairs.append( (subject,object) )
            elif subject in chemical_rxcui_to_clique and object in chemical_rxcui_to_clique:
                subject = chemical_rxcui_to_clique[subject]
                object = chemical_rxcui_to_clique[object]
                pairs.append( (subject,object) )
    print("glom")
    gloms = {}
    glom(gloms,pairs)
    written = set()
    with open(outfilename,"w") as outfile:
        for clique_member,clique in gloms.items():
            if clique in written:
                continue
            outfile.write(f"{list(clique)}\n")

