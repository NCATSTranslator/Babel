from src.prefixes import WORMBASE
from src.babel_utils import pull_via_urllib
import json
import os

mods = ['WB', 'FB', 'ZFIN', 'MGI', 'RGD', 'SGD']
modmap = { x:x for x in mods }
modmap['WB']= WORMBASE

def pull_mods():
    for mod in mods:
        subp = modmap[mod]

        # We get the downloads from https://www.alliancegenome.org/downloads#gene-descriptions.
        # They are also available at:
        # - https://download.alliancegenome.org/8.1.0/GENE-DESCRIPTION-JSON/SGD/GENE-DESCRIPTION-JSON_SGD_9.json.gz
        # - origname = pull_via_urllib(f"https://download.alliancegenome.org/8.1.0/GENE-DESCRIPTION-JSON/{mod}/",f'GENE-DESCRIPTION-JSON_{mod}_9.json.gz', subpath=subp)
        #
        # However, the following URL returns the latest version of this file for each model organism.
        origname = pull_via_urllib('https://fms.alliancegenome.org/download/',f'GENE-DESCRIPTION-JSON_{mod}.json.gz',subpath=subp)

        #This should be fine.  But for the makefile it's nice if the directory in which this goes is the same as the {mod} in the filename.
        # And we'd like it to be the names of the prefixes
        if mod != modmap[mod]:
            newname = origname.replace(mod,modmap[mod])
            os.rename(origname,newname)


def write_labels(dd):
    for mod,prefix in modmap.items():
        with open(f'{dd}/{prefix}/GENE-DESCRIPTION-JSON_{prefix}_9.json','r') as inf:
            j = json.load(inf)
        with open(f'{dd}/{prefix}/labels','w') as outf:
            for gene in j['data']:
                gid = gene['gene_id'].split(':')[-1]
                outf.write(f'{prefix}:{gid}\t{gene["gene_name"]}\n')