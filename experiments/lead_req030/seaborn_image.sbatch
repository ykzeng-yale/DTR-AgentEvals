#!/bin/bash
#SBATCH --job-name=dtr030-seaborn-image-a
#SBATCH --account=pi_gt353
#SBATCH --partition=day
#SBATCH --qos=normal
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=slurm-%j.log
set -euo pipefail
trap 'rc=$?; printf "{\"exit_code\":%s}\n" "$rc" > exit.json' EXIT
umask 077
sha256sum -c SHA256SUMS
mkdir -m700 cache temp
export APPTAINER_CACHEDIR="$PWD/cache" APPTAINER_TMPDIR="$PWD/temp"
timeout --kill-after=15s 900s apptainer pull --disable-cache task.sif docker://swebench/sweb.eval.x86_64.mwaskom_1776_seaborn-3187@sha256:6c0cd3296b90a84889796531ab87a0ed8779015b2bbd2e8d99adbdef95397b03
sha256sum task.sif > image.sha256
host_net=$(readlink /proc/self/ns/net)
timeout --kill-after=15s 60s apptainer exec --containall --cleanenv --no-home --no-mount hostfs,bind-paths --net --network none --pwd / --env "DTR_HOST_NET_ID=$host_net" task.sif /bin/bash -c '
set -eu
test "$(readlink /proc/self/ns/net)" != "$DTR_HOST_NET_ID"
test ! -e /home/yz2324; test ! -e /nfs/roberts; test ! -e /var/run/docker.sock
cd /testbed
git rev-parse HEAD
/opt/miniconda3/envs/testbed/bin/python -c "import sys,seaborn; print(sys.version); print(seaborn.__version__); print(seaborn.__file__)"
' > environment.txt
