#!/bin/bash
#SBATCH --job-name=dtr030-seaborn-export-a
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
echo '9da1f51cb8c01a6ad9e0db4d1969742fbec995021e78150a9623d4f4719a8a47  '"$image" | timeout 60s sha256sum -c -
# bash ulimit -f uses KiB: cap each output file at 512 MiB.
ulimit -f 524288
timeout --kill-after=15s 120s apptainer exec --containall --cleanenv --no-home --no-mount hostfs,bind-paths --net --network none --pwd / "$image" /bin/tar -C / -cf - testbed > testbed.tar
sha256sum testbed.tar > archive.sha256
python3 - <<'PY'
import tarfile,json,os
with tarfile.open('testbed.tar','r:') as t:
 members=t.getmembers()
 assert members and all(m.name=='testbed' or m.name.startswith('testbed/') for m in members)
 assert not any(m.isdev() or m.isfifo() for m in members)
 print(json.dumps({'archive_bytes':os.path.getsize('testbed.tar'),'members':len(members),'regular_unpacked_bytes':sum(m.size for m in members if m.isfile()),'symlinks':sum(m.issym() for m in members)}))
PY
