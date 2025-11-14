#!/bin/bash

sbatch <<EOF
#!/bin/bash
#SBATCH --job-name=babel-${BABEL_VERSION:-current}
#SBATCH --output=babel_outputs/sbatch-babel-${BABEL_VERSION:-current}.out
#SBATCH --time=${BABEL_TIMEOUT:-1:00:00}
#SBATCH --mem=2G
#SBATCH -n 1
#SBATCH --chdir=$PWD

# Notes:
# --chdir: Change the directory to whatever directory the sbatch job was
#          started from. So you should run `sbatch slurm/jobs/run_babel.job`.

source ~/.bashrc

# Build anatomy related compendia in a distributed fashion as defined in slurm/config.yaml profile 
# Note that since Snakemake supports slurm executor plugin natively, submitting this as a SLURM batch 
# job is not recommended since that will create an outer SLURM job running Snakemake which then 
# submits innter SLURM jobs for workflow rules as specified in the profile. The recommended way 
# is to run this directly on the login or head node. However, it might not be a good thing to have 
# a long-running process on login/head nodes. So a good compromise is to still use the sbatch wrapper 
# to submit the snakemake job but request minimal resources for the outer job as shown in this job script.
uv run snakemake --profile slurm anatomy
EOF
