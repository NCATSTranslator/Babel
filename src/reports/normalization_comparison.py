"""Compare how a set of CURIEs normalizes on several NodeNorm deployments, for answering a duplicate-node report.

A report that "these show up as separate results" is answered by asking what each deployment serves for each
CURIE, with and without DrugChemical conflation; which of the resulting cliques are distinct; and how the
distinct cliques' InChIKeys relate, since that usually names the cause (see :mod:`src.model.inchikeys` and
``docs/issues/AGENTS.md``). This module turns the services' responses into that comparison and renders it
as Markdown, with a Babel Explorer link and a draft ``babel_tests`` block to start the issue's tests from.

It does no network access itself: ``src/tools/compare_resolution/cli.py`` fetches with
:mod:`src.utils.translator_services` and passes the responses in, so everything here is testable offline.
"""

import itertools
import re
from dataclasses import dataclass, field

from src.model.inchikeys import InchikeyRelation, classify_inchikey_pair
from src.util import Text

# Prefixes whose members are listed for each clique by default. They are the ones that decided today's
# chemical duplicate reports: a GTOPDB ligand in the wrong clique carries the drug's name with it (#1206),
# and a drug's MESH and DRUGBANK identifiers have no structure of their own, so they show which of two
# structures the sources attached the drug to (#1208).
DEFAULT_HIGHLIGHT_PREFIXES = ("GTOPDB", "MESH", "DRUGBANK")

# Order in which relations are "most alike", used to pick one relation for two cliques that carry several
# InChIKeys each (a few cliques do; #1068).
_RELATION_ORDER = list(InchikeyRelation)


@dataclass(frozen=True)
class CliqueSummary:
    """The parts of a NodeNorm result that matter when comparing cliques."""

    leader: str
    label: str
    biolink_type: str
    size: int
    inchikeys: tuple[str, ...]
    highlighted: tuple[str, ...]
    members: tuple[str, ...] = ()


@dataclass
class InstanceResult:
    """What one NodeNorm deployment serves for each CURIE, without and with DrugChemical conflation.

    ``error`` is set, and both maps are empty, when the deployment could not be queried.
    """

    target: str
    babel_version: str | None = None
    error: str | None = None
    unconflated: dict[str, CliqueSummary | None] = field(default_factory=dict)
    conflated: dict[str, CliqueSummary | None] = field(default_factory=dict)


def summarize_clique(result: dict | None, highlight_prefixes=DEFAULT_HIGHLIGHT_PREFIXES) -> CliqueSummary | None:
    """Reduce one ``get_normalized_nodes`` value to a :class:`CliqueSummary`; ``None`` stays ``None``."""
    if not result:
        return None
    members = [eq["identifier"] for eq in result.get("equivalent_identifiers", [])]
    types = result.get("type") or [""]
    return CliqueSummary(
        leader=result["id"]["identifier"],
        label=result["id"].get("label", ""),
        biolink_type=types[0],
        size=len(members),
        inchikeys=tuple(m for m in members if Text.get_prefix_or_none(m) == "INCHIKEY"),
        highlighted=tuple(m for m in members if Text.get_prefix_or_none(m) in highlight_prefixes),
        members=tuple(members),
    )


def summarize_instance(
    target: str,
    babel_version: str | None,
    curies: list[str],
    raw_unconflated: dict,
    raw_conflated: dict,
    highlight_prefixes=DEFAULT_HIGHLIGHT_PREFIXES,
) -> InstanceResult:
    """Build an :class:`InstanceResult` from one deployment's two ``get_normalized_nodes`` responses."""
    return InstanceResult(
        target=target,
        babel_version=babel_version,
        unconflated={c: summarize_clique(raw_unconflated.get(c), highlight_prefixes) for c in curies},
        conflated={c: summarize_clique(raw_conflated.get(c), highlight_prefixes) for c in curies},
    )


