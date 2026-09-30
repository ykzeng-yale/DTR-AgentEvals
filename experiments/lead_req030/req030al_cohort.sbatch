#!/bin/bash
#SBATCH --job-name=req030al-sixhour
#SBATCH --account=pi_gt353
#SBATCH --partition=gpu_devel
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --gres=gpu:rtx_pro_6000_blackwell:2
#SBATCH --cpus-per-task=12
#SBATCH --mem=256G
#SBATCH --time=05:15:00
#SBATCH --output=logs/req030al-%j.out
set -euo pipefail
umask 077
P=/home/yz2324/project_pi_gt353/yz2324/DTR-AgentEvals
ID=req030al-sixhour-20260930-a
STAGE="$P/staging/$ID"
RUN="$P/runs/$ID"
CLAIM="$P/claims/$ID"
GOAL_DEADLINE=1790821891
finish() {
  rc=$?
  trap - EXIT
  if [[ -d "$RUN" ]]; then
    printf '{"job_id":"%s","exit_code":%s,"finished_epoch":%s}\n' \
      "$SLURM_JOB_ID" "$rc" "$(date +%s)" > "$RUN/job_exit.json.tmp"
    mv "$RUN/job_exit.json.tmp" "$RUN/job_exit.json"
  fi
  exit "$rc"
}
trap finish EXIT
cd "$P"
mkdir -p claims runs logs
mkdir -m 700 "$CLAIM" || { echo DTR_DUPLICATE_CLAIM_REFUSED >&2; exit 90; }
printf '{"job_id":"%s","started_epoch":%s}\n' "$SLURM_JOB_ID" "$(date +%s)" > "$CLAIM/owner.json"
mkdir -m 700 "$RUN"
mkdir -m 700 "$RUN/models"
REMAINING=$(( GOAL_DEADLINE - $(date +%s) - 60 ))
(( REMAINING > 0 )) || { echo DTR_GOAL_DEADLINE_EXPIRED >&2; exit 91; }
(( REMAINING < 18900 )) || REMAINING=18900
cd "$STAGE"
sha256sum -c payload.sha256
sha256sum -c source.sha256
RELEASE_SHA=$(cat release.sha256)
[[ "$RELEASE_SHA" =~ ^[0-9a-f]{64}$ ]]
module load PyTorch/2.9.1-foss-2024a-CUDA-12.8.0
CODER="$P/req030-coder32-deploy-20260928-c"
[[ -d "$CODER/packages" && -d "$CODER/wheels" ]]
export PYTHONPATH="$STAGE/payload:$CODER/packages${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=6
export MKL_NUM_THREADS=6
export OPENBLAS_NUM_THREADS=6
export PYTHONHASHSEED=0
export DTR_CODER_WHEELS="$CODER/wheels"
export HF_HOME="$RUN/hf-cache"
export HF_HUB_DISABLE_TELEMETRY=1
export TOKENIZERS_PARALLELISM=false
export APPTAINER="$(command -v apptainer)"
test -x "$APPTAINER"
ulimit -f 16777216
nvidia-smi --query-gpu=uuid,name,memory.total,driver_version --format=csv > "$RUN/gpu_inventory.csv"
printf '{"job_id":"%s","started_epoch":%s,"goal_deadline_epoch":%s,"outer_seconds":%s,"cuda_visible_devices":"%s"}\n' \
  "$SLURM_JOB_ID" "$(date +%s)" "$GOAL_DEADLINE" "$REMAINING" "${CUDA_VISIBLE_DEVICES:-}" > "$RUN/start.json"
cd "$STAGE/payload"
timeout --signal=TERM --kill-after=30s "$REMAINING" python -m experiments.lead_req030.req030al_cohort run \
  --release "$STAGE/payload/configs/req030al_cohort_20260930.json" \
  --release-sha256 "$RELEASE_SHA" --output "$RUN/results"
