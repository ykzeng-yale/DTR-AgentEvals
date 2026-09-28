#!/bin/bash
#SBATCH --job-name=dtr030-coder32-infer-a
#SBATCH --account=pi_gt353
#SBATCH --partition=gpu_b200
#SBATCH --qos=normal
#SBATCH --gres=gpu:b200:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=00:30:00
#SBATCH --output=infer-%j.log
set -euo pipefail
trap 'rc=$?; printf "{\"exit_code\":%s}\n" "$rc" > inference_exit.json' EXIT
module load PyTorch/2.9.1-foss-2024a-CUDA-12.8.0
export OMP_NUM_THREADS=8
export PYTHONPATH="$PWD/packages:${PYTHONPATH:-}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HOME="$PWD/hf-cache"
sha256sum -c SHA256SUMS
test -f preparation.json
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
timeout --signal=TERM --kill-after=15s 1700s python coder_infer.py
