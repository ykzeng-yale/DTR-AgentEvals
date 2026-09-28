#!/bin/bash
set -euo pipefail
test "$(readlink /proc/self/ns/net)" != "$DTR_HOST_NET_ID"
test ! -e /home/yz2324
test ! -e /nfs/roberts
if touch /DTR_ROOT_WRITE_TEST 2>/dev/null; then exit 90; fi
cd /testbed
git rev-parse HEAD
printf DTR_FIXED_BOUND > .dtr_sentinel
test "$(cat .dtr_sentinel)" = DTR_FIXED_BOUND
rm .dtr_sentinel
git diff --exit-code
df -B1 /testbed /tmp
/opt/miniconda3/envs/testbed/bin/python -c 'import seaborn; print(seaborn.__version__); print(seaborn.__file__)'
