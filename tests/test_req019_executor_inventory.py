"""DTR-REQ-019 fixtures: the source-only executor inventory. Expected values are hand-derived (architecture arithmetic,
a synthetic GGUF header, the committed REQ-008 counts), never recomputed with the code under test."""
import json
import struct
import sys
from collections import OrderedDict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments/v2_adapter'))
import req019_executor_inventory as R  # noqa: E402


def gguf_bytes(kv):
    """a minimal GGUF v3 header with the given (key, type, value) triples and no tensors."""
    out = b'GGUF' + struct.pack('<I', 3) + struct.pack('<QQ', 0, len(kv))
    for k, t, v in kv:
        kb = k.encode()
        out += struct.pack('<Q', len(kb)) + kb + struct.pack('<I', t)
        if t == 8:
            vb = v.encode()
            out += struct.pack('<Q', len(vb)) + vb
        elif t == 9:                               # array of uint32
            out += struct.pack('<IQ', 4, len(v)) + b''.join(struct.pack('<I', x) for x in v)
        else:
            out += struct.pack(R.GGUF_TYPES[t], v)
    return out


def test_gguf_header_reader_by_hand(tmp_path):
    f = tmp_path / 'm.gguf'
    f.write_bytes(gguf_bytes([('general.architecture', 8, 'qwen3'), ('general.license', 8, 'apache-2.0'),
                              ('general.file_type', 4, 15), ('tokenizer.ggml.tokens', 9, [1, 2, 3]),
                              ('qwen3.block_count', 4, 36), ('qwen3.attention.head_count', 4, 32),
                              ('qwen3.attention.head_count_kv', 4, 8), ('qwen3.embedding_length', 4, 2560),
                              ('qwen3.attention.key_length', 4, 128), ('qwen3.context_length', 4, 262144)]))
    m = R.gguf_meta(f)
    assert m['general.architecture'] == 'qwen3' and m['general.license'] == 'apache-2.0'
    assert R.FILE_TYPES[m['general.file_type']] == 'Q4_K_M' and 'tokenizer.ggml.tokens' not in m
    n = R.arch_numbers(meta=m)
    assert (n['layers'], n['kv_heads'], n['head_dim'], n['max_context']) == (36, 8, 128, 262144)
    # K and V, f16: 2 * 36 * 8 * 128 * 16384 * 2 bytes = 2.25 GiB
    assert R.kv_bytes(n, 16384) == 2 * 36 * 8 * 128 * 16384 * 2 == int(2.25 * (1 << 30))


def test_kv_from_config_uses_hidden_size_over_heads_when_head_dim_absent():
    cfg = dict(architectures=['Qwen2ForCausalLM'], model_type='qwen2', num_hidden_layers=28, num_attention_heads=28,
               num_key_value_heads=4, hidden_size=3584, max_position_embeddings=32768)
    n = R.arch_numbers(cfg=cfg)
    assert n['head_dim'] == 128                                    # 3584 / 28
    assert R.kv_bytes(n, 16384) == 2 * 28 * 4 * 128 * 16384 * 2   # 0.875 GiB (the frozen 7B kv_gib 0.88)


def test_readme_license_and_classification():
    assert R.readme_license('---\nlicense: apache-2.0\ntags: [x]\n---\n# card') == 'apache-2.0'
    assert R.readme_license('# no front matter\nlicense: mit') is None
    assert R.classify(dict(repo=None, path='work/models/converted_4fea119/qwen2.5-coder-14b-q4_k_m.gguf')) == 'code_instruct'
    assert R.classify(dict(repo='AI-MO/Kimina-Prover-RL-1.7B', path='x')) == 'theorem_prover'
    assert R.classify(dict(repo='ibm-granite/granite-3.3-8b-instruct-GGUF', path='x')) == 'general_instruct'


def row(key, **over):
    base = dict(key=key, path=key, purpose='general_instruct', servable_by_pinned_llama_cpp=True, license='apache-2.0',
                closed_by_lead=False, max_context=32768, memory_projection_bytes=20, memory_projection_limit_bytes=30,
                competence_evidence=None, layers=36, kv_heads=8, head_dim=128, q4_gguf_bytes_estimate=2 << 30,
                canonical_model=key, shard_index=dict(complete=True))
    base.update(over)
    return base


