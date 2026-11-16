# UniChem's InChIKeys for PubChem CIDs vs. PubChem's own, 2026jul22

Written by `scripts/compare_pubchem_inchikeys.py`; do not edit by hand.

- UniChem (source 22) in 2026jul22: 123,860,454 rows for 123,860,440 CIDs.
- PubChem's `CID-InChI-Key.gz`, downloaded 2026-11-16: 124,863,647 CIDs,
  1,020,130 of them not in UniChem.

| UniChem's key vs. PubChem's | CIDs | Share |
|---|---|---|
| Same key | 121,376,193 | 97.994% |
| Same skeleton; PubChem stereo-less, UniChem specific | 1,454,223 | 1.174% |
| Same skeleton; two different stereo layers | 972,740 | 0.785% |
| Same skeleton; UniChem stereo-less, PubChem specific | 39,417 | 0.032% |
| CID is not in PubChem's file | 16,923 | 0.014% |
| Different skeleton | 958 | 0.001% |

## Examples

Five CIDs of each kind of difference, spread evenly across the CID range.

| Kind | CID | UniChem's key | PubChem's key |
|---|---|---|---|
| CID is not in PubChem's file | 91829 | `PCDVINMRZHPVSF-UHFFFAOYSA-L` | `` |
| CID is not in PubChem's file | 72079768 | `BUUUFPXSSIAPRI-UHFFFAOYSA-N` | `` |
| CID is not in PubChem's file | 131676633 | `NVNRMUXBECTIHH-WNQIDUERSA-N` | `` |
| CID is not in PubChem's file | 145872427 | `UHCGJPNNQSFESH-UHFFFAOYSA-N` | `` |
| CID is not in PubChem's file | 154793141 | `VCWDMFDNRCIPDP-USVZCIMESA-N` | `` |
| Different skeleton | 139899 | `HRFMMLMVZRDSRM-UHFFFAOYSA-K` | `BRVXARAYULRTFY-UHFFFAOYSA-L` |
| Different skeleton | 87477346 | `FZTVIBBFOMLGMB-UHFFFAOYSA-N` | `OFNSXCOAOXYOAW-UHFFFAOYSA-N` |
| Different skeleton | 136501345 | `VPGKEYJBONWWKN-DVTICJEHSA-N` | `OIONLAFNPAIHEF-DVTICJEHSA-O` |
| Different skeleton | 158281987 | `MANGPDHQLJTWHI-UHFFFAOYSA-N` | `VTNLFNJFURUAJN-VMPITWQZSA-O` |
| Different skeleton | 163929340 | `WWXVLONQFAECFF-JTHCTSSBSA-N` | `XVYAKSKUYPSYBF-JTHCTSSBSA-Q` |
| Same skeleton; PubChem stereo-less, UniChem specific | 796 | `NMUOATVLLQEYHI-GORDUTHDSA-N` | `NMUOATVLLQEYHI-UHFFFAOYSA-N` |
| Same skeleton; PubChem stereo-less, UniChem specific | 24160323 | `OETWZZVHULZKPT-MHHGMWQQSA-N` | `OETWZZVHULZKPT-UHFFFAOYSA-N` |
| Same skeleton; PubChem stereo-less, UniChem specific | 101326993 | `YKGUECJTQFXLLT-WCWDXBQESA-N` | `YKGUECJTQFXLLT-UHFFFAOYSA-N` |
| Same skeleton; PubChem stereo-less, UniChem specific | 136590809 | `YOCRIPCUFYPASC-OEULXHSESA-N` | `YOCRIPCUFYPASC-UHFFFAOYSA-N` |
| Same skeleton; PubChem stereo-less, UniChem specific | 156751121 | `FJXYIVPKBVICNE-DEDYPNTBSA-N` | `FJXYIVPKBVICNE-UHFFFAOYSA-N` |
| Same skeleton; UniChem stereo-less, PubChem specific | 19582 | `YSGQGNQWBLYHPE-UHFFFAOYSA-N` | `YSGQGNQWBLYHPE-BRIGUCEYSA-N` |
| Same skeleton; UniChem stereo-less, PubChem specific | 25462825 | `INCLXHBYZJHBGS-UHFFFAOYSA-N` | `INCLXHBYZJHBGS-INIZCTEOSA-N` |
| Same skeleton; UniChem stereo-less, PubChem specific | 78581634 | `UBBNQOGNCRRBHE-UHFFFAOYSA-N` | `UBBNQOGNCRRBHE-PBHUPZEISA-N` |
| Same skeleton; UniChem stereo-less, PubChem specific | 122689900 | `ORRTUIULXAZYQS-UHFFFAOYSA-N` | `ORRTUIULXAZYQS-JGCGQSQUSA-N` |
| Same skeleton; UniChem stereo-less, PubChem specific | 158544768 | `HOYZNODORMMFFK-UHFFFAOYSA-N` | `HOYZNODORMMFFK-CPYMPVJRSA-N` |
| Same skeleton; two different stereo layers | 6289 | `DFBKLUNHFCTMDC-SYBLPMLBSA-N` | `DFBKLUNHFCTMDC-BFLCFTQHSA-N` |
| Same skeleton; two different stereo layers | 57275813 | `HMVYDAWLXXXCAF-JDRLWBPCSA-N` | `HMVYDAWLXXXCAF-QKIXDUKBSA-N` |
| Same skeleton; two different stereo layers | 126706865 | `BCYQJHOEMBCIRD-QOPQNSINSA-N` | `BCYQJHOEMBCIRD-IFUZJYIXSA-N` |
| Same skeleton; two different stereo layers | 144694626 | `VUBUDFGBOZQRIL-MCWNTOPDSA-N` | `VUBUDFGBOZQRIL-UONOGXRCSA-N` |
| Same skeleton; two different stereo layers | 163616661 | `HKOVLXZXFNBGLF-GDQASGNKSA-N` | `HKOVLXZXFNBGLF-OUUKIJBASA-N` |
