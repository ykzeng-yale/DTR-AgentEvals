#!/bin/bash
#SBATCH --job-name=dtr030-bound-workspace-b
#SBATCH --account=pi_gt353
#SBATCH --partition=day
#SBATCH --qos=normal
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:05:00
#SBATCH --output=slurm-%j.log
set -euo pipefail
umask 077
trap 'rc=$?; printf "{\"exit_code\":%s}\n" "$rc" > exit.json' EXIT
sha256sum -c SHA256SUMS
image=/home/yz2324/project_pi_gt353/yz2324/DTR-AgentEvals/req030-seaborn-image-20260928-a/task.sif
archive=/home/yz2324/project_pi_gt353/yz2324/DTR-AgentEvals/req030-seaborn-export-20260928-a/testbed.tar
echo '9da1f51cb8c01a6ad9e0db4d1969742fbec995021e78150a9623d4f4719a8a47  '"$image" | timeout 60s sha256sum -c -
echo '317705a1463c5ac9fca593d7349f7ed0099a5d574d23117cebcafdd5014e60e0  '"$archive" | sha256sum -c -
mkdir seed
# Previously measured archive has no symlinks; validate every member before extraction.
python3 - "$archive" <<'PY'
import sys,tarfile,pathlib
with tarfile.open(sys.argv[1]) as t:
 ms=t.getmembers()
 assert sum(m.size for m in ms)<60000000
 for m in ms:
  p=pathlib.PurePosixPath(m.name)
  assert not p.is_absolute() and '..' not in p.parts and p.parts[0]=='testbed'
  assert m.isfile() or m.isdir()
 t.extractall('seed')
PY
truncate -s 512M workspace.img
timeout --kill-after=15s 60s mkfs.ext3 -F -m 0 -d seed/testbed workspace.img > mkfs.log 2>&1
# mkfs initializes filesystem root as root; preserve caller ownership of /testbed.
timeout 15s debugfs -w -R "set_inode_field / uid $(id -u)" workspace.img > ownership.log 2>&1
timeout 15s debugfs -w -R "set_inode_field / gid $(id -g)" workspace.img >> ownership.log 2>&1
timeout 15s debugfs -R 'stat /' workspace.img >> ownership.log 2>&1
host_net=$(readlink /proc/self/ns/net)
timeout --kill-after=15s 60s apptainer exec --containall --cleanenv --no-home --no-mount hostfs,bind-paths --net --network none --pwd / --env "DTR_HOST_NET_ID=$host_net" --bind "$PWD/workspace.img:/testbed:image-src=/" "$image" /bin/bash -s < seaborn_bound_workspace.sh > environment.txt
