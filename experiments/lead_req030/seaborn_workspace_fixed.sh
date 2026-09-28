#!/bin/bash
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
