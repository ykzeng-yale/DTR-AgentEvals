"""DTR-REQ-021 fixtures: the one-time existing-host capacity check. Expected values are hand-derived from the REQ-020 32k
f16 row (weights 4.739 + 2.326 GiB, KV 4.5 + 4.5 GiB, VM 16 GiB) and the >= 20 % post-load rule."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments/v2_adapter'))
import req021_host_check as H  # noqa: E402

GiB = 1 << 30


def test_admission_arithmetic_by_hand():
    f20 = {'envelopes': {'32k_48': {'memory': {'f16': dict(
        large_weights=5088494342, small_weights=2497281120, large_kv=int(4.5 * GiB), small_kv=int(4.5 * GiB),
        vm_allowance=16 * GiB)}}}}
    host = dict(hw_memsize_bytes=32 * GiB, memory_free_pct=60)
    a = H.local_host_admission(host, f20)
    static = 5088494342 + 2497281120 + 9 * GiB + 16 * GiB
    assert a['static_total_bytes'] == static and a['static_fits'] is False            # 32.065 > 30 GiB
    assert a['ram_needed_gib_without_buffers_or_cache'] == round(static / 0.8 / GiB, 2) == 40.08
    assert a['ram_needed_gib_with_both_default_caches_full'] == round((static + 16 * GiB) / 0.8 / GiB, 2) == 60.08
    # 60 % of 32 GiB free now minus the 16.065 GiB model side: 19.2 - 16.065 = 3.135 GiB = 9.8 % < 20 %
    assert a['post_load_free_pct_projection'] == 9.8
    assert a['post_load_passes'] is False
    a = H.local_host_admission(dict(hw_memsize_bytes=64 * GiB, memory_free_pct=90), f20)
    assert a['static_fits'] is True and a['post_load_passes'] is True                  # a 64 GiB quiet host would pass


def test_ssh_include_is_followed_and_loopback_hosts_are_local(tmp_path):
    inc = tmp_path / 'inc_config'
    inc.write_text('Host vm\n  HostName 127.0.0.1\n  Port 50022\n')
    main = tmp_path / 'config'
    main.write_text('Include %s\n\nHost remote\n  HostName compute.example.invalid\n' % inc)
    hosts = H.ssh_hosts(main)
    assert len(hosts) == 2 and sorted(h['local'] for h in hosts) == [False, True]


def test_published_host_check_is_blocked_and_private():
    out = ROOT / H.OUT_REL / 'host_check.json'
    if not out.exists():
        pytest.skip('host check not built yet')
    rec = json.loads(out.read_text())
    assert rec['verdict']['status'] == 'BLOCKED'
    assert rec['gates']['H1_other_accessible_no_cost_host'] is False
    assert rec['access']['gcloud']['existing_instances_queried'] is False               # no cloud API call
    assert rec['admission_32k_f16']['static_fits'] is False
    text = json.dumps(rec)
    assert '@' not in text and 'github' not in text                                    # no account or host names
