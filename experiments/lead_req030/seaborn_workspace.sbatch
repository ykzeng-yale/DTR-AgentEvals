#!/bin/bash
#SBATCH --job-name=dtr030-seaborn-workspace-a
#SBATCH --account=pi_gt353
#SBATCH --partition=day
#SBATCH --qos=normal
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:05:00
#SBATCH --output=slurm-%j.log
set -euo pipefail
trap 'rc=$?; printf "{\"exit_code\":%s}\n" "$rc" > exit.json' EXIT
umask 077
sha256sum -c SHA256SUMS
image=/home/yz2324/project_pi_gt353/yz2324/DTR-AgentEvals/req030-seaborn-image-20260928-a/task.sif
timeout --kill-after=15s 60s sha256sum "$image" > image.sha256
timeout --kill-after=15s 30s apptainer sif list "$image" > sif-list.txt
timeout --kill-after=15s 30s apptainer inspect --json "$image" > inspect.json
echo '9da1f51cb8c01a6ad9e0db4d1969742fbec995021e78150a9623d4f4719a8a47  '"$image" | sha256sum -c -
host_net=$(readlink /proc/self/ns/net)
timeout --kill-after=15s 60s apptainer exec --writable-tmpfs --containall --cleanenv --no-home --no-mount hostfs,bind-paths --net --network none --pwd / --env "DTR_HOST_NET_ID=$host_net" "$image" /bin/bash -c '
set -eu
test "$(readlink /proc/self/ns/net)" != "$DTR_HOST_NET_ID"
test ! -e /home/yz2324; test ! -e /nfs/roberts; test ! -e /var/run/docker.sock
cd /testbed
git rev-parse HEAD
printf DTR_FIXED_WORKSPACE > /testbed/.dtr_fixed_workspace
 test "$(cat /testbed/.dtr_fixed_workspace)" = DTR_FIXED_WORKSPACE
rm /testbed/.dtr_fixed_workspace
df -B1 /testbed /tmp
cat /proc/mounts | awk '$2 == "/" {print $3, $4}'
git diff --exit-code

/opt/miniconda3/envs/testbed/bin/python -c "import sys,seaborn; print(sys.version); print(seaborn.__version__); print(seaborn.__file__)"
' > environment.txt
