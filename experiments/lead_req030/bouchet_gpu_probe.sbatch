#!/bin/bash
#SBATCH --job-name=dtr030-gpu-probe-a
#SBATCH --account=pi_gt353
#SBATCH --partition=gpu_b200
#SBATCH --qos=normal
#SBATCH --gres=gpu:b200:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:10:00
#SBATCH --output=slurm-%j.log
set -euo pipefail
module load PyTorch/2.9.1-foss-2024a-CUDA-12.8.0
export OMP_NUM_THREADS=4
sha256sum -c SHA256SUMS
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
python bouchet_gpu_probe.py
