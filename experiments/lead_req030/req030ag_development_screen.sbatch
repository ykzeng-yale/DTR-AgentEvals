#!/bin/bash
#SBATCH --job-name=req030ag-dev-screen
#SBATCH --account=pi_gt353
#SBATCH --partition=gpu_b200
#SBATCH --qos=normal
#SBATCH --gres=gpu:b200:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=1-12:00:00
#SBATCH --output=logs/req030ag-%j.out
set -euo pipefail

P=/home/yz2324/project_pi_gt353/yz2324/DTR-AgentEvals
STAGE="$P/staging/req030ag-development-20260930-v4"
CLAIM="$P/claims/req030ag-development-20260930-v4"
RUN=""
RESULT=""
finish() {
  rc=$?
  trap - EXIT
  if [[ -n "$RESULT" && "$RESULT" == "$P/runs/req030ag-development-20260930-v4-"* ]]; then
    rm -rf -- "$RESULT/models" "$RESULT/hf-cache"
  fi
  if [[ -n "$RUN" && -d "$RUN" ]]; then
    printf '{"job_id":"%s","exit_code":%s,"finished_epoch":%s}\n' \
      "$SLURM_JOB_ID" "$rc" "$(date +%s)" > "$RUN/job_exit.json.tmp"
    mv "$RUN/job_exit.json.tmp" "$RUN/job_exit.json"
  fi
  exit "$rc"
}
trap finish EXIT

cd "$P"
mkdir -p "$P/runs" "$P/claims"
if ! mkdir -m 700 "$CLAIM"; then
  echo "DTR_REQ030AG_DUPLICATE_CLAIM_REFUSED" >&2
  exit 90
fi
printf '{"job_id":"%s","host":"%s","started_epoch":%s}\n' \
  "$SLURM_JOB_ID" "$(hostname)" "$(date +%s)" > "$CLAIM/owner.json"
RUN="$P/runs/req030ag-development-20260930-v4-$SLURM_JOB_ID"
mkdir -m 700 "$RUN"
RESULT="$RUN/results/job-$SLURM_JOB_ID"
mkdir -m 700 "$RUN/results"

cd "$STAGE"
sha256sum -c payload.sha256
RELEASE_SHA=$(cat release.sha256)
[[ "$RELEASE_SHA" =~ ^[0-9a-f]{64}$ ]]
mkdir -m 700 "$RUN/payload"
tar -xzf payload.tar.gz -C "$RUN/payload"

module load PyTorch/2.9.1-foss-2024a-CUDA-12.8.0
export OMP_NUM_THREADS=8
export PYTHONUNBUFFERED=1
CODER=/home/yz2324/project_pi_gt353/yz2324/DTR-AgentEvals/req030-coder32-deploy-20260928-c
[[ -d "$CODER/packages" && -d "$CODER/wheels" ]]
export PYTHONPATH="$RUN/payload:$CODER/packages${PYTHONPATH:+:$PYTHONPATH}"
export DTR_CODER_WHEELS="$CODER/wheels"
export HF_HOME="$RESULT/hf-cache"
export HF_HUB_DISABLE_TELEMETRY=1
export TOKENIZERS_PARALLELISM=false
export APPTAINER="$(command -v apptainer)"
test -x "$APPTAINER"
ulimit -f 167772160
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv > "$RUN/gpu_inventory.csv"

BUNDLE="$RUN/payload/work/req030ag_screen_20260930_v4"
RELEASE="$BUNDLE/manifest.json"
timeout --signal=TERM --kill-after=60s 35h python -m experiments.lead_req030.req030ag_screen \
  --bundle "$BUNDLE" --release "$RELEASE" --release-sha256 "$RELEASE_SHA" \
  --run-root "$RESULT" \
  --wheel-manifest "$RUN/payload/experiments/lead_req030/coder_c_wheels.json" \
  --wheel-root "$DTR_CODER_WHEELS"
