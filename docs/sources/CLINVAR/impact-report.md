# Source impact report: CLINVAR

- Generated: 2026-07-29 04:56:00 UTC
- Babel commit: 1445d49c08dc48cd988327a3efa13dc1d7bb275e
- Source pipelines: sequencevariant
- Source prefixes: CLINVAR
- Comparison mode: synthetic

## 1. Identifiers added

Totals: 4,548,781 identifiers across 1 prefix(es) in 1 pipeline(s).

### By prefix

- CLINVAR: 4,548,781

### By pipeline

- sequencevariant: 4,548,781

## 2. Biolink types

### Overall declared type breakdown

- biolink:SequenceVariant: 4,548,781

### Source-declared (from each ids file)

- sequencevariant / CLINVAR
  - biolink:SequenceVariant: 4,548,781

### Final compendium-assigned (after glom)

- (no source identifiers found in any compendium)

## 3. Cross-references added

Totals: 2,896,403 cross-reference rows across 1 concord file(s).

### By pipeline

- sequencevariant / CLINVAR: 2,896,403

### Partner prefix breakdown (per pipeline)

- sequencevariant
  - DBSNP: 2,896,403

## 4. Clique impact

**Worst-case view.** This report is computed from the intermediate identifier and concord files and
cannot see downstream filtering that happens later in the build — most notably the Biolink Model's
per-class prefix restrictions, which drop identifiers whose prefix is not permitted for a clique's
biolink type. The counts and detail files below are therefore an *upper bound*: they show every
change the source could introduce before that filtering is applied.

### sequencevariant

- 4,297,854 new cliques composed only of CLINVAR identifiers (a n/a increase over the 0 pre-existing
  cliques)
- 0 existing cliques contain CLINVAR identifiers in the after state (n/a of the 0 pre-existing
  cliques). Of these, 0 cliques gain at least one structurally new identifier from CLINVAR, and 0
  already contained the CLINVAR CURIE via an xref from another source — CLINVAR's ids file now also
  lists those existing CURIEs as first-class typed identifiers.
- 0 existing cliques will be merged because of new CLINVAR cross-references
- 0 structurally-new CLINVAR identifiers are added to existing cliques (0 via expansion, 0 via
  merges). This is distinct from the 0 existing cliques that change, since one clique can gain
  several identifiers.
- Total cliques in this pipeline go from 0 to 4,297,854

#### Sample pure-new cliques (up to 3)

