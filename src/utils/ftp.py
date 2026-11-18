"""Download a file atomically over an open, logged-in ftplib.FTP, for src.babel_utils.pull_via_ftp()."""

import hashlib
import os


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
