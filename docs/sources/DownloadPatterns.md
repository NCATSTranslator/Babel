# Source Download Patterns

This file documents recurring patterns and trade-offs that appear across multiple data handlers in
`src/datahandlers/`. Prefer adding source-specific notes to that source's own directory; put
guidance here only when the same pattern applies to several sources.

## HTTP directory listing vs FTP for file discovery

Several upstream sources (EBI FTP, NCBI FTP, etc.) expose their file listings both as a native FTP
service and as an HTTP mirror whose URLs look like
`https://ftp.example.org/pub/databases/source/current/`.

**Current approach in Babel** — when a handler only needs to discover which files exist in a
directory and then download them, we parse the HTTP directory listing rather than connecting via
FTP. `src/datahandlers/complexportal.py` is the canonical example: `_DirectoryListingParser`
scrapes `<a href>` tags from the Apache autoindex page to enumerate TSV filenames, and then
`pull_via_urllib` downloads each file over HTTPS.

**Why HTTP over FTP for the actual download** — FTP connections can stall or time out on large
files, especially through firewalls and NAT. HTTPS is more reliable for multi-hundred-megabyte
transfers.

**Why HTTP listing instead of FTP `NLST`/`MLSD`** — EBI's autoindex format has been stable for
years and the parser is a handful of lines. `ftplib` adds a second protocol dependency and
occasional auth/passive-mode headaches. The risk is that EBI (or another host) switches to a
different listing format (e.g. Nginx JSON autoindex, a JavaScript SPA) and the parser silently
returns an empty list. The existing `fetch_complexportal_tsv_filenames()` guard (`if not
tsv_filenames: raise RuntimeError(...)`) catches this immediately at runtime.

**If the HTML listing breaks** — switch `fetch_complexportal_tsv_filenames()` (and equivalent
functions in other handlers) to use `ftplib.FTP.nlst()` or `MLSD` for discovery while keeping
`pull_via_urllib` for the actual download. That combination gives structured directory listings
without sacrificing download reliability. The FTP URL for EBI is
`ftp.ebi.ac.uk/pub/databases/intact/complex/current/complextab/`.

**When to prefer FTP listing from the start** — if the HTTP mirror does not serve an Apache-style
autoindex (no `<a href>` links to files), use FTP `NLST`/`MLSD` for discovery instead.