def relate_cliques(a: CliqueSummary, b: CliqueSummary) -> InchikeyRelation:
    """How two cliques' structures relate: the most alike relation over every pair of their InChIKeys."""
    if not a.inchikeys or not b.inchikeys:
        return InchikeyRelation.MISSING
    relations = [classify_inchikey_pair(x, y) for x in a.inchikeys for y in b.inchikeys]
    return min(relations, key=_RELATION_ORDER.index)


def distinct_cliques(summaries: dict[str, CliqueSummary | None]) -> list[CliqueSummary]:
    """The different cliques among the CURIEs' results, in the order the CURIEs were given."""
    seen = {}
    for summary in summaries.values():
        if summary and summary.leader not in seen:
            seen[summary.leader] = summary
    return list(seen.values())


def shared_identifiers(cliques: list[CliqueSummary]) -> dict[str, list[str]]:
    """Identifiers that are members of more than one of these cliques, with the leaders of those cliques.

    NodeNorm serves only one clique per identifier, so a shared identifier means two compendia both claim it
    and NodeNorm picks one arbitrarily. That breaks Babel's rule that compendia never share an identifier,
    and is the signature of a UMLS CUI typed T116 sitting in both Protein and a chemical compendium (#308).
    """
    holders: dict[str, list[str]] = {}
    for clique in cliques:
        for member in clique.members:
            holders.setdefault(member, []).append(clique.leader)
    return {member: leaders for member, leaders in holders.items() if len(leaders) > 1}


