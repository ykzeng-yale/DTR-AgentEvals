#!/bin/bash
#SBATCH --job-name=dtr030-coder32-prepare-c
#SBATCH --account=pi_gt353
#SBATCH --partition=day
#SBATCH --qos=normal
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:10:00
#SBATCH --output=prepare-%j.log
set -euo pipefail
trap 'rc=$?; printf "{\"exit_code\":%s}\n" "$rc" > prepare_exit.json' EXIT
module load PyTorch/2.9.1-foss-2024a-CUDA-12.8.0
export OMP_NUM_THREADS=4
export PIP_NO_CACHE_DIR=1
export HF_HOME="$PWD/hf-cache"
sha256sum -c SHA256SUMS
timeout --signal=TERM --kill-after=15s 500s python coder_c_prepare.py
