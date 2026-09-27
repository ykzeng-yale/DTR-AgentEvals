set -eu; cd /testbed; git rev-parse HEAD; python --version; cat /proc/net/dev; printf DTR_SANDBOX_OK > /tmp/dtr_probe; cat /tmp/dtr_probe
