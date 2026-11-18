"""FTP helpers shared by the downloaders: checking whether a path exists, and downloading a file atomically.

These take an open, logged-in ftplib.FTP, so a caller that needs several files makes one connection.
src.babel_utils.pull_via_ftp() downloads through retrieve_ftp_file(), as does src.datahandlers.mesh.
"""

import ftplib
import hashlib
import os
import posixpath


def _basenames(ftp, ftpdir) -> set[str]:
    """Return the names in ftpdir. Servers differ on whether NLST returns bare names or full paths."""
    return {posixpath.basename(name.rstrip("/")) for name in ftp.nlst(ftpdir)}


def ftp_path_exists(ftp, path) -> bool:
    """Return True if the absolute path (a file or a directory) exists on the FTP server.

    Decided by listing each parent directory and looking for the next component in it, starting from "/",
    rather than by interpreting the server's error for a missing path. Servers word and code that error
    differently: NLM's ftp.nlm.nih.gov answers NLST of a missing directory with "450 ...: No such file or
    directory", which ftplib raises as a *temporary* error, but CWD to one with a 550, a permanent one. A
    transient failure of one of the listings is raised rather than read as "absent", so it can never send a
    caller down its fallback path.
    """
    if not path.startswith("/"):
        raise ValueError(f"ftp_path_exists() needs an absolute path, got {path!r}")
    parent = "/"
    for component in [c for c in path.split("/") if c]:
        if component not in _basenames(ftp, parent):
            return False
        parent = posixpath.join(parent, component)
    return True


def list_ftp_dir(ftp, ftpdir) -> set[str]:
    """Return the names in the absolute directory ftpdir, or an empty set if it does not exist (ftp_path_exists())."""
    if not ftp_path_exists(ftp, ftpdir):
        return set()
    return _basenames(ftp, ftpdir)


def retrieve_ftp_file(ftp, ftpfile, out_path) -> str:
    """Download ftpfile (relative to ftp's working directory, or absolute) to out_path; return its SHA-1 hex digest.

    Writes to out_path.part and renames it to out_path only once the transfer completes, so an interrupted
    download never leaves a partial file under the name a later run (or a Snakemake rerun) checks for. The
    SHA-1 is computed as the bytes arrive, so a caller that verifies or records it need not read the file again.
    """
    part_path = f"{out_path}.part"
    sha1 = hashlib.sha1()
    try:
        with open(part_path, "wb") as outf:

            def write_chunk(chunk):
                sha1.update(chunk)
                outf.write(chunk)

            ftp.retrbinary(f"RETR {ftpfile}", write_chunk)
        os.replace(part_path, out_path)
    finally:
        if os.path.exists(part_path):
            os.remove(part_path)
    return sha1.hexdigest()


def ftp_modified_time(ftp, ftpfile):
    """Return ftpfile's modification time on the FTP server as an ISO 8601 UTC string, or None if not reported."""
    try:
        response = ftp.sendcmd(f"MDTM {ftpfile}")  # "213 YYYYMMDDHHMMSS", in UTC (RFC 3659)
    except ftplib.all_errors:
        return None
    stamp = response.split()[-1]
    if not (response.startswith("213") and len(stamp) >= 14 and stamp[:14].isdigit()):
        return None
    return f"{stamp[0:4]}-{stamp[4:6]}-{stamp[6:8]}T{stamp[8:10]}:{stamp[10:12]}:{stamp[12:14]}Z"
