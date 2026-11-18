"""``babel-inchikey-audit``: which records were attached to a chemical structure they are not, and by which xref?

The CLI only parses arguments and writes files. The edge reconstruction is :mod:`src.model.glom_edges`; the
components, tiers and triage are :mod:`src.model.inchikey_audit`. See docs/tools/InchikeyAudit.md.
"""
