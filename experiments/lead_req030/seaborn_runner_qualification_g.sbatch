#!/bin/bash
# REQ030AD: corrected inert runner integration qualification; no weights/evaluator data.
#SBATCH --job-name=dtr030-seaborn-join-g
#SBATCH --account=pi_gt353
#SBATCH --partition=devel
#SBATCH --qos=normal
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=slurm-%j.log
set -euo pipefail
umask 077
trap 'rc=$?; printf "{\"exit_code\":%s}\n" "$rc" > exit.json' EXIT

P=/home/yz2324/project_pi_gt353/yz2324/DTR-AgentEvals
RUN="$P/req030-seaborn-runner-qualification-20260929-g"
SIF="$P/req030-seaborn-image-20260928-a/task.sif"
SEED="$P/req030-seaborn-bound-workspace-20260928-b/workspace.img"
CODER="$P/req030-coder32-deploy-20260928-c"
test "$PWD" = "$RUN"
test ! -e qualification.claim
touch qualification.claim
sha256sum -c release.SHA256SUMS
printf '%s  %s\n' 9da1f51cb8c01a6ad9e0db4d1969742fbec995021e78150a9623d4f4719a8a47 "$SIF" | sha256sum -c -
printf '%s  %s\n' 27d054c155e7767ca2048d66c900d75131bf9a6c263fdce5180e06ed5fe6bad6 "$CODER/coder_model.json" | sha256sum -c -
printf '%s  %s\n' 3cc8a60a720e00816e2853bce4e47d58705443cf6f4e8a4531ca69ae458b8100 "$SEED" | sha256sum -c -
cp -- "$SEED" workspace.img
printf '%s  %s\n' 3cc8a60a720e00816e2853bce4e47d58705443cf6f4e8a4531ca69ae458b8100 workspace.img | sha256sum -c -
mkdir -m 700 runner-output hf-cache
module purge >/dev/null 2>&1 || true
module load PyTorch/2.9.1-foss-2024a-CUDA-12.8.0
test "$(python -c 'import torch; print(torch.__version__.split("+")[0])')" = 2.9.1
export PYTHONPATH="$PWD/payload:$CODER/packages${PYTHONPATH:+:$PYTHONPATH}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HOME="$PWD/hf-cache"
export DTR_MODEL_DIR="$CODER/../req030-coder32-deploy-20260928-a/model"
export DTR_MODEL_MANIFEST="$CODER/coder_model.json"
export DTR_RUN_OUTPUT="$PWD/runner-output"
export DTR_TASK_IMAGE="$SIF"
export DTR_TASK_IMAGE_SHA256=9da1f51cb8c01a6ad9e0db4d1969742fbec995021e78150a9623d4f4719a8a47
export DTR_WORKSPACE_IMAGE="$PWD/workspace.img"
export DTR_WORKSPACE_SHA256=3cc8a60a720e00816e2853bce4e47d58705443cf6f4e8a4531ca69ae458b8100
export DTR_SUPERVISOR_SHA256=d39647136d7bb1c8d59d85389ff70f0e980cc6277760455ec773433daface974
export DTR_RELEASE_SHA256=46ca01639078f16f24504ef46f702d758165750ac79b05da2c2288362d42621a
export DTR_RELEASE_MANIFEST="$PWD/release.json"
export DTR_BATCH_SCRIPT="$PWD/seaborn_runner_qualification_g.sbatch"
export DTR_APPTAINER="$(command -v apptainer)"
test -x "$DTR_APPTAINER"
avail=$(df -B1 --output=avail . | tail -n1 | tr -d ' ')
case "$avail" in ''|*[!0-9]*) exit 81;; esac
test "$avail" -ge 2147483648
ulimit -f 614400
python -m unittest payload.experiments.lead_req030.test_seaborn_runner_bootstrap -v
timeout --signal=TERM --kill-after=15s 720s python payload/experiments/lead_req030/seaborn_runner_qualification.py > qualification.stdout.json
test -s runner-output/qualification.json
cat runner-output/qualification.json