def _normalize_label(label: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", label.casefold())


def same_label_curies(lookup_hits: list[dict], name: str) -> list[str]:
    """The CURIEs of NameRes hits whose preferred label is ``name``, ignoring case and punctuation.

    These are the "same name, separate result" nodes a duplicate report is about. A hit whose label only
    contains the name ("ruxolitinib phosphate") is a different substance and is left out.
    """
    wanted = _normalize_label(name)
    return [hit["curie"] for hit in lookup_hits if _normalize_label(hit.get("label", "")) == wanted]


def instance_disagreements(instances: list[InstanceResult], curies: list[str]) -> dict[str, dict[str, str | None]]:
    """For each CURIE whose (unconflated) clique leader differs between deployments, the leader on each one."""
    reachable = [i for i in instances if not i.error]
    disagreements = {}
    for curie in curies:
        leaders = {i.target: (i.unconflated[curie].leader if i.unconflated.get(curie) else None) for i in reachable}
        if len(set(leaders.values())) > 1:
            disagreements[curie] = leaders
    return disagreements


def draft_babel_tests(same_groups: list[list[str]], different_groups: list[list[str]], resolving: list[str]) -> str:
    """A ``babel_tests`` YAML block: ``ResolvesWith`` for each same group, ``DoesNotResolveWith`` for each
    different group, and a ``Resolves`` guard for every CURIE in ``resolving``.

    It is a starting point. Before it goes in an issue, check each group says what the *fix* should
    produce, and run it with babel-validation (``docs/issues/AGENTS.md``).
    """
    lines = ["babel_tests:"]
    for key, groups in (("ResolvesWith", same_groups), ("DoesNotResolveWith", different_groups)):
        if groups:
            lines.append(f"  {key}:")
            lines += [f"    - [{', '.join(repr(c) for c in group)}]" for group in groups]
    if resolving:
        lines.append("  Resolves:")
        lines.append(f"    - [{', '.join(repr(c) for c in resolving)}]")
    return "\n".join(lines) + "\n"


def _cell(values) -> str:
    return ", ".join(f"`{v}`" for v in values) if values else ""


def _render_instance(instance: InstanceResult, curies: list[str], highlight_prefixes) -> list[str]:
    version = f"Babel {instance.babel_version}" if instance.babel_version else "Babel version unknown"
    out = [f"## {instance.target} ({version})", ""]
    if instance.error:
        return out + [f"Could not query this instance: {instance.error}", ""]
    out += [
        f"| CURIE | Clique | Label | Type | Size | InChIKey | {', '.join(highlight_prefixes)} "
        "| With DrugChemical conflation |",
        "|---|---|---|---|---:|---|---|---|",
    ]
    for curie in curies:
        summary = instance.unconflated.get(curie)
        conflated = instance.conflated.get(curie)
        if not summary:
            out.append(f"| `{curie}` | does not normalize | | | | | | |")
            continue
        if not conflated:
            with_conflation = "does not normalize"
        elif conflated.leader != summary.leader:
            with_conflation = f"joins `{conflated.leader}` ({conflated.size} IDs)"
        elif conflated.size != summary.size:
            with_conflation = f"same leader, {conflated.size} IDs"
        else:
            with_conflation = "unchanged"
        out.append(
            f"| `{curie}` | `{summary.leader}` | {summary.label} | {summary.biolink_type} | {summary.size} "
            f"| {_cell(summary.inchikeys)} | {_cell(summary.highlighted)} | {with_conflation} |"
        )
    cliques = distinct_cliques(instance.unconflated)
    conflated_leader = {
        summary.leader: instance.conflated[curie].leader
        for curie, summary in instance.unconflated.items()
        if summary and instance.conflated.get(curie)
    }
    out.append("")
    if len(cliques) < 2:
        return out + ["All of these CURIEs are in one clique.", ""]
    out += ["How the separate cliques' structures relate:", ""]
    unrelated = 0
    for a, b in itertools.combinations(cliques, 2):
        relation = relate_cliques(a, b)
        unrelated_kinds = (InchikeyRelation.DIFFERENT_SKELETON, InchikeyRelation.MISSING)
        if relation in unrelated_kinds and _normalize_label(a.label) != _normalize_label(b.label):
            # Nothing ties these two together, as when several drugs are compared at once: not a duplicate.
            unrelated += 1
            continue
        joined = a.leader in conflated_leader and conflated_leader.get(a.leader) == conflated_leader.get(b.leader)
        note = "; joined by DrugChemical conflation" if joined else ""
        out.append(f"- `{a.leader}` and `{b.leader}`: {relation.value}{note}")
    if unrelated:
        out.append(f"- ({unrelated} more pairs share neither a skeleton nor a label, so are left out)")
    shared = shared_identifiers(cliques)
    if shared:
        out += ["", "Identifiers in more than one of these cliques (two compendia claim them; see #308):", ""]
        out += [f"- `{member}`: {_cell(leaders)}" for member, leaders in shared.items()]
    return out + [""]


def render_report(
    curies: list[str],
    instances: list[InstanceResult],
    explorer_url: str,
    same_groups: list[list[str]],
    different_groups: list[list[str]],
    highlight_prefixes=DEFAULT_HIGHLIGHT_PREFIXES,
) -> str:
    """Render the whole comparison as Markdown."""
    out = [
        f"# How {len(curies)} CURIEs normalize",
        "",
        f"[Compare them in Babel Explorer]({explorer_url}). The tables below are without DrugChemical "
        "conflation; the last column shows where conflation moves a CURIE.",
        "",
    ]
    for instance in instances:
        out += _render_instance(instance, curies, highlight_prefixes)
    disagreements = instance_disagreements(instances, curies)
    if disagreements:
        out += ["## Instances disagree", ""]
        for curie, leaders in disagreements.items():
            out.append(f"- `{curie}`: " + "; ".join(f"{t} → `{leader}`" for t, leader in leaders.items()))
        out.append("")
    resolving = [c for c in curies if any(i.unconflated.get(c) for i in instances if not i.error)]
    out += [
        "## Draft BabelTests",
        "",
        "Edit before use: assert what the fix should produce. Run it with babel-validation before posting.",
        "",
        "```yaml",
        draft_babel_tests(same_groups, different_groups, resolving).rstrip("\n"),
        "```",
        "",
    ]
    return "\n".join(out)
