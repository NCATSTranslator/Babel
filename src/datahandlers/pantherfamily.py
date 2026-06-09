import ftplib
import os
import urllib.error
import urllib.request

from src.babel_utils import get_config, get_user_agent, pull_via_ftp
from src.metadata.provenance import write_metadata
from src.prefixes import PANTHERFAMILY
from src.util import get_logger

logger = get_logger(__name__)

FTP_HOST = "ftp.pantherdb.org"
FTP_DIR = "/sequence_classifications/current_release/PANTHER_Sequence_Classification_files/"
FTP_FILE = "PTHR19.0_human"
HTTP_BASE = (
    "http://data.pantherdb.org/ftp/sequence_classifications/current_release/PANTHER_Sequence_Classification_files/"
)


def pull_pantherfamily():
    outfile = f"{PANTHERFAMILY}/family.csv"
    config = get_config()
    ofilename = os.path.join(config["download_directory"], outfile)

    try:
        pull_via_ftp(FTP_HOST, FTP_DIR, FTP_FILE, outfilename=outfile)
        return
    except (ftplib.Error, OSError, EOFError, TimeoutError) as e:
        logger.warning(f"FTP download from {FTP_HOST} failed ({e}); falling back to HTTP mirror.")

    http_url = HTTP_BASE + FTP_FILE
    logger.info(f"Downloading {http_url} → {ofilename}")
    os.makedirs(os.path.dirname(ofilename), exist_ok=True)
    req = urllib.request.Request(http_url, headers={"User-Agent": get_user_agent()})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp, open(ofilename, "wb") as outf:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                outf.write(chunk)
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(
            f"Both FTP and HTTP downloads failed for PANTHER family file.\n"
            f"  URL: {http_url}\n"
            f"  Local path: {ofilename}\n"
            f"  To download manually: wget '{http_url}' -O '{ofilename}'"
        ) from e


def pull_labels(infile, outfile, metadata_yaml):
    SUBFAMILY_COLUMN = 3
    MAINFAMILY_NAME_COLUMN = 4
    SUBFAMILY_NAME_COLUMN = 5
    done = set()
    with open(infile) as inf, open(outfile, "w") as labelf:
        for raw_line in inf:
            line = raw_line.strip()
            parts = line.split("\t")
            if len(parts) < 5:
                continue
            sf = parts[SUBFAMILY_COLUMN]
            mf = sf.split(":")[0]  # PTHR10845:SF155 -> PTHR10845
            mfname = parts[MAINFAMILY_NAME_COLUMN]  # REGULATOR OF G PROTEIN SIGNALING
            sfname = parts[SUBFAMILY_NAME_COLUMN]  # REGULATOR OF G-PROTEIN SIGNALING 18
            if mf not in done:
                main_family = f"{PANTHERFAMILY}:{mf}"
                # panther_families.append(main_family)
                # labels[main_family]=mfname
                labelf.write(f"{main_family}\t{mfname}\n")
                done.add(mf)
            if sf not in done:
                sub_family = f"{PANTHERFAMILY}:{sf}"
                # panther_families.append(sub_family)
                # labels[sub_family]=sfname
                labelf.write(f"{sub_family}\t{sfname}\n")
                done.add(sf)

    write_metadata(
        metadata_yaml,
        typ="transform",
        name="pantherfamily.pull_labels()",
        description="Main families and subfamily labels extracted from PANTHER Sequence Classification human.",
        sources=[
            {
                "type": "download",
                "name": "PANTHER Sequence Classification: Human",
                "url": "ftp://ftp.pantherdb.org/sequence_classifications/current_release/PANTHER_Sequence_Classification_files/PTHR19.0_human",
            }
        ],
    )
