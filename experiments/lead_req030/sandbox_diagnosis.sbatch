#!/bin/bash
#SBATCH --job-name=dtr030-sandbox-diagnosis-a
#SBATCH --account=pi_gt353
#SBATCH --partition=day
#SBATCH --qos=normal
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --output=slurm-%j.log
set -euo pipefail
trap 'rc=$?; printf "{\"exit_code\":%s}\n" "$rc" > exit.json' EXIT
module load PyTorch/2.9.1-foss-2024a-CUDA-12.8.0
export OMP_NUM_THREADS=2
export PYTHONPATH="$PWD/../req030-coder32-deploy-20260928-c/packages:${PYTHONPATH:-}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
sha256sum -c SHA256SUMS
timeout --kill-after=15s 120s python deployment_replay.py
old="$PWD/../req030-sandbox-preflight-20260928-a"
(cd "$old" && sha256sum -c image.sha256)
# Diagnose original failure with fixed authored probes; no model output execution.
timeout --kill-after=15s 60s apptainer exec --containall --cleanenv --no-home --no-mount hostfs,bind-paths --net --network none --pwd / "$old/probe.sif" /bin/sh -c '
for p in /home/yz2324 /nfs/roberts /var/run/docker.sock; do
 if test -e "$p"; then echo "EXISTS $p"; if test -d "$p"; then ls -A "$p" | wc -l; fi; else echo "ABSENT $p"; fi
done
printf "NETWORK_INTERFACES\n"; ls /sys/class/net
printf "MOUNTS\n"; cat /proc/self/mountinfo
' > diagnosis.txt