def ledger(*rows):
    return dict(checkpoints=list(rows), harness=dict(settings=dict(context_per_slot=16384),
                                                     memory_rule=dict(vm_gib=16, margin_gib=2)),
                host=dict(hw_memsize_bytes=32 << 30))


def test_verdict_needs_one_competent_large_and_a_distinct_small():
    comp = dict(independent_swebv_comparable_contract=True, independent_swebv_any=True)
    _, v = R.evaluate(ledger(row('a'), row('b')))
    assert v['status'] == 'BLOCKED' and v['eligible_large'] == []          # no competence evidence
    _, v = R.evaluate(ledger(row('a', competence_evidence=comp)))
    assert v['status'] == 'BLOCKED'                                         # a single model is not a pair
    _, v = R.evaluate(ledger(row('a', competence_evidence=comp), row('b')))
    assert v['status'] == 'FEASIBLE' and v['eligible_large'] == ['a'] and set(v['eligible_small']) == {'a', 'b'}
    _, v = R.evaluate(ledger(row('a', competence_evidence=comp, closed_by_lead=True), row('b')))
    assert v['status'] == 'BLOCKED'                                         # a closed model never qualifies
    m, v = R.evaluate(ledger(row('a', competence_evidence=comp, max_context=8192), row('b')))
    assert v['status'] == 'BLOCKED' and m[0]['C6_context'] is False
    m, _ = R.evaluate(ledger(row('a', memory_projection_bytes=31)))
    assert m[0]['C7_memory'] is False
    # two formats of one model are not a pair
    _, v = R.evaluate(ledger(row('a', competence_evidence=comp, canonical_model='m'), row('b', canonical_model='m')))
    assert v['status'] == 'BLOCKED'
    # an incomplete shard set is not present
    m, v = R.evaluate(ledger(row('a', competence_evidence=comp, shard_index=dict(complete=False)), row('b')))
    assert m[0]['C1_present'] is False and v['status'] == 'BLOCKED'


def test_relaxed_alternative_is_reported_but_never_the_verdict():
    anyev = dict(independent_swebv_comparable_contract=False, independent_swebv_any=True)
    m, v = R.evaluate(ledger(row('a', competence_evidence=anyev), row('b')))
    assert v['status'] == 'BLOCKED' and m[0]['any_independent_swebv_evidence'] is True
    alt = v['alternative_if_contract_relaxed']
    assert alt['eligible_large'] == ['a'] and alt['pair_possible'] is True and 'NOT a verdict' in alt['note']
    # 36 layers, 8 kv heads, head dim 128 at 32768 tokens, f16 K and V: 4.5 GiB; + 2 GiB weights + 16 GiB VM
    assert alt['memory_at_32768_context']['a']['kv_bytes_at_32768'] == int(4.5 * (1 << 30))
    assert alt['memory_at_32768_context']['a']['single_projection_bytes'] == int((4.5 + 2 + 16) * (1 << 30))
    # co-serving counts the VM once: at 16384 tokens 2 x (2 GiB weights + 2.25 GiB KV) + 16 GiB = 24.5 GiB <= 30 GiB;
    # at 32768 tokens 2 x (2 + 4.5) + 16 = 29 GiB <= 30 GiB
    co = alt['co_serving_distinct_models']['a + b']
    assert co['projection_bytes_at_16384'] == int(24.5 * (1 << 30)) and co['fits_at_16384'] is True
    assert co['projection_bytes_at_32768'] == 29 * (1 << 30) and co['fits_at_32768'] is True


def test_every_shard_is_listed_and_checked_against_the_index(tmp_path):
    d = tmp_path / 'ckpt'
    d.mkdir()
    for name, size in (('model-00001-of-00003.safetensors', 101 << 20), ('model-00002-of-00003.safetensors', 1 << 20)):
        with open(d / name, 'wb') as f:
            f.truncate(size)
    (d / 'model.safetensors.index.json').write_text(json.dumps(dict(weight_map={
        'a': 'model-00001-of-00003.safetensors', 'b': 'model-00002-of-00003.safetensors',
        'c': 'model-00003-of-00003.safetensors'})))
    files = R.weight_files(d)
    assert [f.name for f in files] == ['model-00001-of-00003.safetensors', 'model-00002-of-00003.safetensors']   # small shard kept
    ic = R.index_check(d, files)
    assert ic['complete'] is False and ic['missing'] == ['model-00003-of-00003.safetensors'] and ic['shards_in_index'] == 3
    with open(d / 'model-00003-of-00003.safetensors', 'wb') as f:
        f.truncate(10)
    assert R.index_check(d, R.weight_files(d))['complete'] is True
    small = tmp_path / 'tiny'
    small.mkdir()
    with open(small / 'model.safetensors', 'wb') as f:
        f.truncate(1 << 20)
    assert R.weight_files(small) == []                                     # no >= 100 MiB file: not a checkpoint


