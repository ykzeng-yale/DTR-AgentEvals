#!/bin/bash
#SBATCH --job-name=dtr030-network-a
#SBATCH --account=pi_gt353
#SBATCH --partition=day
#SBATCH --qos=normal
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:05:00
#SBATCH --output=slurm-%j.log
set -euo pipefail
trap 'rc=$?; printf "{\"exit_code\":%s}\n" "$rc" > exit.json' EXIT
sha256sum -c SHA256SUMS
old="$PWD/../req030-sandbox-preflight-20260928-a"
(cd "$old" && sha256sum -c image.sha256)
host_net=$(readlink /proc/self/ns/net)
printf '%s\n' "$host_net" > host_net.txt
timeout --kill-after=15s 60s apptainer exec --containall --cleanenv --no-home --no-mount hostfs,bind-paths --net --network none --pwd / --env "DTR_HOST_NET_ID=$host_net" "$old/probe.sif" /bin/sh -c '
set -eu
actual=$(readlink /proc/self/ns/net)
printf "CONTAINER_NET=%s\n" "$actual"
test "$actual" != "$DTR_HOST_NET_ID"
test ! -e /home/yz2324; test ! -e /nfs/roberts; test ! -e /var/run/docker.sock
ip -o link > /tmp/links
cat /tmp/links
test "$(wc -l < /tmp/links)" -eq 1
grep -q "lo:" /tmp/links
test -z "$(ip route)"
if touch /DTR_ROOT_WRITE_TEST 2>/tmp/root_error; then echo ROOT_WRITABLE; exit 1; fi
cat /tmp/root_error
printf "NETWORK_AND_ROOT_CHECK_PASS\n"
' > isolation.txt
