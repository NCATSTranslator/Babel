"""CLI for the per-source impact report.

Invocation:
    uv run python -m src.cli.source_impact_report --source EMAPA

The CLI discovers where the source contributes (across one or more semantic types),
runs a synthetic re-glom with and without the source for each registered semantic type,
diffs the resulting cliques, scans the final compendia to see which type the source's
CURIEs ended up under, and writes a markdown (and optionally JSON) report.

See ``docs/sources/<SOURCE>/impact-report.md`` for the rendered output; ``--output``
overrides the path.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import pathlib
import subprocess
import sys
from collections.abc import Callable

import src.createcompendia.anatomy as anatomy
from src.model.clique_diff import (
    SourceImpactDiff,
    cliques_from_compendia,
    diff_cliques,
    load_compendium,
)
from src.model.source import SourceContribution, discover_source
from src.reports.source_impact import render_json, render_markdown

logger = logging.getLogger(__name__)


ComputeCliquesFn = Callable[..., tuple[dict, dict]]


SEMANTIC_TYPE_CONFIG: dict[str, dict] = {
    "anatomy": {
        "compute_fn": anatomy.compute_cliques_for_impact_report,
        "compendium_files": [
            "AnatomicalEntity.txt",
            "Cell.txt",
            "CellularComponent.txt",
            "GrossAnatomicalStructure.txt",
        ],
    },
}


def _list_source_files(directory: pathlib.Path) -> list[pathlib.Path]:
    """Return non-metadata files in a `concords/` or `ids/` directory."""
    if not directory.exists():
        return []
    return sorted(
        p for p in directory.iterdir()
        if p.is_file() and not p.name.startswith("metadata-") and not p.name.endswith(".yaml")
    )


def _compute_synthetic_diff(
    semantic_type: str,
    source_name: str,
    intermediate_root: pathlib.Path,
    source_curies: frozenset[str],
) -> SourceImpactDiff:
    """Run a registered compute_fn twice and return the clique diff for one semantic type."""
    cfg = SEMANTIC_TYPE_CONFIG[semantic_type]
    compute_fn: ComputeCliquesFn = cfg["compute_fn"]

    ids_dir = intermediate_root / semantic_type / "ids"
    concords_dir = intermediate_root / semantic_type / "concords"
    identifiers = [str(p) for p in _list_source_files(ids_dir)]
    concordances = [str(p) for p in _list_source_files(concords_dir)]

    logger.info("synthetic diff for %s: %d ids files, %d concord files",
                semantic_type, len(identifiers), len(concordances))

    after_dicts, _ = compute_fn(concordances, identifiers)
    before_dicts, _ = compute_fn(concordances, identifiers, excluded_sources={source_name})

    return diff_cliques(before_dicts, after_dicts, source_curies, semantic_type=semantic_type)


def _final_compendium_breakdown(
    contribution: SourceContribution,
    semantic_types: list[str],
    compendia_root: pathlib.Path,
) -> dict[str, dict[str, int]]:
    """Count how many source CURIEs land in each compendium file per semantic type."""
    breakdown: dict[str, dict[str, int]] = {}
    for st in semantic_types:
        cfg = SEMANTIC_TYPE_CONFIG.get(st)
        if cfg is None:
            continue
        stc = contribution.by_semantic_type.get(st)
        if stc is None:
            continue
        source_curies = stc.all_curies
        per_file: dict[str, int] = {}
        for fname in cfg["compendium_files"]:
            path = compendia_root / fname
            if not path.exists():
                continue
            count = 0
            for clique in load_compendium(path):
                for ident in clique.get("identifiers", []):
                    if ident.get("i") in source_curies:
                        count += 1
            per_file[fname] = count
        breakdown[st] = per_file
    return breakdown


def _remote_comparison_summary(
    contribution: SourceContribution,
    semantic_types: list[str],
    remote_url: str,
    remote_cache_dir: pathlib.Path,
    compendia_root: pathlib.Path,
) -> dict[str, dict[str, int]]:
    """Download previous-build compendia and count cliques present/missing for this source.

    Returns a per-semantic-type breakdown with keys ``remote_total_cliques``,
    ``remote_cliques_with_source_curies``, ``current_cliques_with_source_curies``, and
    ``current_only``. The "current only" count is the number of cliques in the current
    build that contain any source CURIE *and* are not present (by identifier-set) in the
    remote build — a useful first-pass estimate of net-new clique structure introduced
    by adding this source.
    """
    import requests  # imported lazily so synthetic-only runs don't need it

    remote_cache_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, dict[str, int]] = {}
    base = remote_url.rstrip("/")

    for st in semantic_types:
        cfg = SEMANTIC_TYPE_CONFIG.get(st)
        if cfg is None:
            continue
        stc = contribution.by_semantic_type.get(st)
        if stc is None:
            continue
        source_curies = stc.all_curies

        remote_paths: list[pathlib.Path] = []
        current_paths: list[pathlib.Path] = []
        for fname in cfg["compendium_files"]:
            current = compendia_root / fname
            if not current.exists():
                continue
            current_paths.append(current)
            cached = remote_cache_dir / fname
            if not cached.exists():
                url = f"{base}/compendia/{fname}"
                logger.info("downloading remote compendium %s", url)
                resp = requests.get(url, stream=True, timeout=60)
                if not resp.ok:
                    logger.warning("remote download failed for %s: %s %s",
                                   url, resp.status_code, resp.reason)
                    continue
                with cached.open("wb") as out:
                    for chunk in resp.iter_content(chunk_size=64 * 1024):
                        out.write(chunk)
            remote_paths.append(cached)

        remote_cliques = cliques_from_compendia(remote_paths) if remote_paths else frozenset()
        current_cliques = cliques_from_compendia(current_paths) if current_paths else frozenset()

        remote_with_source = sum(1 for c in remote_cliques if c & source_curies)
        current_with_source = sum(1 for c in current_cliques if c & source_curies)
        current_only = sum(
            1 for c in current_cliques
            if (c & source_curies) and c not in remote_cliques
        )

        summary[st] = {
            "remote_total_cliques": len(remote_cliques),
            "remote_cliques_with_source_curies": remote_with_source,
            "current_cliques_with_source_curies": current_with_source,
            "current_only_with_source_curies": current_only,
        }

    return summary


def _git_commit_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="source_impact_report",
        description="Generate an impact report for adding a new Babel data source.",
    )
    parser.add_argument("--source", required=True,
                        help="Name of the source (matches the basename used in "
                             "intermediate/<type>/{ids,concords}/<name>).")
    parser.add_argument("--semantic-types", default=None,
                        help="Comma-separated list of semantic types to analyse. "
                             "Default: auto-detect from filesystem.")
    parser.add_argument("--mode", choices=("synthetic", "remote", "both"), default="synthetic",
                        help="Comparison mode (default: synthetic).")
    parser.add_argument("--remote-url", default=None,
                        help="Base URL of a previous Babel build (e.g. "
                             "https://stars.renci.org/var/babel/2025dec11/). Required for "
                             "remote/both modes.")
    parser.add_argument("--remote-cache-dir", default="babel_downloads/remote_compendia",
                        help="Where to cache downloaded remote compendia.")
    parser.add_argument("--intermediate-root", default="babel_outputs/intermediate")
    parser.add_argument("--compendia-root", default="babel_outputs/compendia")
    parser.add_argument("--output", default=None,
                        help="Output path for the report. Default: "
                             "docs/sources/<SOURCE>/impact-report.md")
    parser.add_argument("--format", choices=("md", "json", "both"), default="md")
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    intermediate_root = pathlib.Path(args.intermediate_root)
    compendia_root = pathlib.Path(args.compendia_root)

    contribution = discover_source(args.source, intermediate_root)
    if not contribution.by_semantic_type:
        logger.error(
            "no intermediate files found for source %r under %s",
            args.source, intermediate_root,
        )
        return 1

    if args.semantic_types:
        requested = [s.strip() for s in args.semantic_types.split(",") if s.strip()]
        unknown = [s for s in requested if s not in contribution.semantic_types]
        if unknown:
            logger.error("source %r has no files for semantic type(s): %s",
                         args.source, ", ".join(unknown))
            return 1
        semantic_types = requested
    else:
        semantic_types = sorted(contribution.semantic_types)

    if (args.mode in ("remote", "both")) and not args.remote_url:
        logger.error("--remote-url is required for mode=%s", args.mode)
        return 1

    diffs_by_semantic_type: dict[str, SourceImpactDiff] = {}
    if args.mode in ("synthetic", "both"):
        for st in semantic_types:
            if st not in SEMANTIC_TYPE_CONFIG:
                logger.warning(
                    "semantic type %r has no synthetic compute_fn registered; "
                    "skipping clique diff for this type", st,
                )
                continue
            stc = contribution.by_semantic_type[st]
            diffs_by_semantic_type[st] = _compute_synthetic_diff(
                semantic_type=st,
                source_name=args.source,
                intermediate_root=intermediate_root,
                source_curies=stc.all_curies,
            )

    remote_summary: dict[str, dict[str, int]] = {}
    if args.mode in ("remote", "both"):
        remote_summary = _remote_comparison_summary(
            contribution=contribution,
            semantic_types=semantic_types,
            remote_url=args.remote_url,
            remote_cache_dir=pathlib.Path(args.remote_cache_dir),
            compendia_root=compendia_root,
        )

    final_breakdown = _final_compendium_breakdown(contribution, semantic_types, compendia_root)

    generated_at = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    babel_commit = _git_commit_sha()

    md = render_markdown(
        contribution,
        diffs_by_semantic_type,
        final_breakdown,
        mode=args.mode,
        generated_at=generated_at,
        babel_commit=babel_commit,
        remote_url=args.remote_url,
    )
    if remote_summary:
        md = md + _render_remote_section(remote_summary)

    if args.output:
        output_path = pathlib.Path(args.output)
    else:
        output_path = pathlib.Path("docs") / "sources" / args.source / "impact-report.md"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.format in ("md", "both"):
        output_path.write_text(md)
        logger.info("wrote markdown report to %s", output_path)
    if args.format in ("json", "both"):
        json_payload = render_json(
            contribution,
            diffs_by_semantic_type,
            final_breakdown,
            mode=args.mode,
            generated_at=generated_at,
            babel_commit=babel_commit,
            remote_url=args.remote_url,
        )
        if remote_summary:
            payload_obj = json.loads(json_payload)
            payload_obj["remote_summary"] = remote_summary
            json_payload = json.dumps(payload_obj, indent=2, sort_keys=True)
        json_path = output_path.with_suffix(".json")
        json_path.write_text(json_payload)
        logger.info("wrote json report to %s", json_path)

    return 0


def _render_remote_section(remote_summary: dict[str, dict[str, int]]) -> str:
    lines: list[str] = ["", "## 5. Remote comparison summary", ""]
    for st in sorted(remote_summary):
        s = remote_summary[st]
        lines.append(f"### {st}")
        lines.append("")
        lines.append(f"- Remote total cliques (compendia): {s.get('remote_total_cliques', 0):,}")
        lines.append(
            "- Remote cliques containing source CURIEs: "
            f"{s.get('remote_cliques_with_source_curies', 0):,}"
        )
        lines.append(
            "- Current cliques containing source CURIEs: "
            f"{s.get('current_cliques_with_source_curies', 0):,}"
        )
        lines.append(
            "- Cliques with source CURIEs in current but not in remote: "
            f"{s.get('current_only_with_source_curies', 0):,}"
        )
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
