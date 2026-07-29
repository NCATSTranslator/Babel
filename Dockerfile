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
RUN apt-get install -y ripgrep

# Create a non-root-user.
RUN adduser --home ${ROOT} --uid 1000 nru

# Set up a $ROOT directory with the source code to work in.
RUN mkdir -p ${ROOT}
WORKDIR ${ROOT}

# Rust toolchain — required because the build backend is maturin, which compiles a native
# extension on every `uv sync`. Installed via rustup rather than `apt install cargo`: Debian
# bookworm ships cargo 1.63, which is *exactly* pyo3 0.23's minimum, so the next pyo3 bump would
# break this image with an error that reads as unrelated. rustup also honours rust-toolchain.toml,
# which apt's cargo ignores.
ENV RUSTUP_HOME=/usr/local/rustup CARGO_HOME=/usr/local/cargo
ENV PATH=${CARGO_HOME}/bin:${PATH}
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
    | sh -s -- -y --no-modify-path --profile minimal --default-toolchain stable \
    && chmod -R a+rX ${RUSTUP_HOME} ${CARGO_HOME}

USER nru
COPY --chown=nru . ${ROOT}

# Install and run `uv sync` to install packages.
RUN pipx install uv
ENV PATH="${ROOT}/.local/bin:${PATH}"
RUN uv sync

# Our default entrypoint is to start the Babel run.
ENTRYPOINT ["bash", "-c", "uv run snakemake --cores ${CORES}"]
