"""``babel-check-concords`` — would any row of these concords fail Babel's concord parser?

Every concord reader in the build goes through :func:`src.model.intermediates.parse_concord_line`, which
raises on a row that isn't three non-empty, unpadded, tab-separated columns. Run this before
tightening that parser, or before trusting a set of concords from somewhere else, to find out
which rows would fail -- without waiting hours for a compendium rule to find the first one.

Each target is a concord file, a local directory (every file under a ``concords/`` directory in or
beneath it, skipping the metadata sidecars the DuckDB export also skips), or an ``http(s)://`` URL
of a file or a directory listing, which is crawled the same way and streamed rather than
downloaded::

    uv run babel-check-concords babel_outputs/intermediate
    uv run babel-check-concords https://stars.renci.org/var/babel/2025dec11/intermediate/

Prints one tab-separated line per file (``file``, ``rows``, ``rejected``, ``reasons``) and, for each
file with rejects, the first rejected line of each kind. Exits 1 if any row was rejected.
"""

import argparse
import io
import pathlib
import re
import sys
import urllib.parse
import urllib.request

from src.model.intermediates import CONCORD_ENCODING, is_metadata_sidecar, scan_concord_lines
from src.util import get_logger

logger = get_logger(__name__)

# Seconds before a stalled HTTP read gives up. Generous because the largest published concords are
# several GB and a directory listing on stars.renci.org can be slow to start.
HTTP_TIMEOUT_SECONDS = 300

# An href in an nginx/Apache autoindex page: relative, not a self or parent link or a sort query.
# find_remote_concords() also refuses to revisit a listing or leave the one it started from, so a
# link this misses can't make the crawl loop.
_HREF = re.compile(r'href="(?!\.\.?/|\?|/|https?:)([^"]+)"')


def _is_concord_name(path: str) -> bool:
    """True for a file inside a ``concords/`` directory that isn't a metadata sidecar.

    ``path`` must be the whole path (an absolute local path or a URL's path), not one relative to
    the target: a target such as ``.../concords/UNICHEM`` has no ``concords`` component below it.
    """
    parts = path.split("/")
    return "concords" in parts[:-1] and not is_metadata_sidecar(parts[-1])


def find_local_concords(target: pathlib.Path) -> list[pathlib.Path]:
    """A file is checked as given; a directory is searched for files under ``concords/``."""
    if target.is_file():
        return [target]
    return sorted(p for p in target.rglob("*") if p.is_file() and _is_concord_name(p.absolute().as_posix()))


def find_remote_concords(url: str) -> list[str]:
    """A URL not ending in ``/`` is a file; one ending in ``/`` is a directory listing to crawl."""
    if not url.endswith("/"):
        return [url]
    found = []
    pending = [url]
    seen = {url}
    while pending:
        listing_url = pending.pop()
        with urllib.request.urlopen(listing_url, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            listing = resp.read().decode("utf-8")
        for href in _HREF.findall(listing):
            child = urllib.parse.urljoin(listing_url, href)
            if href.endswith("/"):
                # Only descend: a link back to this listing, or anywhere outside it, would loop.
                if child.startswith(listing_url) and child not in seen:
                    seen.add(child)
                    pending.append(child)
            elif _is_concord_name(urllib.parse.urlparse(child).path):
                found.append(child)
    return sorted(found)


def scan_target(name: str):
    """Scan one local path or URL, streaming it line by line."""
    if name.startswith(("http://", "https://")):
        with urllib.request.urlopen(name, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            return scan_concord_lines(io.TextIOWrapper(resp, encoding=CONCORD_ENCODING), name)
    with open(name, encoding=CONCORD_ENCODING) as inf:
        return scan_concord_lines(inf, name)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("targets", nargs="+", help="Concord files, directories, or http(s) URLs.")
    args = parser.parse_args(argv)

    files = []
    empty_targets = []
    for target in args.targets:
        if target.startswith(("http://", "https://")):
            found = find_remote_concords(target)
        else:
            found = [str(p) for p in find_local_concords(pathlib.Path(target))]
        if not found:
            empty_targets.append(target)
        files.extend(found)
    if empty_targets:
        # Checking nothing must not look like a clean result -- including for one target of several,
        # such as a mistyped or not-yet-built directory next to a valid concord.
        raise RuntimeError(f"No concord files found under {empty_targets}")

    print("file\trows\trejected\treasons")
    total_rows = total_rejected = 0
    for name in files:
        logger.info("scanning %s", name)
        scan = scan_target(name)
        total_rows += scan.rows
        total_rejected += scan.rejected
        reasons = ", ".join(f"{reason}: {count}" for reason, count in scan.rejects.most_common())
        print(f"{name}\t{scan.rows}\t{scan.rejected}\t{reasons}", flush=True)
        for reason, (line_number, line) in scan.examples.items():
            print(f"#   first '{reason}' at line {line_number}: {line!r}", flush=True)
    print(f"# {len(files)} files, {total_rows} rows, {total_rejected} rejected")
    return 1 if total_rejected else 0


if __name__ == "__main__":
    sys.exit(main())
