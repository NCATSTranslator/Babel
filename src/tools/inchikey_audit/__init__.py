"""``babel-inchikey-audit``: which chemical cliques carry an InChIKey that does not belong to their records?

The CLI only parses arguments and writes files. The edge reconstruction is :mod:`src.model.glom_edges`; the
components, tiers and triage are :mod:`src.model.inchikey_audit`. See docs/tools/InchikeyAudit.md.
"""
