#!/bin/bash
#SBATCH --job-name=dtr030-sandbox-a
#SBATCH --account=pi_gt353
#SBATCH --partition=day
#SBATCH --qos=normal
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --output=slurm-%j.log
set -euo pipefail
trap 'rc=$?; printf "{\"exit_code\":%s}\n" "$rc" > exit.json' EXIT
umask 077
mkdir -m700 cache temp
export APPTAINER_CACHEDIR="$PWD/cache" APPTAINER_TMPDIR="$PWD/temp"
apptainer --version > version.txt
timeout --kill-after=15s 300s apptainer pull --disable-cache probe.sif docker://alpine@sha256:1c4eef651f65e2f7daee7ee785882ac164b02b78fb74503052a26dc061c90474
sha256sum probe.sif > image.sha256
# Fixed authored script only; no generated commands, host mounts or benchmark inputs.
timeout --kill-after=15s 60s apptainer exec --containall --cleanenv --no-home --no-mount hostfs,bind-paths --net --network none probe.sif /bin/sh -c 'set -eu; test ! -e /home/yz2324; test ! -e /nfs/roberts; test ! -e /var/run/docker.sock; ip -o link; test "$(ls /sys/class/net)" = lo; echo DTR_SANDBOX_PREFLIGHT' > isolation.txt
