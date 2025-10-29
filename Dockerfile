# Dockerfile for building a Babel image.

# Let's pick up the latest Debian-based Python image.
FROM python:3.11

# Configuration options:
# - ${ROOT} is where Babel source code will be copied.
ARG ROOT=/code/babel
# - ${CORES} is the default number of cores to use.
ARG CORES=5

# Upgrade system files.
RUN apt update
RUN apt -y upgrade

# Install or upgrade some prerequisite packages.
RUN apt install -y gcc
RUN apt install -y git

# Some day we will be able to install uv directly on Debian, and then this will be redundant.
RUN apt install -y pipx

# The following packages are useful in debugging runs
# of this software on a Kubernetes cluster, but can
# be removed if not needed.
RUN apt-get install -y htop
RUN apt-get install -y screen
RUN apt-get install -y vim
RUN apt-get install -y rsync
RUN apt-get install -y jq

# Create a non-root-user.
RUN adduser --home ${ROOT} --uid 1000 nru

# Set up a $ROOT directory with the source code to work in.
RUN mkdir -p ${ROOT}
WORKDIR ${ROOT}
USER nru
COPY --chown=nru . ${ROOT}

# Install and run `uv sync` to install packages.
RUN pipx install uv
ENV PATH="${ROOT}/.local/bin:${PATH}"
RUN uv sync

# Our default entrypoint is to start the Babel run.
ENTRYPOINT ["bash", "-c", "uv run snakemake --cores ${CORES}"]
