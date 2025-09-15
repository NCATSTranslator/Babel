#!/usr/bin/env bash

#
# rsync-to-server.sh - use rsync to copy the necessary files to another server.
#
# SYNOPSIS
#   bash rsync-to-server.sh username@ssh.server.org:/location/to/write/to

rsync -avP --exclude 'babel_outputs/duckdb' babel_outputs/ "$1"
