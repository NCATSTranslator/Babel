# Fixtures for `babel-compare-resolution`

Unedited responses from dev NodeNorm and NameRes (Babel 2026jul22), saved on 2026-11-17. They
stand in for the services in the unit tests, so the tests see real response shapes. Regenerate
them with the same requests if the services' response format changes.

| File | Request |
|---|---|
| `dev_ruxolitinib_dc_false.json` | `POST https://nodenormalization-sri.renci.org/get_normalized_nodes` with `{"curies": ["CHEBI:66919", "CHEBI:91405", "GTOPDB:5688", "NOTAPREFIX:1"], "conflate": true, "drug_chemical_conflate": false, "description": false}` |
| `dev_ruxolitinib_dc_true.json` | The same, with `"drug_chemical_conflate": true` |
| `dev_lookup_ruxolitinib.json` | `GET https://name-resolution-sri.renci.org/lookup?string=ruxolitinib&limit=5&autocomplete=false` |
| `dev_status.json` | `GET https://nodenormalization-sri.renci.org/status` |

They show the #1206 regression: `GTOPDB:5688` sits in the stereo-unspecified clique `CHEBI:91405`
rather than with the drug, `CHEBI:66919`.
