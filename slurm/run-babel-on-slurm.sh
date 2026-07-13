#!/bin/bash

sbatch <<EOF
#!/bin/bash
#SBATCH --job-name=babel-${BABEL_VERSION:-current}
#SBATCH --output=babel_outputs/logs/sbatch-${BABEL_VERSION:-babel-current}.out
#SBATCH --error=babel_outputs/logs/sbatch-${BABEL_VERSION:-babel-current}.err
#SBATCH --time=${BABEL_TIMEOUT:-24:00:00}
#SBATCH --mem=16G
#SBATCH --nodes=1
#SBATCH --chdir=$PWD

# Notes:
# --chdir: Change the directory to whatever directory the sbatch job was
#          started from. So you should run: BABEL_VERSION=babel-1.14 bash slurm/run-babel-on-slurm.sh

source ~/.bashrc

# UV likes setting up a local .venv with the packages hardlinked in, but on Hatteras, project directories are on
# their own partitions and you can't create hardlinks across partition boundaries. So all Babel runs on Hatteras
# share a UV cache on their own partition.
export UV_CACHE_DIR="/projects/babel/runs/uv-cache/"

# Run Babel in a distributed fashion as defined in slurm/config.yaml profile
#
# Note that since Snakemake supports slurm executor plugin natively, submitting this as a SLURM batch
# job is not recommended since that will create an outer SLURM job running Snakemake which then
# submits inner SLURM jobs for workflow rules as specified in the profile. The recommended way
# is to run this directly on the login or head node. However, it might not be a good thing to have
# a long-running process on login/head nodes. So a good compromise is to still use the sbatch wrapper
# to submit the snakemake job but request minimal resources for the outer job as shown in this job script.

uv run snakemake --slurm-jobname-prefix "${BABEL_VERSION:-babel-current}" --profile slurm $@
snakemake_exit=\$?

if [ \$snakemake_exit -ne 0 ]; then
    report=babel_outputs/logs/error-report-${BABEL_VERSION:-babel-current}.md
    if uv run babel-slurm-errors ${BABEL_VERSION:-babel-current} --markdown > "\$report"; then
        echo "Error report written to \$report" >&2
    else
        echo "Warning: error report generation failed (exit \$?); partial output may be in \$report" >&2
    fi
fi

exit \$snakemake_exit

EOF