- [`CLINVAR:1077597`](http://identifiers.org/clinvar1077597)
  "NM_001330700.2(TOP2B):c.396-17_396-5del" **(preferred)**
  - [`CLINVAR:1078559`](http://identifiers.org/clinvar1078559)
    "NM_001330700.2(TOP2B):c.396-28_396-5del"
  - [`CLINVAR:1097328`](http://identifiers.org/clinvar1097328)
    "NM_001330700.2(TOP2B):c.396-20_396-5del"
  - [`CLINVAR:1107907`](http://identifiers.org/clinvar1107907)
    "NM_001330700.2(TOP2B):c.396-19_396-5del"
  - [`CLINVAR:1109179`](http://identifiers.org/clinvar1109179)
    "NM_001330700.2(TOP2B):c.396-24_396-5del"
  - [`CLINVAR:1129460`](http://identifiers.org/clinvar1129460)
    "NM_001330700.2(TOP2B):c.396-22_396-5del"
  - [`CLINVAR:1139321`](http://identifiers.org/clinvar1139321)
    "NM_001330700.2(TOP2B):c.396-25_396-5del"
  - [`CLINVAR:1141959`](http://identifiers.org/clinvar1141959)
    "NM_001330700.2(TOP2B):c.396-18_396-5del"
  - [`CLINVAR:1146422`](http://identifiers.org/clinvar1146422)
    "NM_001330700.2(TOP2B):c.396-23_396-5del"
  - [`CLINVAR:1164795`](http://identifiers.org/clinvar1164795)
    "NM_001330700.2(TOP2B):c.396-16_396-5del"
  - [`CLINVAR:1169723`](http://identifiers.org/clinvar1169723)
    "NM_001330700.2(TOP2B):c.396-14_396-5del"
  - [`CLINVAR:1169897`](http://identifiers.org/clinvar1169897)
    "NM_001330700.2(TOP2B):c.396-15_396-5del"
  - [`CLINVAR:1536334`](http://identifiers.org/clinvar1536334)
    "NM_001330700.2(TOP2B):c.396-11_396-5del"
  - [`CLINVAR:1559416`](http://identifiers.org/clinvar1559416)
    "NM_001330700.2(TOP2B):c.396-10_396-5del"
  - [`CLINVAR:1562401`](http://identifiers.org/clinvar1562401)
    "NM_001330700.2(TOP2B):c.396-15_396-5dup"
  - [`CLINVAR:1574681`](http://identifiers.org/clinvar1574681)
    "NM_001330700.2(TOP2B):c.396-18_396-5dup"
  - [`CLINVAR:1590560`](http://identifiers.org/clinvar1590560)
    "NM_001330700.2(TOP2B):c.396-34_396-5dup"
  - [`CLINVAR:1592578`](http://identifiers.org/clinvar1592578)
    "NM_001330700.2(TOP2B):c.396-27_396-5del"
  - [`CLINVAR:1594569`](http://identifiers.org/clinvar1594569)
    "NM_001330700.2(TOP2B):c.396-26_396-5del"
  - [`CLINVAR:1613468`](http://identifiers.org/clinvar1613468)
    "NM_001330700.2(TOP2B):c.396-13_396-5del"
  - [`CLINVAR:1621849`](http://identifiers.org/clinvar1621849)
    "NM_001330700.2(TOP2B):c.396-16_396-5dup"
  - [`CLINVAR:1622340`](http://identifiers.org/clinvar1622340)
    "NM_001330700.2(TOP2B):c.396-12_396-5del"
  - [`CLINVAR:1625147`](http://identifiers.org/clinvar1625147)
    "NM_001330700.2(TOP2B):c.396-19_396-5dup"
  - [`CLINVAR:1627688`](http://identifiers.org/clinvar1627688)
    "NM_001330700.2(TOP2B):c.396-21_396-5dup"
  - [`CLINVAR:1628130`](http://identifiers.org/clinvar1628130)
    "NM_001330700.2(TOP2B):c.396-21_396-5del"
  - [`CLINVAR:1631783`](http://identifiers.org/clinvar1631783)
    "NM_001330700.2(TOP2B):c.396-28_396-5dup"
  - [`CLINVAR:1635798`](http://identifiers.org/clinvar1635798)
    "NM_001330700.2(TOP2B):c.396-26_396-5dup"
  - [`CLINVAR:1637554`](http://identifiers.org/clinvar1637554)
    "NM_001330700.2(TOP2B):c.396-24_396-5dup"
  - [`CLINVAR:1637704`](http://identifiers.org/clinvar1637704)
    "NM_001330700.2(TOP2B):c.396-22_396-5dup"
  - [`CLINVAR:1640710`](http://identifiers.org/clinvar1640710)
    "NM_001330700.2(TOP2B):c.396-17_396-5dup"
  - [`CLINVAR:1644927`](http://identifiers.org/clinvar1644927)
    "NM_001330700.2(TOP2B):c.396-40_396-5dup"
  - [`CLINVAR:1663054`](http://identifiers.org/clinvar1663054)
    "NM_001330700.2(TOP2B):c.396-9_396-5del"
  - [`CLINVAR:1666342`](http://identifiers.org/clinvar1666342)
    "NM_001330700.2(TOP2B):c.396-29_396-5del"
  - [`CLINVAR:1671084`](http://identifiers.org/clinvar1671084)
    "NM_001330700.2(TOP2B):c.396-36_396-5dup"
  - [`CLINVAR:1944222`](http://identifiers.org/clinvar1944222)
    "NM_001330700.2(TOP2B):c.396-31_396-5del"
  - [`CLINVAR:2067743`](http://identifiers.org/clinvar2067743)
    "NM_001330700.2(TOP2B):c.396-7_396-5dup"
  - [`CLINVAR:2070991`](http://identifiers.org/clinvar2070991)
    "NM_001330700.2(TOP2B):c.396-9_396-5dup"
  - [`CLINVAR:2080217`](http://identifiers.org/clinvar2080217)
    "NM_001330700.2(TOP2B):c.396-8_396-5dup"
  - [`CLINVAR:2498924`](http://identifiers.org/clinvar2498924)
    "NM_001330700.2(TOP2B):c.396-6_396-5del"
  - [`CLINVAR:2653632`](http://identifiers.org/clinvar2653632)
    "NM_001330700.2(TOP2B):c.396-8_396-5del"
  - [`CLINVAR:2712185`](http://identifiers.org/clinvar2712185) "NM_001330700.2(TOP2B):c.396-5del"
  - [`CLINVAR:2720131`](http://identifiers.org/clinvar2720131)
    "NM_001330700.2(TOP2B):c.396-6_396-5dup"
  - [`CLINVAR:2900096`](http://identifiers.org/clinvar2900096)
    "NM_001330700.2(TOP2B):c.396-20_396-5dup"
  - [`CLINVAR:738536`](http://identifiers.org/clinvar738536)
    "NM_001330700.2(TOP2B):c.396-5_396-4insTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTATTTTTT"
  - [`DBSNP:rs56986587`](http://identifiers.org/dbsnp/rs56986587)
- [`CLINVAR:1685670`](http://identifiers.org/clinvar1685670) "NM_000251.3(MSH2):c.942+18_942+29dup"
  **(preferred)**
  - [`CLINVAR:1685677`](http://identifiers.org/clinvar1685677)
    "NM_000251.3(MSH2):c.942+20_942+29dup"
  - [`CLINVAR:1685683`](http://identifiers.org/clinvar1685683)
    "NM_000251.3(MSH2):c.942+15_942+29dup"
  - [`CLINVAR:1685688`](http://identifiers.org/clinvar1685688)
    "NM_000251.3(MSH2):c.942+14_942+29dup"
  - [`CLINVAR:1685690`](http://identifiers.org/clinvar1685690)
    "NM_000251.3(MSH2):c.942+13_942+29dup"
  - [`CLINVAR:1685699`](http://identifiers.org/clinvar1685699)
    "NM_000251.3(MSH2):c.942+12_942+29dup"
  - [`CLINVAR:1685710`](http://identifiers.org/clinvar1685710)
    "NM_000251.3(MSH2):c.942+11_942+29dup"
  - [`CLINVAR:1685718`](http://identifiers.org/clinvar1685718)
    "NM_000251.3(MSH2):c.942+10_942+29dup"
  - [`CLINVAR:1685726`](http://identifiers.org/clinvar1685726) "NM_000251.3(MSH2):c.942+9_942+29dup"
  - [`CLINVAR:1685732`](http://identifiers.org/clinvar1685732) "NM_000251.3(MSH2):c.942+8_942+29dup"
  - [`CLINVAR:1685751`](http://identifiers.org/clinvar1685751)
    "NM_000251.3(MSH2):c.942+19_942+29dup"
  - [`CLINVAR:1685754`](http://identifiers.org/clinvar1685754)
    "NM_000251.3(MSH2):c.942+24_942+29dup"
  - [`CLINVAR:1685758`](http://identifiers.org/clinvar1685758)
    "NM_000251.3(MSH2):c.942+25_942+29dup"
  - [`CLINVAR:1685767`](http://identifiers.org/clinvar1685767)
    "NM_000251.3(MSH2):c.942+26_942+29dup"
  - [`CLINVAR:1685774`](http://identifiers.org/clinvar1685774)
    "NM_000251.3(MSH2):c.942+23_942+29del"
  - [`CLINVAR:1685775`](http://identifiers.org/clinvar1685775) "NM_000251.3(MSH2):c.942+29dup"
  - [`CLINVAR:1685779`](http://identifiers.org/clinvar1685779)
    "NM_000251.3(MSH2):c.942+28_942+29dup"
  - [`CLINVAR:1685782`](http://identifiers.org/clinvar1685782)
    "NM_000251.3(MSH2):c.942+27_942+29dup"
  - [`CLINVAR:1685792`](http://identifiers.org/clinvar1685792)
    "NM_000251.3(MSH2):c.942+16_942+29dup"
  - [`CLINVAR:1685798`](http://identifiers.org/clinvar1685798)
    "NM_000251.3(MSH2):c.942+21_942+29dup"
  - [`CLINVAR:1692299`](http://identifiers.org/clinvar1692299)
    "NM_000251.3(MSH2):c.942+19_942+29del"
  - [`CLINVAR:1692300`](http://identifiers.org/clinvar1692300)
    "NM_000251.3(MSH2):c.942+21_942+29del"
  - [`CLINVAR:1692301`](http://identifiers.org/clinvar1692301)
    "NM_000251.3(MSH2):c.942+18_942+29del"
  - [`CLINVAR:182601`](http://identifiers.org/clinvar182601) "NM_000251.3(MSH2):c.942+17_942+29del"
  - [`CLINVAR:252474`](http://identifiers.org/clinvar252474) "NM_000251.3(MSH2):c.942+25_942+29del"
  - [`CLINVAR:2575512`](http://identifiers.org/clinvar2575512)
    "NM_000251.3(MSH2):c.942+12_942+29del"
  - [`CLINVAR:3072692`](http://identifiers.org/clinvar3072692)
    "NM_000251.3(MSH2):c.942+11_942+29del"
  - [`CLINVAR:3076131`](http://identifiers.org/clinvar3076131)
    "NM_000251.3(MSH2):c.942+29_942+30insAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
  - [`CLINVAR:336427`](http://identifiers.org/clinvar336427) "NM_000251.3(MSH2):c.942+28_942+29del"
  - [`CLINVAR:336428`](http://identifiers.org/clinvar336428) "NM_000251.3(MSH2):c.942+26_942+29del"
  - [`CLINVAR:374958`](http://identifiers.org/clinvar374958) "NM_000251.3(MSH2):c.942+29del"
  - [`CLINVAR:439908`](http://identifiers.org/clinvar439908) "NM_000251.3(MSH2):c.942+27_942+29del"
  - [`CLINVAR:491848`](http://identifiers.org/clinvar491848) "NM_000251.3(MSH2):c.942+16_942+29del"
  - [`CLINVAR:695772`](http://identifiers.org/clinvar695772) "NM_000251.3(MSH2):c.942+24_942+29del"
  - [`CLINVAR:801682`](http://identifiers.org/clinvar801682) "NM_000251.3(MSH2):c.942+7_942+29dup"
  - [`CLINVAR:801683`](http://identifiers.org/clinvar801683) "NM_000251.3(MSH2):c.942+22_942+29del"
  - [`CLINVAR:801684`](http://identifiers.org/clinvar801684) "NM_000251.3(MSH2):c.942+23_942+29dup"
  - [`CLINVAR:801685`](http://identifiers.org/clinvar801685) "NM_000251.3(MSH2):c.942+22_942+29dup"
  - [`CLINVAR:801686`](http://identifiers.org/clinvar801686) "NM_000251.3(MSH2):c.942+17_942+29dup"
  - [`CLINVAR:91248`](http://identifiers.org/clinvar91248) "NM_000251.3(MSH2):c.942+20_942+29del"
  - [`CLINVAR:983056`](http://identifiers.org/clinvar983056) "NM_000251.3(MSH2):c.942+14_942+29del"
  - [`DBSNP:rs11309117`](http://identifiers.org/dbsnp/rs11309117)
- [`CLINVAR:1164648`](http://identifiers.org/clinvar1164648) "NM_002024.6(FMR1):c.-129CGG[6]"
  **(preferred)**
  - [`CLINVAR:1166634`](http://identifiers.org/clinvar1166634) "NM_002024.6(FMR1):c.-129CGG[7]"
  - [`CLINVAR:1168103`](http://identifiers.org/clinvar1168103) "NM_002024.6(FMR1):c.-129CGG[5]"
  - [`CLINVAR:183387`](http://identifiers.org/clinvar183387) "NM_002024.6(FMR1):c.-129CGG[201]"
  - [`CLINVAR:752727`](http://identifiers.org/clinvar752727) "NM_002024.6(FMR1):c.-129CGG[11]"
  - [`CLINVAR:760968`](http://identifiers.org/clinvar760968) "NM_002024.6(FMR1):c.-129CGG[31]"
  - [`CLINVAR:760974`](http://identifiers.org/clinvar760974) "NM_002024.6(FMR1):c.-129CGG[23]"
  - [`CLINVAR:761002`](http://identifiers.org/clinvar761002) "NM_002024.6(FMR1):c.-129CGG[29]"
  - [`CLINVAR:761003`](http://identifiers.org/clinvar761003) "NM_002024.6(FMR1):c.-129CGG[30]"
  - [`CLINVAR:761004`](http://identifiers.org/clinvar761004) "NM_002024.6(FMR1):c.-129CGG[37]"
  - [`CLINVAR:761197`](http://identifiers.org/clinvar761197) "NM_002024.6(FMR1):c.-129CGG[20]"
  - [`CLINVAR:761225`](http://identifiers.org/clinvar761225) "NM_002024.6(FMR1):c.-129CGG[42]"
  - [`CLINVAR:762341`](http://identifiers.org/clinvar762341) "NM_002024.6(FMR1):c.-129CGG[35]"
  - [`CLINVAR:762343`](http://identifiers.org/clinvar762343) "NM_002024.6(FMR1):c.-129CGG[33]"
  - [`CLINVAR:762358`](http://identifiers.org/clinvar762358) "NM_002024.6(FMR1):c.-129CGG[32]"
  - [`CLINVAR:762365`](http://identifiers.org/clinvar762365) "NM_002024.6(FMR1):c.-129CGG[40]"
  - [`CLINVAR:762367`](http://identifiers.org/clinvar762367) "NM_002024.6(FMR1):c.-129CGG[36]"
  - [`CLINVAR:762625`](http://identifiers.org/clinvar762625) "NM_002024.6(FMR1):c.-129CGG[38]"
  - [`CLINVAR:762626`](http://identifiers.org/clinvar762626) "NM_002024.6(FMR1):c.-129CGG[22]"
  - [`CLINVAR:762634`](http://identifiers.org/clinvar762634) "NM_002024.6(FMR1):c.-129CGG[41]"
  - [`CLINVAR:762636`](http://identifiers.org/clinvar762636) "NM_002024.6(FMR1):c.-129CGG[26]"
  - [`CLINVAR:762640`](http://identifiers.org/clinvar762640) "NM_002024.6(FMR1):c.-129CGG[27]"
  - [`CLINVAR:762764`](http://identifiers.org/clinvar762764) "NM_002024.6(FMR1):c.-129CGG[24]"
  - [`CLINVAR:762766`](http://identifiers.org/clinvar762766) "NM_002024.6(FMR1):c.-129CGG[44]"
  - [`CLINVAR:762791`](http://identifiers.org/clinvar762791) "NM_002024.6(FMR1):c.-129CGG[19]"
  - [`CLINVAR:762804`](http://identifiers.org/clinvar762804) "NM_002024.6(FMR1):c.-129CGG[14]"
  - [`CLINVAR:762827`](http://identifiers.org/clinvar762827) "NM_002024.6(FMR1):c.-129CGG[25]"
  - [`CLINVAR:762841`](http://identifiers.org/clinvar762841) "NM_002024.6(FMR1):c.-129CGG[34]"
  - [`CLINVAR:762842`](http://identifiers.org/clinvar762842) "NM_002024.6(FMR1):c.-129CGG[43]"
  - [`CLINVAR:762898`](http://identifiers.org/clinvar762898) "NM_002024.6(FMR1):c.-129CGG[21]"
  - [`CLINVAR:762915`](http://identifiers.org/clinvar762915) "NM_002024.6(FMR1):c.-129CGG[39]"
  - [`CLINVAR:763001`](http://identifiers.org/clinvar763001) "NM_002024.6(FMR1):c.-129CGG[18]"
  - [`CLINVAR:763079`](http://identifiers.org/clinvar763079) "NM_002024.6(FMR1):c.-129CGG[28]"
  - [`CLINVAR:763160`](http://identifiers.org/clinvar763160) "NM_002024.6(FMR1):c.-129CGG[16]"
  - [`CLINVAR:763962`](http://identifiers.org/clinvar763962) "NM_002024.6(FMR1):c.-129CGG[13]"
  - [`CLINVAR:766072`](http://identifiers.org/clinvar766072) "NM_002024.6(FMR1):c.-129CGG[9]"
  - [`CLINVAR:766615`](http://identifiers.org/clinvar766615) "NM_002024.6(FMR1):c.-129CGG[17]"
  - [`CLINVAR:793052`](http://identifiers.org/clinvar793052) "NM_002024.6(FMR1):c.-129CGG[15]"
  - [`CLINVAR:794273`](http://identifiers.org/clinvar794273) "NM_002024.6(FMR1):c.-129CGG[12]"
  - [`CLINVAR:795779`](http://identifiers.org/clinvar795779) "NM_002024.6(FMR1):c.-129CGG[8]"
  - [`DBSNP:rs193922936`](http://identifiers.org/dbsnp/rs193922936)
