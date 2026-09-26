"""DTR-REQ-019 (lead e6a1670, docs/theory_feedback_20260926_req018_review.md): source-only qualification inventory of
the currently available, locally runnable open-weight checkpoints for a fresh SWE-bench Verified repository-repair
executor pair, under the pinned mini-swe-agent / SWE-bench harness.

No download, model call, server, container start, paid service or archive change. It reads only local files, git,
and read-only host probes (sysctl, memory_pressure, statvfs, ps/lsof, `colima list`, and `df` inside the
already running Colima VM), and writes under results/v2_adapter/req019_executor_inventory_20260926/:

    inventory.json   host envelope and peers, harness/dataset pins, every local causal-LM checkpoint (location,
                     revision, weight files with sha256, license, architecture, context, KV size at the frozen
                     16384-token slot, servability by the pinned llama.cpp), the exposed-task exclusion list,
                     the competence evidence (competence_evidence.json, cited, read-only web research), the
                     per-criterion candidate matrix and the feasibility verdict
    candidate_matrix.csv   one row per checkpoint

External volumes are only counted (weight files >= 100 MB), never listed.

    .venv/bin/python experiments/v2_adapter/req019_executor_inventory.py [--out DIR]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOME = Path.home()
REQUEST = 'DTR-REQ-019'
OUT_REL = 'results/v2_adapter/req019_executor_inventory_20260926'
GiB = 1 << 30
HF_HUB = HOME / '.cache/huggingface/hub'
SCAN_DIRS = OrderedDict([                       # label -> directory holding one checkpoint per subdirectory
    ('repo_work_hf', ROOT / 'work/models/hf'),
    ('repo_work_gguf', ROOT / 'work/models'),
])
# everything else under the home directory (outside the HF cache, this repository and ~/Library) is found by a generic
# scan and published anonymously: its provenance cannot be bound to a public release revision
WEIGHT_EXT = ('.gguf', '.safetensors', '.bin', '.pth')
MIN_WEIGHT = 100 * (1 << 20)
# the frozen v2 contract (configs/v2_req014_14b_capacity_probe_20260924.json: settings, memory_rule, disk_rule)
CONTRACT_MANIFEST = 'configs/v2_req014_14b_capacity_probe_20260924.json'
CLOSED = {'Qwen/Qwen2.5-Coder-7B-Instruct', 'Qwen/Qwen2.5-Coder-14B-Instruct', 'Qwen/Qwen2.5-Coder-7B-Instruct-GGUF',
          'mlx-community/Qwen2.5-Coder-7B-Instruct-4bit'}
REQ008 = 'results/v2_adapter/req008_pool_inventory.json'
REQ009 = 'results/v2_adapter/req009_component_queue.json'
POST_REQ008_MODEL_EPISODES = OrderedDict([      # instance -> manifests of model-outcome episodes after REQ-008 (24 Sep)
    ('astropy__astropy-14598', ['configs/v2_req011_competence_pair_20260924.json',
                                'configs/v2_req012_repair_probe_20260924.json',
                                'configs/v2_req014_14b_capacity_probe_20260924.json'])])
POST_REQ008_OTHER_TOUCHES = OrderedDict([        # touches after REQ-008 that are not model-outcome episodes
    ('astropy__astropy-14598', ['results/v2_adapter/req010_sentinel_20260924 (evaluator qualification sentinel)',
                                'configs/v2_req013_14b_discriminator_20260924.json (step 1 without a model; the 14B '
                                'episode was BLOCKED for capacity)'])])
ID_PATTERN = re.compile(r'\b[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+-[0-9]+\b')
EVIDENCE = OUT_REL + '/competence_evidence.json'
Q4_BYTES_PER_PARAM = 4.97 / 8


def canonical(key):
    """the model a checkpoint is a copy of: organization, format suffix and local file decorations removed."""
    k = key.split('/')[-1]
    k = re.sub(r'-(GGUF|gguf)$', '', k)
    k = re.sub(r'-(q4_k_m|bf16|[0-9]+bit)(\.gguf)?$', '', re.sub(r'\.gguf$', '', k), flags=re.I)
    k = re.sub(r'-[0-9a-f]{7}$', '', k)
    return k.lower()
RELAXED_CTX = 32768                              # the smallest context used by the cited Qwen3-4B evidence (SWE-MeM, 32k)
COLIMA = HOME / '.local/dtr-runtime/bin/colima'


def sh(cmd, env=None, timeout=60):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, '', str(e)


def git(*args):
    return sh(['git', '--no-replace-objects', '-C', str(ROOT)] + list(args))[1].strip()


def sha_file(path, cache):
    st = path.stat()
    key = '%s|%d|%d' % (path, st.st_size, int(st.st_mtime))
    if key not in cache:
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(1 << 24), b''):
                h.update(chunk)
        cache[key] = h.hexdigest()
    return cache[key]


# ------------------------------------------------------------------ GGUF metadata (header only)
GGUF_TYPES = {0: '<B', 1: '<b', 2: '<H', 3: '<h', 4: '<I', 5: '<i', 6: '<f', 7: '<?', 10: '<Q', 11: '<q', 12: '<d'}


def gguf_meta(path, wanted_prefixes=('general.', 'tokenizer.chat_template')):
    """Scalar/string metadata from a GGUF header (v2/v3), skipping arrays; architecture keys kept whole."""
    out = OrderedDict()
    with open(path, 'rb') as f:
        if f.read(4) != b'GGUF':
            return None
        version, = struct.unpack('<I', f.read(4))
        n_tensors, n_kv = struct.unpack('<QQ', f.read(16))

        def rstr():
            n, = struct.unpack('<Q', f.read(8))
            return f.read(n).decode('utf-8', 'replace')

        def rval(t):
            if t == 8:
                return rstr()
            if t == 9:
                et, n = struct.unpack('<IQ', f.read(12))
                for _ in range(n):
                    rval(et)
                return '<array %d>' % n
            fmt = GGUF_TYPES[t]
            return struct.unpack(fmt, f.read(struct.calcsize(fmt)))[0]
        for _ in range(n_kv):
            k = rstr()
            t, = struct.unpack('<I', f.read(4))
            v = rval(t)
            if t != 9 and (k.startswith(wanted_prefixes) or '.' in k):
                out[k] = v if k != 'tokenizer.chat_template' else ('<template %d chars>' % len(v))
        out['_gguf_version'] = version
        out['_n_tensors'] = n_tensors
    return out


FILE_TYPES = {0: 'F32', 1: 'F16', 7: 'Q8_0', 15: 'Q4_K_M', 17: 'Q5_K_M', 18: 'Q6_K', 32: 'BF16'}


def readme_license(text):
    m = re.search(r'^---\s*\n(.*?)\n---', text, re.S)
    if m:
        lm = re.search(r'^license:\s*(\S+)', m.group(1), re.M)
        if lm:
            return lm.group(1).strip('"\'')
    return None


# ------------------------------------------------------------------ checkpoints
def weight_files(d):
    """every weight file of a checkpoint directory (any size), if at least one is >= MIN_WEIGHT; else []."""
    files = sorted(p for p in d.rglob('*') if p.is_file() and p.suffix in WEIGHT_EXT)
    return files if any(p.stat().st_size >= MIN_WEIGHT for p in files) else []


def index_check(d, files):
    """compare the listed files with the shard index (model.safetensors.index.json), when there is one."""
    idx = d / 'model.safetensors.index.json' if d.is_dir() else None
    if not idx or not idx.exists():
        return OrderedDict(index=None, complete=True)
    need = sorted(set(json.loads(idx.read_text())['weight_map'].values()))
    have = sorted(f.name for f in files)
    return OrderedDict(index=idx.name, shards_in_index=len(need), missing=[n for n in need if n not in have],
                       complete=all(n in have for n in need))


def arch_numbers(cfg=None, meta=None):
    """layers, kv heads, head dim, max context from config.json or GGUF metadata."""
    if cfg:
        cfg = cfg.get('text_config', cfg)
        heads = cfg.get('num_attention_heads')
        head_dim = cfg.get('head_dim') or (cfg.get('hidden_size') // heads if heads else None)
        return OrderedDict(architecture=(cfg.get('architectures') or [cfg.get('model_type')])[0],
                           model_type=cfg.get('model_type'), layers=cfg.get('num_hidden_layers'),
                           kv_heads=cfg.get('num_key_value_heads', heads), head_dim=head_dim,
                           max_context=cfg.get('max_position_embeddings'))
    if meta:
        a = meta.get('general.architecture')
        heads = meta.get('%s.attention.head_count' % a)
        emb = meta.get('%s.embedding_length' % a)
        return OrderedDict(architecture=a, model_type=a, layers=meta.get('%s.block_count' % a),
                           kv_heads=meta.get('%s.attention.head_count_kv' % a, heads),
                           head_dim=meta.get('%s.attention.key_length' % a) or (emb // heads if emb and heads else None),
                           max_context=meta.get('%s.context_length' % a))
    return OrderedDict()


def kv_bytes(n, ctx):
    if not all(n.get(k) for k in ('layers', 'kv_heads', 'head_dim')):
        return None
    return 2 * n['layers'] * n['kv_heads'] * n['head_dim'] * ctx * 2          # K and V, f16 cache


def hf_checkpoints(cache):
    rows = []
    for d in sorted(HF_HUB.glob('models--*')):
        repo = d.name[len('models--'):].replace('--', '/', 1)
        snaps = sorted((d / 'snapshots').glob('*'))
        ref = (d / 'refs/main').read_text().strip() if (d / 'refs/main').exists() else None
        for s in snaps:
            wf = [p for p in sorted(s.iterdir()) if p.suffix in WEIGHT_EXT and p.exists()]
            if not any(p.stat().st_size >= MIN_WEIGHT for p in wf):
                wf = []
            cfg = json.loads((s / 'config.json').read_text()) if (s / 'config.json').exists() else None
            readme = (s / 'README.md').read_text(errors='replace') if (s / 'README.md').exists() else ''
            rows.append(dict(location='hf_cache', path='~/.cache/huggingface/hub/%s/snapshots/%s' % (d.name, s.name),
                             repo=repo, revision=s.name, ref_main=ref, files=wf, cfg=cfg, dir=s,
                             license_readme=readme_license(readme),
                             license_file=(s / 'LICENSE').exists()))
    return rows


def dir_checkpoints():
    rows = []
    for label, base in SCAN_DIRS.items():
        if not base.exists():
            continue
        if label == 'repo_work_gguf':
            for g in sorted(p for p in base.rglob('*.gguf') if p.stat().st_size >= MIN_WEIGHT):
                rows.append(dict(location=label, path=_rel(g), repo=None, revision=None, ref_main=None, files=[g],
                                 cfg=None, license_readme=None, license_file=False, dir=g))
            continue
        for d in sorted(p for p in base.iterdir() if p.is_dir()):
            wf = weight_files(d)
            if not wf:
                continue
            cfg = json.loads((d / 'config.json').read_text()) if (d / 'config.json').exists() else None
            readme = (d / 'README.md').read_text(errors='replace') if (d / 'README.md').exists() else ''
            m = re.match(r'(.+)@([0-9a-f]{7,40})$', d.name)
            rev = full_revision(m.group(2)) if m else None
            rows.append(dict(location=label, path=_rel(d), repo=('Qwen/' + m.group(1)) if m else None,
                             revision=rev, ref_main=None, files=wf, cfg=cfg, dir=d,
                             license_readme=readme_license(readme), license_file=(d / 'LICENSE').exists()))
    return rows


def home_checkpoints():
    rc, out, _ = sh(['find', str(HOME), '-xdev', '(', '-name', '*.gguf', '-o', '-name', '*.safetensors', ')', '-size',
                     '+100M'], timeout=900)
    skip = (str(HF_HUB), str(ROOT), str(HOME / 'Library'), str(HOME / '.Trash'))
    groups = OrderedDict()
    for line in sorted(l for l in out.splitlines() if l.strip()):
        f = Path(line)
        if str(f).startswith(skip):
            continue
        groups.setdefault(f if f.suffix == '.gguf' else f.parent, []).append(f)
    rows = []
    for d, files in groups.items():
        if d.is_dir():
            files = weight_files(d)                  # all shards of the checkpoint, not only the >= 100 MB ones
        cfg_path = (d if d.is_dir() else d.parent) / 'config.json'
        cfg = json.loads(cfg_path.read_text()) if d.is_dir() and cfg_path.exists() else None
        rows.append(dict(location='other_local', path=str(d), repo=None, revision=None, ref_main=None,
                         files=sorted(files), cfg=cfg, license_readme=None, license_file=False, dir=d))
    return rows


def full_revision(prefix):
    """the full revision of a repo-pinned download (work/models/hf/download_pinned.py PINS), else the prefix."""
    src = ROOT / 'work/models/hf/download_pinned.py'
    text = src.read_text() if src.exists() else ''
    m = re.search(r'\b(%s[0-9a-f]{%d})\b' % (re.escape(prefix), 40 - len(prefix)), text)
    return m.group(1) if m else prefix


def _rel(p):
    p = Path(p)
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return '~/' + str(p.relative_to(HOME))


def external_weight_count():
    vols = [v for v in Path('/Volumes').iterdir() if v.is_dir() and not v.is_symlink()] if Path('/Volumes').exists() else []
    n = 0
    for v in vols:
        rc, out, _ = sh(['find', str(v), '-maxdepth', '9', '(', '-name', '*.gguf', '-o', '-name', '*.safetensors', ')',
                         '-size', '+100M'], timeout=300)
        n += len([l for l in out.splitlines() if l.strip()])
    return OrderedDict(external_volumes_scanned=len(vols), weight_files_at_least_100MB=n,
                       note='counted read-only (depth 9); contents never listed')


# ------------------------------------------------------------------ host, peers, harness
def host_envelope():
    rc, out, _ = sh(['sysctl', '-n', 'hw.memsize'])
    memsize = int(out.strip()) if rc == 0 and out.strip().isdigit() else None
    rc, mp, _ = sh(['memory_pressure'], timeout=30)
    m = re.search(r'System-wide memory free percentage:\s*(\d+)%', mp or '')
    vm = None
    rc, out, _ = sh([str(COLIMA), 'ssh', '--profile', 'dtr', '--', 'df', '-Pk', '/var/lib/docker'],
                    env=dict(os.environ, PATH='%s:%s' % (COLIMA.parent, os.environ.get('PATH', ''))), timeout=60)
    rows = [f for f in (x.split() for x in (out or '').splitlines())
            if len(f) >= 6 and all(v.isdigit() for v in f[1:4]) and f[4].endswith('%')]
    if rc == 0 and len(rows) == 1:
        vm = int(rows[0][3]) / (1 << 20)
    rc, cl, _ = sh([str(COLIMA), 'list'], env=dict(os.environ, PATH='%s:%s' % (COLIMA.parent, os.environ.get('PATH', ''))))
    colima = [l.split() for l in (cl or '').splitlines()[1:] if l.strip()]
    return OrderedDict(
        hw_model=sh(['sysctl', '-n', 'hw.model'])[1].strip(), cpu=sh(['sysctl', '-n', 'machdep.cpu.brand_string'])[1].strip(),
        hw_memsize_bytes=memsize, memory_free_pct=int(m.group(1)) if m else None,
        swap=sh(['sysctl', '-n', 'vm.swapusage'])[1].strip(),
        host_disk_free_gib=round(shutil.disk_usage(str(ROOT)).free / GiB, 2),
        colima=[OrderedDict(profile=c[0], status=c[1], arch=c[2], cpus=c[3], memory=c[4], disk=c[5]) for c in colima
                if len(c) >= 6],
        vm_disk_free_gib=None if vm is None else round(vm, 2),
        load_average=os.getloadavg())


PEER_NAMES = ('llama-server', 'mlx_lm', 'ollama', 'run.py', 'mini', 'swebench', 'vllm', 'lmstudio', 'python')


def peers():
    rc, out, _ = sh(['ps', '-axo', 'pid=,pcpu=,rss=,comm='])
    rows = []
    for line in out.splitlines():
        f = line.split(None, 3)
        if len(f) == 4 and any(n in Path(f[3]).name for n in ('llama-server', 'mlx_lm', 'ollama', 'vllm', 'LM Studio')):
            rows.append(OrderedDict(comm=Path(f[3]).name, pcpu=float(f[1]), rss_gib=round(int(f[2]) / (1 << 20), 2)))
    rc, lsof, _ = sh(['lsof', '-nP', '-iTCP', '-sTCP:LISTEN'])
    ports = sorted({(int(m.group(2)), m.group(1)) for m in re.finditer(r'^(\S+)\s.*:(\d+) \(LISTEN\)', lsof or '', re.M)
                    if 8000 <= int(m.group(2)) < 9000})
    ports = [OrderedDict(port=p, command=c) for p, c in ports]
    stage = sh(['pgrep', '-f', 'run.py --stage'])[1].split()
    return OrderedDict(model_server_processes=rows, listening_ports_8000_8999=ports, code_routing_stage_processes=len(stage),
                       rule='names/ports only; no sibling process is touched')


def first_license_line(d):
    f = next((d / n for n in ('LICENSE', 'LICENSE.md', 'LICENSE.txt', 'COPYING') if (d / n).exists()), None)
    return f.read_text(errors='replace').strip().splitlines()[0].strip() if f else None


def harness_pins():
    c = json.loads((ROOT / CONTRACT_MANIFEST).read_text())
    freeze = ROOT / 'work/venvs/minisweagent_04d809c_freeze.txt'
    sfreeze = ROOT / 'work/venvs/swebench_f7bbbb2_freeze.txt'
    lb = ROOT / 'work/upstream/llama.cpp-4fea119/build/bin/llama-server'
    arch_src = (ROOT / 'work/upstream/llama.cpp-4fea119/src/llama-arch.cpp')
    arch_text = arch_src.read_text() if arch_src.exists() else ''
    supported = sorted(set(re.findall(r'\{\s*LLM_ARCH_\w+,\s*"([a-z0-9_\-]+)"\s*\}', arch_text)))
    r8 = json.loads((ROOT / REQ008).read_text())
    return OrderedDict(
        contract_manifest=CONTRACT_MANIFEST, contract_manifest_sha256=hashlib.sha256((ROOT / CONTRACT_MANIFEST).read_bytes()).hexdigest(),
        settings=c['settings'], memory_rule=c['memory_rule'], disk_rule=c['disk_rule'],
        serving=OrderedDict((k, c['serving'][k]) for k in ('llama_cpp_commit', 'llama_server', 'flags')),
        llama_server_present=lb.exists(), llama_server_sha256=hashlib.sha256(lb.read_bytes()).hexdigest() if lb.exists() else None,
        llama_cpp_supported_architectures=supported, converter_registered_classes=converter_classes(),
        mini_swe_agent_freeze_sha256=hashlib.sha256(freeze.read_bytes()).hexdigest() if freeze.exists() else None,
        swebench_freeze_sha256=hashlib.sha256(sfreeze.read_bytes()).hexdigest() if sfreeze.exists() else None,
        dataset=OrderedDict((k, r8['pins'][k]) for k in ('dataset', 'dataset_revision', 'dataset_sha256', 'evaluator_commit',
                                                        'n_rows', 'id_set_sha256')),
        harness_sources=OrderedDict(
            (name, OrderedDict(present=(ROOT / d).exists(), license=first_license_line(ROOT / d),
                               venv_present=(ROOT / v).exists()))
            for name, d, v in (('mini-swe-agent', 'work/upstream/mini-swe-agent-04d809ceab9df28f9adaed044884180159172930',
                                'work/venvs/minisweagent_04d809c'),
                               ('SWE-bench', 'work/upstream/SWE-bench-f7bbbb2ccdf479001d6467c9e34af59e44a840f9',
                                'work/venvs/swebench_f7bbbb2'),
                               ('llama.cpp', 'work/upstream/llama.cpp-4fea119', 'work/venvs/llamacpp_4fea119'))),
        evaluator_controls=OrderedDict(
            runtime_qualification='results/v2_adapter/qualification_20260922 (no-change and reference-patch controls)',
            sentinel='results/v2_adapter/req010_sentinel_20260924 (astropy__astropy-14598)'))


def exposure():
    r8 = json.loads((ROOT / REQ008).read_text())
    cat = {r['instance_id']: r['category']['conservative'] for r in r8['rows']}
    exposed = sorted(i for i, c in cat.items() if c == 'model_outcome_exposed')
    touched = sorted(i for i, c in cat.items() if c == 'qualification_or_inspection_only')
    delta = OrderedDict()
    for iid, manifests in POST_REQ008_MODEL_EPISODES.items():
        ok = all(json.loads((ROOT / m).read_text()).get('instance_id') == iid for m in manifests)
        delta[iid] = OrderedDict(manifests=manifests, manifests_agree=ok, req008_category=cat.get(iid))
    exclude = sorted(set(exposed) | set(touched) | set(delta))
    q9 = json.loads((ROOT / REQ009).read_text()) if (ROOT / REQ009).exists() else {}
    queue = [x if isinstance(x, str) else x.get('instance_id') for x in (q9.get('queue') or [])]
    reasons = OrderedDict()
    for iid, why in sorted((q9.get('exclusion_reason') or {}).items()):
        reasons.setdefault(why, []).append(iid)
    lead_rule = OrderedDict((k, sorted(v)) for k, v in sorted(reasons.items())
                            if k in ('component_touches_exposed_or_qualification_only', 'empty_pass_to_pass'))
    all_ids = {r['instance_id'] for r in r8['rows']}
    scanned = OrderedDict()
    for f in sorted((ROOT / 'configs').glob('v2_*.json')):
        ids = sorted(set(ID_PATTERN.findall(f.read_text())) & all_ids)
        if ids:
            scanned[str(f.relative_to(ROOT))] = ids
    unexplained = sorted({i for v in scanned.values() for i in v} - set(exclude))

    def idsha(ids):
        return hashlib.sha256(''.join(i + '\n' for i in sorted(ids)).encode()).hexdigest()
    total = sorted(set(exclude) | {i for v in lead_rule.values() for i in v})
    return OrderedDict(
        definition='conservative (lead 0fe40b8): model-outcome episodes incl. third-party recorded episodes, plus the '
                   '5 qualification-or-inspection-only IDs and the post-REQ-008 exposure',
        req008_source=REQ008, req008_sha256=hashlib.sha256((ROOT / REQ008).read_bytes()).hexdigest(),
        req008_model_outcome_exposed=exposed, req008_qualification_or_inspection_only=touched,
        post_req008_model_outcome_exposed=delta,
        exclude_from_untouched_evaluation=exclude, n_exclude=len(exclude), exclude_id_list_sha256=idsha(exclude),
        post_req008_other_touches=POST_REQ008_OTHER_TOUCHES,
        lead_rule_additional_exclusions=lead_rule,
        exclude_including_lead_rules=total, n_exclude_including_lead_rules=len(total),
        exclude_including_lead_rules_sha256=idsha(total),
        config_scan=OrderedDict(files_with_pinned_ids=scanned, ids_not_in_exclude=unexplained,
                                rule='every committed configs/v2_*.json mentioning a pinned SWE-bench Verified ID; '
                                     'an ID outside the exclusion list would need review'),
        req009_sha256=hashlib.sha256((ROOT / REQ009).read_bytes()).hexdigest() if (ROOT / REQ009).exists() else None,
        req009_design_queue=queue,
        req009_design_queue_remaining_unexposed=[q for q in queue if q not in set(exclude)],
        note='the REQ-008 scanner at HEAD fails closed (new artifacts after its source checkpoint); the delta since '
             'REQ-008 is enumerated from the committed REQ-010 sentinel and the REQ-011, REQ-012 and REQ-014 episode '
             'manifests, all on astropy__astropy-14598 (REQ-013 ran no model episode), and cross-checked by the config '
             'scan; REQ-015..017 are MiniWoB browser tasks, not SWE-bench. exclude_including_lead_rules adds the lead\'s '
             'REQ-009 rules (0fe40b8): component-mates of exposed or qualification-only tasks and empty PASS_TO_PASS')


# ------------------------------------------------------------------ build
PURPOSE = [                                        # (case-insensitive regex on repo/path, purpose class)
    (r'prover|leandojo', 'theorem_prover'),
    (r'gte-|byt5', 'encoder_or_embedding'), (r'coder', 'code_instruct'), (r'instruct', 'general_instruct')]


def classify(row):
    key = '%s %s' % (row.get('repo') or '', row['path'])
    return next((c for rx, c in PURPOSE if re.search(rx, key, re.I)), 'unclassified')


def converter_classes():
    base = ROOT / 'work/upstream/llama.cpp-4fea119'
    text = ''.join(f.read_text() for f in [base / 'convert_hf_to_gguf.py'] + sorted((base / 'conversion').glob('*.py'))
                   if f.exists())
    return sorted({n for args in re.findall(r'register\(([^)]*)\)', text) for n in re.findall(r'"([A-Za-z0-9_]+)"', args)})


def build(cache):
    ctx = json.loads((ROOT / CONTRACT_MANIFEST).read_text())['settings']['context_per_slot']
    mem = json.loads((ROOT / CONTRACT_MANIFEST).read_text())['memory_rule']
    host = host_envelope()
    pins = harness_pins()
    raw = hf_checkpoints(cache) + dir_checkpoints() + home_checkpoints()
    convert = converter_classes()
    evid = json.loads((ROOT / EVIDENCE).read_text()) if (ROOT / EVIDENCE).exists() else None
    ev_by = {k: e for e in (evid or {}).get('models', []) for k in [e['model_key']] + e.get('aliases', [])}
    checkpoints = []
    for r in raw:
        if not r['files']:
            continue
        files = []
        meta = None
        for f in r['files']:
            real = f.resolve()
            files.append(OrderedDict(name=f.name, bytes=real.stat().st_size, sha256=sha_file(real, cache)))
            if f.suffix == '.gguf' and meta is None:
                meta = gguf_meta(real)
        nums = arch_numbers(r['cfg'], meta)
        fmt = 'gguf' if all(x['name'].endswith('.gguf') for x in files) else 'safetensors'
        total = sum(x['bytes'] for x in files)
        quant = FILE_TYPES.get(meta.get('general.file_type'), meta.get('general.file_type')) if meta else None
        purpose = 'other_local_unverified_provenance' if r['location'] == 'other_local' else classify(r)
        key = (r.get('repo') or Path(r['path']).name)
        arch = (nums.get('model_type') or '').lower()
        mlx_quant = bool(r['cfg'] and (r['cfg'].get('quantization') or 'mlx' in r['path'].lower()))
        enc_dec = bool((r['cfg'] or {}).get('is_encoder_decoder')) or 'ConditionalGeneration' in str(nums.get('architecture'))
        if enc_dec:
            servable_arch = False
        elif fmt == 'gguf':
            servable_arch = arch in pins['llama_cpp_supported_architectures']
        else:
            servable_arch = (not mlx_quant) and nums.get('architecture') in convert
        how = ('encoder-decoder: the pinned llama-server has no encoder path' if enc_dec else
               'gguf, architecture in llama-arch.cpp' if fmt == 'gguf' else
               'MLX-quantized weights: not convertible by convert_hf_to_gguf' if mlx_quant else
               'safetensors: class registered in the pinned convert_hf_to_gguf.py' if servable_arch else
               'safetensors: class not registered in the pinned converter')
        kv = kv_bytes(nums, ctx)
        dtype = (r['cfg'] or {}).get('torch_dtype')
        mlx_bits = ((r['cfg'] or {}).get('quantization') or {}).get('bits') if r['cfg'] else None
        if fmt == 'gguf':
            params = None if quant in ('Q4_K_M',) else total / {'BF16': 2, 'F16': 2, 'F32': 4}.get(quant, 2)
        elif mlx_bits:
            params = None
        else:
            params = total / {'float32': 4}.get(dtype, 2)
        # Q4_K_M: the file itself; else ~4.97 bits/weight (the local Q4_K_M files average 4.97 bpw)
        q4_est = total if fmt == 'gguf' and quant == 'Q4_K_M' else (int(params * Q4_BYTES_PER_PARAM) if params else None)
        if mlx_bits:
            quant = 'MLX %d-bit' % mlx_bits
        proj = None if kv is None or q4_est is None else q4_est + kv + int(mem['vm_gib'] * GiB)
        limit = host['hw_memsize_bytes'] - mem['margin_gib'] * GiB if host['hw_memsize_bytes'] else None
        lic = r['license_readme'] or (meta or {}).get('general.license') or ('LICENSE file present' if r['license_file'] else None)
        closed = key in CLOSED or 'qwen2.5-coder' in r['path'].lower()
        ev = ev_by.get(key) or ev_by.get(re.sub(r'-GGUF$', '', key)) or ev_by.get(Path(r['path']).name)
        lic_source = 'local' if lic else None
        if r['location'] == 'other_local':
            ev = None
        if not lic and ev and ev.get('license_public'):
            lic, lic_source = ev['license_public'], 'public model card: %s' % ev.get('license_url')
        digests = sorted(f['sha256'] for f in files)
        idx = index_check(r['dir'], r['files']) if r.get('dir') is not None and Path(r['dir']).is_dir() else \
            OrderedDict(index=None, complete=True)
        dup = next((c['key'] for c in checkpoints if c.get('_digests') == digests), None)
        if r['location'] == 'other_local':                 # published anonymously: no name, path or digest
            n_other = sum(1 for c in checkpoints if c['location'] == 'other_local') + 1
            key, files = 'other-local-%02d' % n_other, [OrderedDict(n_files=len(files))]
            r = dict(r, path='(outside the HF cache and this repository; not listed)')
            lic, ev, idx = None, None, OrderedDict(complete=idx['complete'])
        checkpoints.append(OrderedDict(
            key=key, location=r['location'], path=r['path'], repo=r.get('repo'), revision=r.get('revision'),
            ref_main=r.get('ref_main'), purpose=purpose, format=fmt, quantization=quant, weight_bytes=total,
            files=files, license=lic, architecture=nums.get('architecture'), model_type=nums.get('model_type'),
            max_context=nums.get('max_context'), layers=nums.get('layers'), kv_heads=nums.get('kv_heads'),
            head_dim=nums.get('head_dim'), kv_bytes_at_contract_ctx=kv, servable_by_pinned_llama_cpp=servable_arch,
            servability_basis=how, license_source=lic_source,
            needs_conversion_to_gguf=fmt != 'gguf', q4_gguf_bytes_estimate=q4_est,
            memory_projection_bytes=proj, memory_projection_limit_bytes=limit,
            closed_by_lead=closed, competence_evidence=ev, shard_index=idx, identical_to=dup,
            canonical_model=canonical(key if r['location'] != 'other_local' else key),
            snapshot_is_ref_main=(r.get('revision') == r.get('ref_main')) if r['location'] == 'hf_cache' else None,
            _digests=digests))
    ledger = OrderedDict(
        request=REQUEST, kind='source-only local executor inventory (no download, model call, server or container start)',
        lead_commit='e6a1670', lead_decision='docs/theory_feedback_20260926_req018_review.md',
        source_commit=git('rev-parse', 'HEAD'),
        builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        evidence_sha256=hashlib.sha256((ROOT / EVIDENCE).read_bytes()).hexdigest() if (ROOT / EVIDENCE).exists() else None,
        host=host, peers=peers(), harness=pins, external=external_weight_count(),
        exposure=exposure(), competence_evidence_source=EVIDENCE if evid else None,
        competence_evidence_method=(evid or {}).get('method'),
        checkpoints=checkpoints)
    ledger['matrix'], ledger['verdict'] = evaluate(ledger)
    for c in checkpoints:
        c.pop('_digests', None)
    return ledger


CRITERIA = OrderedDict([
    ('C1_present', 'weights present locally (no download)'),
    ('C2_servable', 'architecture served by the pinned llama.cpp 4fea119 (GGUF, or safetensors convertible by its converter)'),
    ('C3_license', 'a license is recorded locally or in the cited public model card'),
    ('C4_not_closed', 'not the closed Qwen2.5-Coder-7B/14B pair (lead e6a1670)'),
    ('C5_purpose', 'a public general or code instruction release with a bindable revision (not a theorem prover, an '
                   'encoder, or a checkpoint of unverified provenance outside the HF cache and this repository)'),
    ('C6_context', 'max context >= the frozen 16384-token slot'),
    ('C7_memory', 'REQ-014 static projection (q4 GGUF + KV + VM) <= hw.memsize - margin'),
    ('C8_competence', 'independent (not vendor-only) published SWE-bench Verified evidence with a resolve rate above zero '
                      'under a contract comparable to the frozen one (mini-swe-agent-style bash text actions, <= 16384-'
                      'token context, <= 24 steps)'),
])


def evaluate(ledger):
    rows = []
    for c in ledger['checkpoints']:
        ev = c['competence_evidence'] or {}
        crit = OrderedDict(
            C1_present=True, C2_servable=bool(c['servable_by_pinned_llama_cpp']), C3_license=bool(c['license']),
            C4_not_closed=not c['closed_by_lead'], C5_purpose=c['purpose'] in ('general_instruct', 'code_instruct'),
            C6_context=bool(c['max_context'] and c['max_context'] >= ledger['harness']['settings']['context_per_slot']),
            C7_memory=bool(c['memory_projection_bytes'] and c['memory_projection_limit_bytes'] and
                           c['memory_projection_bytes'] <= c['memory_projection_limit_bytes']),
            C8_competence=bool(ev.get('independent_swebv_comparable_contract')))
        crit['C1_present'] = bool((c.get('shard_index') or {}).get('complete', True))
        rows.append(OrderedDict(key=c['key'], path=c['path'], purpose=c['purpose'],
                                canonical_model=c.get('canonical_model', c['key']), **crit,
                                any_independent_swebv_evidence=bool(ev.get('independent_swebv_any')),
                                eligible_small=all(v for k, v in crit.items() if k != 'C8_competence'),
                                eligible_large=all(crit.values())))
    large = [r['key'] for r in rows if r['eligible_large']]
    small = [r['key'] for r in rows if r['eligible_small']]
    model = {r['key']: r['canonical_model'] for r in rows}

    def pairs(bigs, smalls):
        return sorted({(b, s) for b in bigs for s in smalls if model[b] != model[s]})
    feasible = bool(pairs(large, small))
    by_key = {c['key']: c for c in ledger['checkpoints']}
    relaxed_large = [r['key'] for r in rows if r['eligible_small'] and r['any_independent_swebv_evidence']]
    vm = ledger['harness']['memory_rule']['vm_gib'] * GiB
    limit = (ledger['host']['hw_memsize_bytes'] - ledger['harness']['memory_rule']['margin_gib'] * GiB) \
        if ledger.get('host', {}).get('hw_memsize_bytes') else None
    wide = OrderedDict()
    for k in sorted(set(small)):
        c = by_key[k]
        kv = kv_bytes(c, RELAXED_CTX)
        wide[k] = OrderedDict(kv_bytes_at_32768=kv, q4_gguf_bytes_estimate=c['q4_gguf_bytes_estimate'],
                              single_projection_bytes=None if kv is None else c['q4_gguf_bytes_estimate'] + kv + vm)
    co = OrderedDict()
    for a_, b_ in sorted({tuple(sorted((a, b))) for a in small for b in small if model[a] != model[b]}):
        row = OrderedDict()
        for ctx in (ledger['harness']['settings']['context_per_slot'], RELAXED_CTX):
            ka, kb = kv_bytes(by_key[a_], ctx), kv_bytes(by_key[b_], ctx)
            tot = None if None in (ka, kb) else by_key[a_]['q4_gguf_bytes_estimate'] + by_key[b_]['q4_gguf_bytes_estimate'] + ka + kb + vm
            row['projection_bytes_at_%d' % ctx] = tot
            row['fits_at_%d' % ctx] = bool(tot is not None and limit is not None and tot <= limit)
        co['%s + %s' % (a_, b_)] = row
    verdict = OrderedDict(
        feasible=feasible, status='FEASIBLE' if feasible else 'BLOCKED',
        criteria=CRITERIA, eligible_large=large, eligible_small=small,
        rule='a fresh pair needs at least one checkpoint meeting C1-C8 (the stronger executor) and a second checkpoint '
             'of a different model meeting C1-C7; the criteria are the worker\'s operationalization of the lead\'s '
             'acceptance for review, and the lead selects and freezes any pair',
        disclosure='C8 as operationalized cannot currently be met by any published evidence, local or not: no published '
                   'open-weight SWE-bench Verified result reports a run under a 24-step cap at 16384 tokens (on the '
                   'swebench.com Verified board the fewest mean mini-SWE-agent calls per instance among the 15 '
                   'open-weight entries is 27.6), and REQ-014 ended in a context-limit operational zero under this '
                   'contract; BLOCKED therefore follows from the frozen contract itself, and qualifying any pair needs a '
                   'lead decision on the contract',
        alternative_if_contract_relaxed=OrderedDict(
            note='NOT a verdict: what C8 would admit if the lead accepted independent SWE-bench Verified evidence obtained '
                 'under a different scaffold and larger budget (any agentic scaffold, any context/steps); this changes '
                 'the frozen contract, which is a lead decision',
            eligible_large=relaxed_large, eligible_small=small,
            pairs=[list(x) for x in pairs(relaxed_large, small)],
            pair_possible=bool(pairs(relaxed_large, small)),
            only_one_fresh_model_has_any_evidence=len({model[k] for k in relaxed_large}) == 1,
            memory_at_32768_context=wide,
            co_serving_distinct_models=co,
            co_serving_rule='a joint extension of the per-model REQ-014 static rule (which checks each model alone; the '
                            'frozen setup serves one model at a time): both GGUFs + both f16 KV caches + one VM '
                            'allowance <= hw.memsize - margin. Under the per-model rule every candidate fits at 32768 '
                            'tokens',
            memory_limit_bytes=(ledger['host']['hw_memsize_bytes'] - ledger['harness']['memory_rule']['margin_gib'] * GiB)
            if ledger.get('host', {}).get('hw_memsize_bytes') else None))
    return rows, verdict


def matrix_csv(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), lineterminator='\n')
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    ap.add_argument('--out', default=str(ROOT / OUT_REL))
    ap.add_argument('--hash-cache', default=str(ROOT / 'work/req019_sha256_cache.json'))
    a = ap.parse_args(argv)
    cpath = Path(a.hash_cache)
    cache = json.loads(cpath.read_text()) if cpath.exists() else {}
    ledger = build(cache)
    cpath.parent.mkdir(parents=True, exist_ok=True)
    cpath.write_text(json.dumps(cache, indent=0, sort_keys=True))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'inventory.json').write_text(json.dumps(ledger, indent=1, default=str) + '\n')
    (out / 'candidate_matrix.csv').write_text(matrix_csv(ledger['matrix']))
    print(json.dumps(OrderedDict(verdict=ledger['verdict']['status'], eligible_large=ledger['verdict']['eligible_large'],
                                 eligible_small=ledger['verdict']['eligible_small'],
                                 n_checkpoints=len(ledger['checkpoints']), n_exclude=ledger['exposure']['n_exclude'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
