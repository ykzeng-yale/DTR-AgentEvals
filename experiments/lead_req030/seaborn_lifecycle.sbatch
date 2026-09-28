#!/bin/bash
#SBATCH --job-name=dtr030-lifecycle-a
#SBATCH --account=pi_gt353
#SBATCH --partition=day
#SBATCH --qos=normal
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:05:00
#SBATCH --output=slurm-%j.log
set -euo pipefail
umask 077
trap 'rc=$?; printf "{\"exit_code\":%s}\n" "$rc" > exit.json' EXIT
sha256sum -c SHA256SUMS
timeout --kill-after=15s 180s python3 seaborn_lifecycle.py
