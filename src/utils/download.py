"""Atomic, hashed downloads, shared by pull_via_ftp() in src.babel_utils and the MeSH HTTPS downloader."""

import hashlib
import os
from contextlib import contextmanager


@contextmanager
def atomic_hashed_write(out_path):
    """Yield ``(write, sha1)`` for saving a download to out_path.

    write(chunk) appends chunk to out_path.part and adds it to sha1, so a caller that verifies or records the SHA-1
    need not read the file again. out_path.part is renamed to out_path only if the with block exits cleanly, and is
    removed otherwise, so an interrupted or rejected download (raise inside the block to reject one) never leaves a
    partial file under the name a later run, or a Snakemake rerun, checks for.
    """
    part_path = f"{out_path}.part"
    sha1 = hashlib.sha1()
    try:
        with open(part_path, "wb") as outf:

            def write(chunk):
                sha1.update(chunk)
                outf.write(chunk)

            yield write, sha1
        os.replace(part_path, out_path)
    finally:
        if os.path.exists(part_path):
            os.remove(part_path)


def retrieve_ftp_file(ftp, ftpfile, out_path) -> str:
    """Download ftpfile (relative to ftp's working directory, or absolute) to out_path; return its SHA-1 hex digest.

    ftp is an open, logged-in ftplib.FTP. The file is written through atomic_hashed_write().
    """
    with atomic_hashed_write(out_path) as (write, sha1):
        ftp.retrbinary(f"RETR {ftpfile}", write)
    return sha1.hexdigest()
