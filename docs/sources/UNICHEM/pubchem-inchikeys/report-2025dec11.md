# UniChem's InChIKeys for PubChem CIDs vs. PubChem's own, 2025dec11

Written by `scripts/compare_pubchem_inchikeys.py`; do not edit by hand.

- UniChem (source 22) in 2025dec11: 116,164,164 rows for 116,164,164 CIDs.
- PubChem's `CID-InChI-Key.gz`, downloaded 2026-11-16: 124,863,647 CIDs,
  10,560,140 of them not in UniChem.

| UniChem's key vs. PubChem's | CIDs | Share |
|---|---|---|
| Same key | 114,302,709 | 98.398% |
| CID is not in PubChem's file | 1,860,657 | 1.602% |
| Different skeleton | 606 | 0.001% |
| Same skeleton; two different stereo layers | 87 | 0.000% |
| Same skeleton; UniChem stereo-less, PubChem specific | 59 | 0.000% |
| Same skeleton; PubChem stereo-less, UniChem specific | 46 | 0.000% |

## Examples

Five CIDs of each kind of difference, spread evenly across the CID range.

| Kind | CID | UniChem's key | PubChem's key |
|---|---|---|---|
| CID is not in PubChem's file | 83 | `VHAFWRWGHGSZDL-UHFFFAOYSA-N` | `` |
| CID is not in PubChem's file | 88515751 | `IVSMKHOSPDABHE-QAYKDTKBSA-N` | `` |
| CID is not in PubChem's file | 134176733 | `HAMPFMDYPOIQHR-OYISTZKKSA-N` | `` |
| CID is not in PubChem's file | 154026952 | `XVFMCTWUJQNOTI-IWIPYMOSSA-N` | `` |
| CID is not in PubChem's file | 158301485 | `GMNYICKUXVITKU-UHFFFAOYSA-O` | `` |
| Different skeleton | 50286 | `VGTOUOZCVUBDBV-UHFFFAOYSA-M` | `KRPAACLBBQSAEA-UHFFFAOYSA-M` |
| Different skeleton | 58480409 | `DQQMDUNOVOLBEK-UHFFFAOYSA-L` | `MVRXQQKCLTZVIF-UHFFFAOYSA-L` |
| Different skeleton | 88096891 | `NGVOBJRKVCQWEG-UHFFFAOYSA-N` | `MMUNNXITCUYTJK-UHFFFAOYSA-N` |
| Different skeleton | 89698364 | `LYPYKIQRCNHEJA-UHFFFAOYSA-N` | `HXQXJKPLZHMLEZ-UHFFFAOYSA-N` |
| Different skeleton | 134790222 | `FHFBAVADRQVDCN-UHFFFAOYSA-N` | `XQVLCYQYBCGQNK-UHFFFAOYSA-N` |
| Same skeleton; PubChem stereo-less, UniChem specific | 79073 | `ZQZYKZCGDCQGII-AKAJXFOGSA-N` | `ZQZYKZCGDCQGII-UHFFFAOYSA-N` |
| Same skeleton; PubChem stereo-less, UniChem specific | 461519 | `ABTLZHPMQVSERP-GOSISDBHSA-N` | `ABTLZHPMQVSERP-UHFFFAOYSA-N` |
| Same skeleton; PubChem stereo-less, UniChem specific | 21822061 | `YPVVVWXXZSKKKY-OAQYLSRUSA-N` | `YPVVVWXXZSKKKY-UHFFFAOYSA-N` |
| Same skeleton; PubChem stereo-less, UniChem specific | 122504828 | `MPWXECXGMYKQHL-VIFPVBQESA-N` | `MPWXECXGMYKQHL-UHFFFAOYSA-N` |
| Same skeleton; PubChem stereo-less, UniChem specific | 155107897 | `MNQZWGTZKMJXBR-GMHPVODTSA-N` | `MNQZWGTZKMJXBR-UHFFFAOYSA-N` |
| Same skeleton; UniChem stereo-less, PubChem specific | 125941 | `QGYHHJFMAISYHD-UHFFFAOYSA-N` | `QGYHHJFMAISYHD-WMPKNSHKSA-N` |
| Same skeleton; UniChem stereo-less, PubChem specific | 4922066 | `DUHSKOVFPABWEW-UHFFFAOYSA-N` | `DUHSKOVFPABWEW-XGAUYOCXSA-N` |
| Same skeleton; UniChem stereo-less, PubChem specific | 9545875 | `LSPIQKXJHDDALY-UHFFFAOYSA-N` | `LSPIQKXJHDDALY-AFLCPGBUSA-N` |
| Same skeleton; UniChem stereo-less, PubChem specific | 87722813 | `XXTHJPJWELFZFD-UHFFFAOYSA-N` | `XXTHJPJWELFZFD-LDADJPATSA-N` |
| Same skeleton; UniChem stereo-less, PubChem specific | 88091945 | `ZEEKIUDDCCLAMQ-UHFFFAOYSA-N` | `ZEEKIUDDCCLAMQ-YVLHZVERSA-N` |
| Same skeleton; two different stereo layers | 359157 | `QCAVOIFYYYBGOQ-LLVKDONJSA-N` | `QCAVOIFYYYBGOQ-NSHDSACASA-N` |
| Same skeleton; two different stereo layers | 9545443 | `PXTQDGUXNANUPT-ULSWSFLHSA-N` | `PXTQDGUXNANUPT-QSDYZZDBSA-N` |
| Same skeleton; two different stereo layers | 9545804 | `HKEBIGKZDLSJRT-PNVGIOEQSA-N` | `HKEBIGKZDLSJRT-YEASRJMDSA-N` |
| Same skeleton; two different stereo layers | 87728724 | `YFUKJAYFLVIFPJ-TUURXHPNSA-N` | `YFUKJAYFLVIFPJ-SXOIMPFCSA-N` |
| Same skeleton; two different stereo layers | 136695191 | `FMCIYBBPJONAMN-OUJUMPROSA-N` | `FMCIYBBPJONAMN-BUCIVEMSSA-N` |