def test_canonical_model_names():
    assert R.canonical('unsloth/Qwen3-4B-Instruct-2507-GGUF') == R.canonical('Qwen/Qwen3-4B-Instruct-2507') == \
        'qwen3-4b-instruct-2507'
    assert R.canonical('qwen2.5-coder-7b-instruct-c03e6d3-q4_k_m.gguf') == 'qwen2.5-coder-7b-instruct'
    assert R.canonical('Qwen/Qwen2.5-7B-Instruct-GGUF') != R.canonical('Qwen/Qwen2.5-3B-Instruct-GGUF')


def test_exposure_exclusion_list_matches_req008_plus_the_later_episodes():
    e = R.exposure()
    assert (len(e['req008_model_outcome_exposed']), len(e['req008_qualification_or_inspection_only'])) == (64, 5)
    assert e['post_req008_model_outcome_exposed']['astropy__astropy-14598']['manifests_agree'] is True
    assert e['post_req008_model_outcome_exposed']['astropy__astropy-14598']['req008_category'] == 'not_yet_assessed'
    assert e['n_exclude'] == 64 + 5 + 1 and 'astropy__astropy-14598' in e['exclude_from_untouched_evaluation']
    assert len(e['req009_design_queue']) == 24 and e['req009_design_queue'][0] == 'astropy__astropy-14598'
    assert len(e['req009_design_queue_remaining_unexposed']) == 23          # rank 1 was run by REQ-011..014
    # the lead's REQ-009 rules (0fe40b8) add 11 component-mates and 8 empty PASS_TO_PASS: 70 + 19 = 89
    assert {k: len(v) for k, v in e['lead_rule_additional_exclusions'].items()} == {
        'component_touches_exposed_or_qualification_only': 11, 'empty_pass_to_pass': 8}
    assert e['n_exclude_including_lead_rules'] == 89 and e['config_scan']['ids_not_in_exclude'] == []
    assert list(e['post_req008_model_outcome_exposed']['astropy__astropy-14598']['manifests']) == [
        'configs/v2_req011_competence_pair_20260924.json', 'configs/v2_req012_repair_probe_20260924.json',
        'configs/v2_req014_14b_capacity_probe_20260924.json']                  # REQ-013 ran no model episode


def test_published_inventory_is_consistent():
    out = ROOT / R.OUT_REL
    if not (out / 'inventory.json').exists():
        pytest.skip('inventory not built yet')
    inv = json.loads((out / 'inventory.json').read_text())
    assert inv['request'] == 'DTR-REQ-019' and inv['exposure']['n_exclude'] == 70
    assert all(c['closed_by_lead'] for c in inv['checkpoints'] if 'coder' in c['path'].lower())
    assert all(not m['eligible_large'] for m in inv['matrix'] if m['purpose'] != 'general_instruct'
               and m['purpose'] != 'code_instruct')
    assert inv['external']['weight_files_at_least_100MB'] >= 0 and 'Volumes' not in json.dumps(inv['external'])
    assert (out / 'candidate_matrix.csv').read_text().count('\n') == len(inv['matrix']) + 1
    q = next(c for c in inv['checkpoints'] if c['key'] == 'Qwen/Qwen3-4B-Instruct-2507')
    assert len(q['files']) == 3 and q['shard_index']['complete'] is True and q['weight_bytes'] == 8044982000
    assert all(c['shard_index']['complete'] for c in inv['checkpoints'])
    assert inv['verdict']['status'] == 'BLOCKED' and 'cannot currently be met' in inv['verdict']['disclosure']
    for c in inv['checkpoints']:                   # nothing outside the HF cache or this repository is named
        if c['location'] == 'other_local':
            assert c['key'].startswith('other-local-') and 'not listed' in c['path'] and 'sha256' not in json.dumps(c)
