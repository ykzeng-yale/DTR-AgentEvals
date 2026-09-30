#!/bin/bash
#SBATCH --job-name=req030ag-gitdiag
#SBATCH --account=pi_gt353
#SBATCH --partition=day
#SBATCH --qos=normal
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --output=logs/req030ag-gitdiag-%j.out
set -euo pipefail

P=/home/yz2324/project_pi_gt353/yz2324/DTR-AgentEvals
STAGE="$P/staging/req030ag-image-git-diagnostic-20260930-a"
CLAIM="$P/claims/req030ag-image-git-diagnostic-20260930-a"
V5="$P/runs/req030ag-development-20260930-v5-27928205"
RUN=""
finish() {
  rc=$?
  trap - EXIT
  if [[ -n "$RUN" && -d "$RUN" ]]; then
    printf '{"job_id":"%s","exit_code":%s,"finished_epoch":%s}\n' \
      "$SLURM_JOB_ID" "$rc" "$(date +%s)" > "$RUN/job_exit.json.tmp"
    mv "$RUN/job_exit.json.tmp" "$RUN/job_exit.json"
  fi
  exit "$rc"
}
trap finish EXIT

mkdir -p "$P/claims" "$P/runs"
if ! mkdir -m 700 "$CLAIM"; then
  echo "DTR_REQ030AG_IMAGE_GIT_DIAGNOSTIC_DUPLICATE_REFUSED" >&2
  exit 90
fi
RUN="$P/runs/req030ag-image-git-diagnostic-20260930-a-$SLURM_JOB_ID"
mkdir -m 700 "$RUN"
test -d "$STAGE"
test -d "$V5/results/job-27928205/images"
test -f "$V5/payload/work/req030ag_screen_20260930_v5/manifest.json"

module load PyTorch/2.9.1-foss-2024a-CUDA-12.8.0
python3 "$STAGE/req030ag_image_git_diagnostic.py" \
  --manifest "$V5/payload/work/req030ag_screen_20260930_v5/manifest.json" \
  --images "$V5/results/job-27928205/images" \
  --output "$RUN/diagnostic.json"
