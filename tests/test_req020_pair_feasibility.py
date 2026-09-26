"""DTR-REQ-020 fixtures: the source-only Klear-AgentForge-8B / Qwen3-4B-Instruct-2507 pair feasibility. Expected values are
hand-derived from the public config (36 layers, 8 KV heads, head dim 128, 8,190,735,360 parameters) and the REQ-014
static rule, never recomputed with the code under test."""
import base64
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments/v2_adapter'))
import req020_pair_feasibility as F  # noqa: E402

GiB = 1 << 30
OUT = ROOT / F.OUT_REL


def test_kv_arithmetic_by_hand():
    # K and V, f16: 2 * 36 * 8 * 128 * 32768 * 2 bytes = 4.5 GiB; twice that at 65536 tokens
    assert F.kv_bytes(36, 8, 128, 32768) == 2 * 36 * 8 * 128 * 32768 * 2 == int(4.5 * GiB)
    assert F.kv_bytes(36, 8, 128, 65536) == 9 * GiB
    # q8_0 stores 34 bytes per 32 values
    assert F.kv_bytes(36, 8, 128, 32768, 34 / 32) == int(4.5 * GiB * 34 / 64)


def test_template_facts_on_a_minimal_template():
    t = {'chat_template': "{%- if tools %}<tool_call>{%- endif %}<|im_start|>{%- if (x > y) and 0 %}<|im_end|>",
         'eos_token': '<|im_end|>'}
    f = F.template_facts(t)
    assert f['chatml_markers'] and f['has_tools_branch'] and f['emits_tool_call_xml_for_tool_calls']
    assert f['think_block_insertion_disabled'] is True


def test_published_feasibility_matches_hand_arithmetic():
    if not (OUT / 'feasibility.json').exists():
        pytest.skip('feasibility not built yet')
    L = json.loads((OUT / 'feasibility.json').read_text())
    large = L['pair']['stronger']
    assert large['revision'] == 'fa3d41e92e9ce7a5b4a52a3e7439aa00521f40c9' and large['api_sha_matches_pin']
    assert large['license'] == 'apache-2.0' and large['index_complete'] and len(large['shards']) == 4
    assert (large['layers'], large['kv_heads'], large['head_dim'], large['max_context']) == (36, 8, 128, 65536)
    assert large['q4_gguf_bytes_estimate'] == int(8190735360 * 4.97 / 8)
    small = L['pair']['smaller']
    assert small['gguf_bytes'] == 2497281120 and (small['layers'], small['kv_heads'], small['head_dim']) == (36, 8, 128)
    q4 = int(8190735360 * 4.97 / 8)
    for name, ctx in (('32k_48', 32768), ('64k_100', 65536)):
        row = L['envelopes'][name]['memory']['f16']
        total = q4 + 2497281120 + 2 * (2 * 36 * 8 * 128 * ctx * 2) + 16 * GiB
        assert row['simultaneous_total'] == total and row['limit'] == 30 * GiB
        assert row['fits'] is (total <= 30 * GiB) is False                   # 32.07 and 41.07 GiB
    assert L['envelopes']['32k_48']['memory']['q8_0']['fits'] is True          # sensitivity only (static rule)
    assert L['envelopes']['32k_48']['memory']['f16']['max_vm_allowance_that_fits_gib_rounded_down'] == 13.93
    pl = L['envelopes']['32k_48']['post_load_reserve']['f16']
    assert pl['model_side_bytes'] == int(8190735360 * 4.97 / 8) + 2497281120 + 2 * int(4.5 * GiB) and pl['passes'] is False
    assert L['host_measured_utc'].endswith('Z')
    assert L['envelopes']['64k_100']['memory']['q8_0']['fits'] is False
    assert L['verdict']['overall'] == 'BLOCKED'
    assert all(v['failing_gates'] == ['G4_simultaneous_memory_f16_kv'] for v in L['verdict']['per_envelope'].values())
    assert L['code_inspection']['harness_model_class'] == 'LitellmTextbasedModel'
    assert L['code_inspection']['textbased_model_sends_tools'] is False
    comm = L['envelopes']['32k_48']['memory']['f16_with_community_q4_size']
    assert comm['simultaneous_total'] == 5027783808 + 2497281120 + 2 * int(4.5 * GiB) + 16 * GiB and comm['fits'] is False
    pr = L['protocol']
    assert pr['frozen_harness']['yaml_v1_matches_frozen_binding'] is True
    assert pr['frozen_harness']['fence'] == 'mswea_bash_command' and pr['klear_trained']['fence'] == 'bash'
    assert pr['frozen_harness']['submit_sentinel'] == 'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT'
    assert len(pr['differences']) == 3 and pr['status'].startswith('RISK')    # a risk, not a failing gate
    assert L['disk']['peak_bytes_if_intermediates_kept'] == 2 * 16381516824 + int(8190735360 * 4.97 / 8)
    text = json.dumps(L) + (OUT / 'klear_evidence.json').read_text()
    # no internal cluster path, local username, scratch path or personal name (strings kept out of this file)
    leaks = [base64.b64decode(b).decode() for b in (b'bW11X25scA==', b'eXVrYW5nemVuZ2NtYWM=', b'L3ByaXZhdGUvdG1w',
                                                   b'SG9uZ3po', b'Zmpfb2xkbWVyZ2U=')]
    assert not [i for i, leak in enumerate(leaks) if leak in text]
