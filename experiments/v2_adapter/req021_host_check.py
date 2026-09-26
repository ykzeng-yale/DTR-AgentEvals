"""DTR-REQ-021 (lead 9fae0e4, docs/theory_feedback_20260926_req020_decision.md): one-time check for an already
accessible, no-cost host that could keep the REQ-020 pair (Klear-AgentForge-8B + Qwen3-4B-Instruct-2507) resident under
the pinned evaluator for the common 32k/48-call DEVELOPMENT envelope.

Read-only and local: no connection to any other machine, no cloud API call, no download, server, VM change, inference,
reservation or task exposure. It (1) enumerates the host access configured on this machine (SSH host entries and known
hosts, cloud/cluster CLIs and their configuration, Docker contexts, Colima profiles) without contacting anything and
without publishing names, and (2) measures this host and applies the conservative admission rule the lead asked for:
both weights and f16 KV at 32768 tokens + the 16 GiB evaluator-VM allowance + compute buffers + prompt caches, with at
least 20 % of physical memory free after load. Writes OUT/host_check.json.

    .venv/bin/python experiments/v2_adapter/req021_host_check.py [--out DIR] [--force]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/v2_adapter'))
import req019_executor_inventory as INV  # noqa: E402

REQUEST = 'DTR-REQ-021'
OUT_REL = 'results/v2_adapter/req021_host_check_20260926'
REQ020 = 'results/v2_adapter/req020_pair_feasibility_20260926/feasibility.json'
GiB = 1 << 30
HOME = Path.home()
CLOUD_CLIS = ('gcloud', 'aws', 'az', 'kubectl', 'modal', 'runpod', 'runpodctl', 'vastai', 'lambda', 'sky', 'oci',
              'doctl', 'linode-cli', 'flyctl', 'tailscale', 'ngrok')
PROMPT_CACHE_DEFAULT_MIB = 8192                   # pinned llama.cpp common/common.h cache_ram_mib default, per server


def access_inventory():
    """configured access to other machines, counted locally (nothing is contacted, no name is published)."""
    hosts = ssh_hosts(HOME / '.ssh/config')
    kh = HOME / '.ssh/known_hosts'
    known = [l.split()[0].split(',')[0] for l in kh.read_text().splitlines() if l.strip() and not l.startswith('#')] \
        if kh.exists() else []
    code_hosting = {'github.com', 'gitlab.com', 'bitbucket.org', 'ssh.github.com', 'huggingface.co'}
    clis = OrderedDict((c, shutil.which(c) is not None) for c in CLOUD_CLIS)
    gcloud = OrderedDict(installed=clis['gcloud'], loads_with_default_python=None, account_configured=None,
                         project_configured=None, existing_instances_queried=False)
    if clis['gcloud']:
        rc, out, _ = INV.sh(['gcloud', 'config', 'list', '--format=value(core.account,core.project)'], timeout=60)
        gcloud['loads_with_default_python'] = rc == 0
        if rc != 0:                                  # the CLI needs a newer Python; read the same local config with ours
            env = dict(os.environ, CLOUDSDK_PYTHON=sys.executable, CLOUDSDK_COMPONENT_MANAGER_DISABLE_UPDATE_CHECK='1')
            rc, out, _ = INV.sh(['gcloud', 'config', 'list', '--format=value(core.account,core.project)'], env=env,
                                timeout=60)
        if rc == 0:
            parts = (out.strip().split('\t') + ['', ''])[:2]
            gcloud['account_configured'], gcloud['project_configured'] = bool(parts[0].strip()), bool(parts[1].strip())
    env = dict(os.environ, PATH='%s:%s' % (INV.COLIMA.parent, os.environ.get('PATH', '')))
    rc, ctx, _ = INV.sh([str(INV.COLIMA.parent / 'docker'), 'context', 'ls', '--format', '{{.Name}} {{.DockerEndpoint}}'],
                        env=env)
    contexts = [l.split() for l in (ctx or '').splitlines() if l.strip()]
    remote_ctx = [c for c in contexts if len(c) > 1 and not c[1].startswith('unix://')]
    rc, cl, _ = INV.sh([str(INV.COLIMA), 'list'], env=env)
    profiles = [l.split()[0] for l in (cl or '').splitlines()[1:] if l.strip()]
    return OrderedDict(
        ssh_host_entries=len(hosts), ssh_remote_host_entries=len([h for h in hosts if not h['local']]),
        ssh_known_hosts=len(known),
        ssh_known_hosts_non_code_hosting=len([h for h in known if h not in code_hosting]),
        cloud_or_cluster_clis_installed=[c for c, v in clis.items() if v],
        gcloud=gcloud,
        docker_contexts=len(contexts), docker_remote_contexts=len(remote_ctx), colima_profiles=len(profiles),
        paid_cloud_note='a Google Cloud account and project are configured locally, but cloud compute is a paid service '
                        'and provisioning is not authorized; whether the project already holds an instance is unknown, '
                        'because no cloud API was called',
        remote_access_clients_installed=remote_access_clients(),
        scope='access configured on this machine only; institutional resources reachable through the installed '
              'remote-access clients (VPN, remote desktop) are not visible from local configuration',
        observation='worker-host measured (local configuration only; nothing was contacted; names not published)')


def ssh_hosts(cfg, seen=None):
    """Host entries of an OpenSSH config, following Include; local = its HostName is a loopback address."""
    seen = seen or set()
    if not cfg.exists() or cfg in seen:
        return []
    seen.add(cfg)
    out, cur = [], None
    for line in cfg.read_text().splitlines():
        m = re.match(r'\s*(\w+)\s+(.*)', line)
        if not m:
            continue
        key, val = m.group(1).lower(), m.group(2).strip()
        if key == 'include':
            for pat in val.split():
                pat = str(Path(pat).expanduser()) if pat.startswith('~') else (pat if pat.startswith('/') else
                                                                                 str(HOME / '.ssh' / pat))
                for f in sorted(Path('/').glob(pat.lstrip('/'))):
                    out += ssh_hosts(f, seen)
        elif key == 'host':
            cur = dict(local=False)
            out.append(cur)
        elif key == 'hostname' and cur is not None:
            cur['local'] = val in ('localhost', '127.0.0.1', '::1')
    return out


def remote_access_clients():
    apps = Path('/Applications')
    names = [p.name for p in apps.iterdir()] if apps.exists() else []
    kinds = []
    if any('Cisco' in n or 'VPN' in n or 'GlobalProtect' in n for n in names):
        kinds.append('VPN client')
    if any('Citrix' in n or 'Remote Desktop' in n or 'Parallels Client' in n for n in names):
        kinds.append('remote-desktop client')
    return kinds


def local_host_admission(host, f20):
    """the conservative admission calculation for this host at 32k/48 with f16 KV."""
    row = f20['envelopes']['32k_48']['memory']['f16']
    model_side = row['large_weights'] + row['small_weights'] + row['large_kv'] + row['small_kv']
    vm = row['vm_allowance']
    mem = host['hw_memsize_bytes']
    cache_max = 2 * PROMPT_CACHE_DEFAULT_MIB * (1 << 20)
    static = model_side + vm
    # physical RAM needed for >= 20 % free after load: (model side + VM + buffers + caches) <= 0.8 * RAM
    need_no_cache = static / 0.8
    need_full_cache = (static + cache_max) / 0.8
    free_now = host['memory_free_pct'] / 100 * mem if host['memory_free_pct'] is not None else None
    after = None if free_now is None else free_now - model_side
    return OrderedDict(
        envelope='32k_48 (f16 KV; the 64k/100 envelope is held by the lead)',
        hw_memsize_bytes=mem, model_side_bytes=model_side, vm_allowance_bytes=vm, static_total_bytes=static,
        static_limit_bytes=mem - 2 * GiB, static_fits=static <= mem - 2 * GiB,
        compute_buffers='not measurable without starting a server; positive, so they only tighten the gate',
        prompt_cache_max_bytes=cache_max,
        prompt_cache_note='pinned llama-server default cache_ram_mib 8192 per server (common/common.h); may stay '
                          'below its maximum in a short episode',
        post_load_free_pct_projection=None if after is None else round(100 * after / mem, 2),
        post_load_min_free_pct=20, post_load_passes=bool(after is not None and after / mem >= 0.20),
        ram_needed_gib_without_buffers_or_cache=round(need_no_cache / GiB, 2),
        ram_needed_gib_with_both_default_caches_full=round(need_full_cache / GiB, 2),
        reading='host RAM for this pair at 32k with f16 KV, one 16 GiB VM allowance and >= 20 %% free after load: at '
                'least %.1f GiB before buffers and caches, and at least %.1f GiB if both default prompt caches fill '
                '(both lower bounds: compute buffers and OS use are excluded); this host has %.1f GiB'
                % (need_no_cache / GiB, need_full_cache / GiB, mem / GiB))


def build():
    f20 = json.loads((ROOT / REQ020).read_text())
    host = INV.host_envelope()
    peers = INV.peers()
    access = access_inventory()
    adm = local_host_admission(host, f20)
    evaluator = OrderedDict(
        colima_profile_dtr_running=any(c['profile'] == 'dtr' and c['status'] == 'Running' for c in host['colima']),
        vm_disk_free_gib=host['vm_disk_free_gib'],
        pinned_harness='mini-swe-agent 04d809c, SWE-bench evaluator f7bbbb2 (REQ-019 harness_sources)',
        template_compatibility='source-inspected in REQ-020: Klear ChatML without tools; the jinja/autoparser path '
                               'and the trained action protocol (```bash fence, MINI_SWE_AGENT_FINAL_OUTPUT, edit tool) '
                               'differ from the frozen harness and remain unverified without a run')
    other_hosts = (access['ssh_remote_host_entries'] + access['ssh_known_hosts_non_code_hosting'] +
                   access['docker_remote_contexts'])          # a paid cloud account is not a no-cost host
    gates = OrderedDict(
        H1_other_accessible_no_cost_host=other_hosts > 0,
        H2_this_host_static_memory=adm['static_fits'],
        H3_this_host_post_load_reserve=adm['post_load_passes'])
    feasible = gates['H2_this_host_static_memory'] and gates['H3_this_host_post_load_reserve']
    verdict = OrderedDict(
        status='FEASIBLE (this host)' if feasible else 'BLOCKED',
        failing_gates=[k for k, v in gates.items() if v is False],
        statement='no already accessible, no-cost host can keep both models resident at 32k/48 with f16 KV under the '
                  'pinned evaluator: no other no-cost host is configured for access on this machine (a Google Cloud '
                  'account is paid and out of scope; its existing instances were not queried), and this 32 GiB host '
                  'fails the combined memory gate (static %.3f GiB > %.3f GiB before buffers and caches; projected '
                  '%.1f %% free after load < 20 %%). Per the lead, the local configuration search stops here.'
                  % (adm['static_total_bytes'] / GiB, adm['static_limit_bytes'] / GiB,
                     adm['post_load_free_pct_projection']) if not feasible else 'see gates')
    return OrderedDict(
        request=REQUEST, kind='one-time existing-host capacity check (read-only, local; nothing contacted)',
        lead_commit='9fae0e4', lead_decision='docs/theory_feedback_20260926_req020_decision.md',
        source_commit=INV.git('rev-parse', 'HEAD'), builder_sha256=INV.hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        req020_feasibility_sha256=INV.hashlib.sha256((ROOT / REQ020).read_bytes()).hexdigest(),
        host_measured_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        access=access, host=host, peers=peers, evaluator=evaluator, admission_32k_f16=adm, gates=gates, verdict=verdict,
        not_done=['no connection to another machine', 'no cloud API call', 'no download, server, VM change, inference, '
                  'reservation or task exposure'])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    ap.add_argument('--out', default=None)
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args(argv)
    out = Path(a.out) if a.out else ROOT / OUT_REL
    if (out / 'host_check.json').exists() and not a.force:
        print('refusing to overwrite recorded host readings; pass --force')
        return 2
    rec = build()
    out.mkdir(parents=True, exist_ok=True)
    (out / 'host_check.json').write_text(json.dumps(rec, indent=1, default=str) + '\n')
    print(json.dumps(rec['verdict'], indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
