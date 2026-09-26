"""DTR-REQ-020 (lead d0b905a, docs/theory_feedback_20260926_req019_decision.md): source-only feasibility of one possible
stronger fresh pair for the unchanged SWE-bench Verified strict terminal endpoint: nonlocal Kwai-Klear/Klear-AgentForge-8B
(stronger) versus the already local Qwen/Qwen3-4B-Instruct-2507 (smaller), under two common DEVELOPMENT envelopes,
32k context / 48 calls and then 64k context / 100 calls.

No download, inference, server/container start, new task exposure or source-pin change. Inputs:
  - source-inspected: the public Klear files saved at the pinned revision under OUT/source/ (HF API metadata,
    config.json, generation_config.json, tokenizer_config.json, the shard index, a redacted merge_config summary) and
    the cited research in OUT/klear_evidence.json;
  - code-inspected: the pinned llama.cpp 4fea119 architecture table and converter, and the pinned mini-swe-agent
    04d809c model classes used by this project's harness;
  - worker-host measured: the local Qwen3-4B-Instruct-2507 facts from the REQ-019 inventory and fresh read-only host,
    VM and peer readings (reusing the REQ-019 probes).
Writes OUT/feasibility.json with a yes/no per envelope and the failing gates with their arithmetic.

    .venv/bin/python experiments/v2_adapter/req020_pair_feasibility.py [--out DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/v2_adapter'))
import req019_executor_inventory as INV  # noqa: E402

REQUEST = 'DTR-REQ-020'
OUT_REL = 'results/v2_adapter/req020_pair_feasibility_20260926'
GiB = 1 << 30
KLEAR = OrderedDict(repo='Kwai-Klear/Klear-AgentForge-8B', revision='fa3d41e92e9ce7a5b4a52a3e7439aa00521f40c9')
SMALL_KEY = 'unsloth/Qwen3-4B-Instruct-2507-GGUF'          # the local Q4_K_M copy (REQ-019); same model as the HF weights
SMALL_HF_KEY = 'Qwen/Qwen3-4B-Instruct-2507'
REQ019 = 'results/v2_adapter/req019_executor_inventory_20260926/inventory.json'
ENVELOPES = OrderedDict([('32k_48', OrderedDict(context_tokens=32768, call_limit=48)),
                         ('64k_100', OrderedDict(context_tokens=65536, call_limit=100))])
KV_BYTES = OrderedDict(f16=2, q8_0=34 / 32)       # llama.cpp q8_0: 34 bytes per 32 values
COMMUNITY_Q4_BYTES = 5027783808                   # mradermacher/Klear-AgentForge-8B-GGUF Q4_K_M (klear_evidence.json)
MINI = 'work/upstream/mini-swe-agent-04d809ceab9df28f9adaed044884180159172930/src/minisweagent'
LLAMA = 'work/upstream/llama.cpp-4fea119'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def kv_bytes(layers, kv_heads, head_dim, ctx, per_value=2):
    return int(2 * layers * kv_heads * head_dim * ctx * per_value)


def code_inspection():
    arch = (ROOT / LLAMA / 'src/llama-arch.cpp').read_text()
    textbased = (ROOT / MINI / 'models/litellm_textbased_model.py').read_text()
    toolcall = (ROOT / MINI / 'models/litellm_model.py').read_text()
    harness = (ROOT / 'experiments/v2_agent/pilot_episode.py').read_text()
    chat = (ROOT / LLAMA / 'src/llama-chat.cpp').read_text()
    return OrderedDict(
        llama_cpp_has_qwen3='"qwen3"' in arch,
        converter_registers_Qwen3ForCausalLM='Qwen3ForCausalLM' in INV.converter_classes(),
        llama_cpp_has_chatml_template='LLM_CHAT_TEMPLATE_CHATML' in chat,
        harness_model_class='LitellmTextbasedModel' if 'LitellmTextbasedModel' in harness else None,
        textbased_model_sends_tools='tools=' in textbased,
        toolcall_model_sends_tools='tools=[BASH_TOOL]' in toolcall,
        reading='this project runs mini-swe-agent with LitellmTextbasedModel (experiments/v2_agent/pilot_episode.py): '
                'plain-text bash actions and no tools parameter, so the served chat template takes its no-tools branch')


def protocol_inspection():
    """the frozen harness protocol (yaml-v1 = the pinned default.yaml) read from the pinned source."""
    cfg = ROOT / MINI / 'config/default.yaml'
    text = cfg.read_text()
    model = (ROOT / MINI / 'models/litellm_textbased_model.py').read_text()
    docker = (ROOT / MINI / 'environments/docker.py').read_text()
    m = re.search(r'action_regex: str = r"([^"]+)"', model)
    return OrderedDict(
        yaml_v1_file='config/default.yaml', yaml_v1_sha256=sha(cfg),
        yaml_v1_matches_frozen_binding=sha(cfg) == '112aa58328f478a41cc2630702a4b89ef459e912870e05065157ed221f56701f',
        action_regex=m.group(1) if m else None, fence='mswea_bash_command' if 'mswea_bash_command' in text else None,
        submit_sentinel='COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT' if 'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT' in text else None,
        sentinel_hard_coded_in_docker_environment='COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT' in docker,
        edit_tool=False, frozen_step_limit_override=24,
        frozen_binding='yaml-v1-repair1 (base yaml-v1); the three differences hold under both',
        frozen_per_call=OrderedDict(temperature=0.0, max_tokens=1536, physical_attempts_per_call=2,
                                    episode_wall_seconds=1800, command_timeout_s=60),
        llama_server_uses_jinja_by_default='bool use_jinja = true' in (ROOT / LLAMA / 'common/common.h').read_text(),
        observation='code-inspected at the pinned mini-swe-agent 04d809c')


def template_facts(tok):
    t = tok.get('chat_template') or ''
    return OrderedDict(
        chatml_markers='<|im_start|>' in t and '<|im_end|>' in t,
        has_tools_branch='if tools' in t, emits_tool_call_xml_for_tool_calls='<tool_call>' in t,
        think_block_insertion_disabled='and 0 %}' in t or 'and 0%}' in t,
        eos_token=tok.get('eos_token'), template_sha256=hashlib.sha256(t.encode()).hexdigest())


def build(root=ROOT):
    out = root / OUT_REL
    src = out / 'source'
    files = OrderedDict((p.name, OrderedDict(sha256=sha(p), bytes=p.stat().st_size)) for p in sorted(src.iterdir()))
    api = json.loads((src / 'hf_api_model.json').read_text())
    cfg = json.loads((src / 'config.json').read_text())
    gen = json.loads((src / 'generation_config.json').read_text())
    tok = json.loads((src / 'tokenizer_config.json').read_text())
    idx = json.loads((src / 'model.safetensors.index.json').read_text())
    merge = json.loads((src / 'merge_config_redacted.json').read_text())
    evid = json.loads((out / 'klear_evidence.json').read_text()) if (out / 'klear_evidence.json').exists() else None
    inv = json.loads((root / REQ019).read_text())
    small = next(c for c in inv['checkpoints'] if c['key'] == SMALL_KEY)
    small_hf = next(c for c in inv['checkpoints'] if c['key'] == SMALL_HF_KEY)
    rule = inv['harness']['memory_rule']
    disk_rule = inv['harness']['disk_rule']

    shards = [s for s in api['siblings'] if s['rfilename'].endswith('.safetensors')]
    params = api['safetensors']['total']
    large = OrderedDict(
        repo=KLEAR['repo'], revision=KLEAR['revision'], api_sha_matches_pin=api['sha'] == KLEAR['revision'],
        license=(api.get('cardData') or {}).get('license'), card_bytes=files['README.md']['bytes'],
        architecture=cfg['architectures'][0], model_type=cfg['model_type'], params=params,
        dtype=cfg.get('torch_dtype'), layers=cfg['num_hidden_layers'], kv_heads=cfg['num_key_value_heads'],
        head_dim=cfg['head_dim'], max_context=cfg['max_position_embeddings'], rope_scaling=cfg.get('rope_scaling'),
        shards=[OrderedDict(name=s['rfilename'], bytes=s['size'], lfs_sha256=s.get('lfs_sha256')) for s in shards],
        shard_bytes=sum(s['size'] for s in shards), index_total_size=idx['metadata']['total_size'],
        index_shards=sorted(set(idx['weight_map'].values())),
        index_complete=sorted(set(idx['weight_map'].values())) == sorted(s['rfilename'] for s in shards),
        q4_gguf_bytes_estimate=int(params * INV.Q4_BYTES_PER_PARAM), generation_defaults=gen,
        template=template_facts(tok), merge=merge, observation='source-inspected (public files at the pinned revision)')
    small_d = OrderedDict(
        key=SMALL_KEY, revision=small['revision'], license=small['license'], architecture=small_hf['architecture'],
        layers=small['layers'], kv_heads=small['kv_heads'], head_dim=small['head_dim'], max_context=small['max_context'],
        gguf_bytes=small['weight_bytes'], gguf_sha256=small['files'][0]['sha256'], quantization=small['quantization'],
        hf_weights_key=SMALL_HF_KEY, hf_revision=small_hf['revision'],
        observation='worker-host measured (REQ-019 inventory: local file bytes and sha256)')

    host = INV.host_envelope()
    peers = INV.peers()
    limit = host['hw_memsize_bytes'] - rule['margin_gib'] * GiB
    envelopes = OrderedDict()
    for name, env in ENVELOPES.items():
        ctx = env['context_tokens']
        rows = OrderedDict()
        for kvname, per in KV_BYTES.items():
            kl = kv_bytes(large['layers'], large['kv_heads'], large['head_dim'], ctx, per)
            ks = kv_bytes(small_d['layers'], small_d['kv_heads'], small_d['head_dim'], ctx, per)
            total = large['q4_gguf_bytes_estimate'] + small_d['gguf_bytes'] + kl + ks + rule['vm_gib'] * GiB
            rows[kvname] = OrderedDict(
                large_weights=large['q4_gguf_bytes_estimate'], small_weights=small_d['gguf_bytes'], large_kv=kl,
                small_kv=ks, vm_allowance=rule['vm_gib'] * GiB, simultaneous_total=total, limit=limit,
                excess=total - limit, fits=total <= limit,
                max_vm_allowance_that_fits=limit - (total - rule['vm_gib'] * GiB),
                max_vm_allowance_that_fits_gib_rounded_down=int((limit - (total - rule['vm_gib'] * GiB)) / GiB * 100) / 100,
                arithmetic='%.3f + %.3f + %.3f + %.3f + %d = %.3f GiB vs limit %.3f GiB' % (
                    large['q4_gguf_bytes_estimate'] / GiB, small_d['gguf_bytes'] / GiB, kl / GiB, ks / GiB,
                    rule['vm_gib'], total / GiB, limit / GiB))
        gates = OrderedDict(
            G1_source_pinned=large['api_sha_matches_pin'] and large['index_complete'] and bool(large['license']),
            G2_llama_cpp_architecture=True,       # filled below from code inspection
            G3_context=ctx <= large['max_context'] and ctx <= small_d['max_context'],
            G4_simultaneous_memory_f16_kv=rows['f16']['fits'],
            G5_host_disk=None, G6_host_admission_now=None)
        kl = kv_bytes(large['layers'], large['kv_heads'], large['head_dim'], ctx)
        ks = kv_bytes(small_d['layers'], small_d['kv_heads'], small_d['head_dim'], ctx)
        comm = COMMUNITY_Q4_BYTES + small_d['gguf_bytes'] + kl + ks + rule['vm_gib'] * GiB
        rows['f16_with_community_q4_size'] = OrderedDict(
            large_weights=COMMUNITY_Q4_BYTES, simultaneous_total=comm, limit=limit, excess=comm - limit,
            fits=comm <= limit, note='sensitivity: the published community Q4_K_M size (mradermacher, revision '
                                     '0626423882f5), not the pinned-converter estimate')
        free_now = None if host['memory_free_pct'] is None else host['memory_free_pct'] / 100 * host['hw_memsize_bytes']
        post = OrderedDict()
        for kvname in ('f16', 'q8_0'):
            r = rows[kvname]
            model_side = r['large_weights'] + r['small_weights'] + r['large_kv'] + r['small_kv']
            after = None if free_now is None else free_now - model_side
            pct = None if after is None else round(100 * after / host['hw_memsize_bytes'], 2)
            post[kvname] = OrderedDict(model_side_bytes=model_side, free_now_bytes=free_now, free_after_load_bytes=after,
                                       free_after_load_pct=pct, post_load_min_free_pct=rule['post_load_min_free_pct'],
                                       passes=bool(pct is not None and pct >= rule['post_load_min_free_pct']))
        post['basis'] = ('host-measured: current free memory (the Colima VM is already running and counted in it) minus '
                         'both models\' static weights and KV; excludes two compute buffers and the pinned llama-server '
                         'default prompt cache of up to 8192 MiB per server (common/common.h cache_ram_mib), so it is '
                         'optimistic')
        gates['G4_simultaneous_memory_f16_kv'] = rows['f16']['fits'] and post['f16']['passes']
        envelopes[name] = OrderedDict(env, memory=rows, post_load_reserve=post, gates=gates,
                                      g4_observation='mixed: source-inspected Klear geometry and parameter count, '
                                                     'host-measured Qwen3-4B file size and memory, frozen rule constants')
    code = code_inspection()
    proto = protocol_inspection()
    klear_trained = OrderedDict(
        fence='bash', submit_sentinel='MINI_SWE_AGENT_FINAL_OUTPUT', edit_tool='str-replace helper (edit_via_str_replace)',
        reply_shape='THOUGHT plus exactly one fenced block', thinking='non-thinking (inferred)',
        observation='source-inspected: the released SFT trajectories, the mini-swe-agent-plus source and the paper '
                    '(klear_evidence.json)')
    protocol = OrderedDict(
        frozen_harness=proto, klear_trained=klear_trained,
        differences=[d for d, x in (('fence (```bash vs ```mswea_bash_command)', proto['fence'] != 'bash'),
                                    ('submit sentinel (MINI_SWE_AGENT_FINAL_OUTPUT vs '
                                     'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT, hard-coded in the pinned DockerEnvironment)',
                                     proto['submit_sentinel'] != 'MINI_SWE_AGENT_FINAL_OUTPUT'),
                                    ('str-replace edit tool absent in the frozen harness', not proto['edit_tool'])) if x],
        status='RISK: the trained action and submission protocol differs from the frozen harness; whether the model '
               'follows the frozen prompt is not identifiable from source (compare the REQ-016 format failure). Not '
               'counted as a failing gate; a qualification run or a versioned adapter would be a lead decision',
        smaller_model_note='Qwen3-4B-Instruct-2507 training data are unpublished; there is no public evidence either way '
                           'about its exposure to either protocol; it receives the same prompt',
        template_path_risk='the pinned llama-server renders with jinja by default; the Klear template matches no '
                           'specialized handler and falls through to the differential autoparser, whose behaviour for '
                           'this template is unverified without running it (klear_evidence.json)')
    budget = OrderedDict(
        envelopes=OrderedDict((k, dict(v)) for k, v in ENVELOPES.items()),
        published_author=OrderedDict(value='39.4% SWE-bench Verified', steps=200, context_tokens=65536,
                                     scaffold='mini-swe-agent-plus (edit tool, matching prompt)', runs='not stated',
                                     temperature='not stated'),
        published_independent=OrderedDict(value='26.6% SWE-bench Verified (the only independent figure found)',
                                          checkpoint='most likely Klear-AgentForge-8B-SFT',
                                          scaffold='mini-SWE-agent in SkyRL (training caps 35 turns, 28,672 input tokens; '
                                                   'public eval config 125 steps, 64k)'),
        call_definition='48 and 100 are read as logical agent calls (the step_limit analogue); each logical call keeps '
                        'up to 2 physical attempts under the frozen settings',
        reading='both published figures use more steps than either envelope (48 or 100 calls) and a different protocol; '
                'neither establishes competence under the frozen harness')
    # disk: download bf16 shards, convert to a bf16 GGUF with the pinned converter, quantize to Q4_K_M (peak if kept)
    peak = large['shard_bytes'] + large['shard_bytes'] + large['q4_gguf_bytes_estimate']
    disk = OrderedDict(
        download_bytes=large['shard_bytes'], bf16_gguf_bytes_estimate=large['shard_bytes'],
        q4_gguf_bytes_estimate=large['q4_gguf_bytes_estimate'], peak_bytes_if_intermediates_kept=peak,
        host_free_gib=host['host_disk_free_gib'], host_min_gib=disk_rule['host_min_gib'],
        free_after_peak_gib=round(host['host_disk_free_gib'] - peak / GiB, 2),
        fits=host['host_disk_free_gib'] - peak / GiB >= disk_rule['host_min_gib'],
        vm_disk_free_gib=host['vm_disk_free_gib'], vm_min_gib=disk_rule['vm_min_gib'],
        vm_fits=bool(host['vm_disk_free_gib'] and host['vm_disk_free_gib'] >= disk_rule['vm_min_gib']))
    swap = re.search(r'total = ([0-9.]+)M\s+used = ([0-9.]+)M', host['swap'] or '')
    admission = OrderedDict(
        memory_free_pct=host['memory_free_pct'], admission_min_free_pct=rule['admission_min_free_pct'],
        memory_ok=bool(host['memory_free_pct'] is not None and host['memory_free_pct'] >= rule['admission_min_free_pct']),
        swap_used_gib=round(float(swap.group(2)) / 1024, 2) if swap else None,
        swap_total_gib=round(float(swap.group(1)) / 1024, 2) if swap else None,
        model_servers_running=len(peers['model_server_processes']), code_routing_stages=peers['code_routing_stage_processes'],
        no_peer_model_job=not peers['model_server_processes'] and not peers['code_routing_stage_processes'],
        observation='worker-host measured at build time (live; not a reservation)')
    for e in envelopes.values():
        e['gates']['G2_llama_cpp_architecture'] = bool(code['llama_cpp_has_qwen3'] and code['converter_registers_Qwen3ForCausalLM'])
        e['gates']['G5_host_disk'] = bool(disk['fits'] and disk['vm_fits'])
        e['gates']['G6_host_admission_now'] = bool(admission['memory_ok'] and admission['no_peer_model_job'])
        failing = [k for k, v in e['gates'].items() if v is False]
        e['feasible'] = not failing
        e['verdict'] = 'YES' if not failing else 'NO'
        e['failing_gates'] = failing
    ledger = OrderedDict(
        request=REQUEST, kind='source-only pair feasibility (no download, inference, server or container start)',
        host_measured_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        lead_commit='d0b905a', lead_decision='docs/theory_feedback_20260926_req019_decision.md',
        source_commit=INV.git('rev-parse', 'HEAD'), builder_sha256=sha(Path(__file__)),
        source_files=files, evidence_sha256=sha(out / 'klear_evidence.json') if evid else None,
        pair=OrderedDict(stronger=large, smaller=small_d), code_inspection=code, protocol=protocol, budget=budget,
        exposure=OrderedDict(
            summary=(evid or {}).get('summary', {}).get('training_exposure'),
            consequence='no training rows from the 12 SWE-bench Verified repositories were found in the released SFT '
                        'data (11 of 12 re-queried by the verifier; matplotlib unresolved); SWE RL data and base-model '
                        'pretraining exposure are unknown, so contamination cannot be excluded for either model',
            near_duplicate_and_selection='SWE-smith includes neighbour repositories of SWE-bench projects (e.g. '
                                         'astroid, iniconfig, django/channels, daphne, patsy) and its toolkit profiles '
                                         'flag eval sets including SWE-bench_Verified; the Klear runner carries '
                                         'undocumented verified100/verified236 subsets and an unnamed RL validation '
                                         'set, so selection on Verified cannot be excluded (klear_evidence.json)'),
        host=host, peers=peers,
        memory_rule=rule, disk_rule=disk_rule, disk=disk, admission=admission, envelopes=envelopes,
        exclusions=OrderedDict(req019_exclude_70_sha256=inv['exposure']['exclude_id_list_sha256'],
                               req019_exclude_89_sha256=inv['exposure']['exclude_including_lead_rules_sha256'],
                               note='unchanged; a later qualification would use already exposed development tasks'),
        evidence=evid, not_modelled=[
            'llama.cpp compute/graph buffers of two servers (outside the REQ-014 static rule)',
            'the pinned llama-server default prompt cache of up to 8192 MiB per server',
            'the episode-time 10 % free reserve (only the post-load 20 % reserve is projected)',
            'wall-clock budgets of 48 or 100 calls', 'the model\'s action-format behaviour under the text harness'])
    ledger['verdict'] = OrderedDict(
        per_envelope=OrderedDict((k, OrderedDict(verdict=v['verdict'], failing_gates=v['failing_gates'],
                                                  f16_arithmetic=v['memory']['f16']['arithmetic']))
                                 for k, v in envelopes.items()),
        overall='BLOCKED' if not any(v['feasible'] for v in envelopes.values()) else 'FEASIBLE for ' + ', '.join(
            k for k, v in envelopes.items() if v['feasible']),
        rule='simultaneous serving of both models (call-level routing): the REQ-019 joint extension of the per-model '
             'REQ-014 static rule (both weights and f16 KV caches + one 16 GiB VM allowance <= hw.memsize - 2 GiB) and '
             'the post-load 20 % free reserve on the current host reading; sequential serving is not treated as evidence '
             'that call-level routing is feasible; q8_0 KV and smaller VM allowances are sensitivities for the lead, not '
             'the verdict')
    return ledger


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    ap.add_argument('--out', default=None)
    ap.add_argument('--force', action='store_true', help='replace an existing feasibility.json (its live host readings)')
    a = ap.parse_args(argv)
    out = Path(a.out) if a.out else ROOT / OUT_REL
    if (out / 'feasibility.json').exists() and not a.force:
        print('refusing to overwrite %s (recorded host readings); pass --force' % (out / 'feasibility.json'))
        return 2
    ledger = build()
    out.mkdir(parents=True, exist_ok=True)
    (out / 'feasibility.json').write_text(json.dumps(ledger, indent=1, default=str) + '\n')
    print(json.dumps(ledger['verdict'], indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
