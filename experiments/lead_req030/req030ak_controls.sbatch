#!/bin/bash
#SBATCH --job-name=req030ak-controls
#SBATCH --account=pi_gt353
#SBATCH --partition=day
#SBATCH --qos=normal
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=08:00:00
#SBATCH --output=logs/req030ak-%j.out
set -euo pipefail
umask 077
P=/home/yz2324/project_pi_gt353/yz2324/DTR-AgentEvals
ID=req030ak-controls-20260930-a
STAGE="$P/staging/$ID"
CLAIM="$P/claims/$ID"
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
cd "$P"
mkdir -p claims runs
mkdir -m 700 "$CLAIM" || { echo DTR_DUPLICATE_CLAIM_REFUSED >&2; exit 90; }
printf '{"job_id":"%s","started_epoch":%s}\n' "$SLURM_JOB_ID" "$(date +%s)" > "$CLAIM/owner.json"
RUN="$P/runs/$ID-$SLURM_JOB_ID"
mkdir -m 700 "$RUN"
cd "$STAGE"
sha256sum -c payload.sha256
RELEASE_SHA=$(cat release.sha256)
[[ "$RELEASE_SHA" =~ ^[0-9a-f]{64}$ ]]
module load Python/3.12.3-GCCcore-13.3.0
python - "$RUN" <<'PY'
import sys, tarfile
from pathlib import PurePosixPath
with tarfile.open('payload.tar.gz', 'r:gz') as archive:
    members = archive.getmembers()
    for item in members:
        p = PurePosixPath(item.name)
        assert p.parts[0] == 'payload' and not p.is_absolute() and '..' not in p.parts
        assert item.isfile() or item.isdir()
    assert len(members) < 100 and sum(x.size for x in members) < 20 * 1024 * 1024
    archive.extractall(sys.argv[1], members=members, filter='data')
PY
export PYTHONPATH="$RUN/payload"
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=4
export APPTAINER_CACHEDIR="$RUN/apptainer-cache"
# The Python owner verifies this allocation's /tmp ext4/xfs capacity and creates
# an exclusive 0700 build tree. Never use a project/network build-temp fallback.
mkdir -m 700 "$APPTAINER_CACHEDIR"
# Bash ulimit -f uses 1024-byte blocks: 8 GiB per file, independently of
# the Python guard's 80 GiB sampled private-directory limit.
ulimit -f 8388608
python - "$RUN/file_limit.json" <<'PY'
import json, resource, sys
limits = resource.getrlimit(resource.RLIMIT_FSIZE)
assert limits[0] == 8 * 1024**3
with open(sys.argv[1], 'x') as stream:
    json.dump({'rlimit_fsize_soft': limits[0], 'rlimit_fsize_hard': limits[1]}, stream)
PY
cd "$RUN/payload"
python --version > "$RUN/python_version.txt"
BUNDLE="$RUN/payload/work/req030ah_controls_20260930_a"
timeout --signal=TERM --kill-after=30s 27500 python -m experiments.lead_req030.req030ak_controls \
  --bundle "$BUNDLE" --release "$BUNDLE/release.json" --release-sha256 "$RELEASE_SHA" \
  --output "$RUN/results"
