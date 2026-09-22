"""DTR-REQ-002: first REAL-AGENT pipeline smoke episode (authorized by the author 2026-09-22: "do all directly for all you
need", after my offer to run agents). NOT a routing/policy result, NOT CONFIRM, not a representative sample.

Pinned stack: mini-swe-agent 04d809c (v2.4.6), unmodified DefaultAgent + LitellmTextbasedModel (single-action regex) +
DockerEnvironment; the lead's candidate prompt basis config/default.yaml (SHA-256 112aa583... checked); step limit H=24
(lead 8ecdfde), cost tracking ignore_errors / cost_limit 0; ONE fixed backend per episode (no routing) served by the
project's llama-server (Qwen2.5 GGUF q4_k_m, per-slot context as served, recorded). The container is the locally built,
digest-pinned SWE-bench instance image (namespace none, amd64 via Rosetta in the Colima VM).
Declared workspace binding (candidate, for lead review): default.yaml's submit command carries no patch, so on an
explicit Submitted exit the driver captures the tracked-file diff of /testbed (`git -c core.fileMode=false diff`)
from the same container as the submission; any other exit (limits, format errors, context window, exception) has an
EMPTY submission (operational zero). The submission is then graded by the pinned f7bbbb2 harness (stock path) and the
M03 strict rule, in a separate step.
  work/venvs/minisweagent_04d809c/bin/python experiments/v2_agent/agent_smoke_episode.py --backend large|small
"""
from __future__ import annotations
import argparse, hashlib, json, os, platform, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MSWEA = ROOT / 'work/upstream/mini-swe-agent-04d809ceab9df28f9adaed044884180159172930'
DEFAULT_YAML_SHA = '112aa58328f478a41cc2630702a4b89ef459e912870e05065157ed221f56701f'
DATA = ROOT / 'work/benchmark_inputs/swebench_verified_c104f840/test-00000-of-00001.parquet'
BACKENDS = dict(large=dict(alias='qwen2.5-7b-instruct', port=8191), small=dict(alias='qwen2.5-3b-instruct', port=8193))
H = 24
WALL_S = 1800   # smoke-episode wall bound via mini-swe-agent's own wall_time_limit_seconds (not a frozen study limit)
OUT = ROOT / 'results/v2_agent/smoke_episode_20260922'
DOCKER = str(Path.home() / '.local/dtr-runtime/bin/docker')


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--backend', choices=sorted(BACKENDS), required=True)
    ap.add_argument('--instance', default='pallets__flask-5014')
    args = ap.parse_args()
    import pandas as pd
    import requests
    import yaml
    from minisweagent.agents.default import DefaultAgent
    from minisweagent.environments.docker import DockerEnvironment
    from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel

    cfg_path = MSWEA / 'src/minisweagent/config/default.yaml'
    if sha(cfg_path.read_bytes()) != DEFAULT_YAML_SHA:
        raise SystemExit('default.yaml differs from the lead pin')
    cfg = yaml.safe_load(cfg_path.read_text())
    row = next(r for r in pd.read_parquet(DATA).to_dict('records') if r['instance_id'] == args.instance)
    image_ref = 'sweb.eval.x86_64.%s:latest' % args.instance
    import subprocess
    image_id = subprocess.run([DOCKER, 'image', 'inspect', '--format', '{{.Id}}', image_ref], capture_output=True, text=True, check=True).stdout.strip()
    be = BACKENDS[args.backend]
    props = requests.get('http://127.0.0.1:%d/props' % be['port'], timeout=10).json()
    model = LitellmTextbasedModel(model_name='openai/' + be['alias'], cost_tracking='ignore_errors',
                                  model_kwargs=dict(api_base='http://127.0.0.1:%d/v1' % be['port'], api_key='none',
                                                    temperature=0.0, max_tokens=1536))
    class ContainerPlatformDockerEnvironment(DockerEnvironment):
        """Binding v2: report the CONTAINER's uname to the prompt templates. The pinned DockerEnvironment uses the host's
        platform.uname() (docker.py L61-L62), which on a macOS host tells the model it is on Darwin (and default.yaml then
        recommends BSD `sed -i ''`) although every command runs in a Linux container. No upstream code is modified."""
        def container_platform(self):
            if not hasattr(self, '_cplat'):
                vals = {k: self.execute({'command': 'uname -%s' % f}).get('output', '').strip() for k, f in
                        (('system', 's'), ('release', 'r'), ('version', 'v'), ('machine', 'm'))}
                self._cplat = vals
            return self._cplat

        def get_template_vars(self, **kwargs):
            return {**super().get_template_vars(**kwargs), **self.container_platform()}

    env = ContainerPlatformDockerEnvironment(image=image_id, cwd='/testbed', executable=DOCKER, timeout=60,
                                             run_args=['--rm', '--platform', 'linux/amd64'], env=dict(PAGER='cat', MANPAGER='cat'))
    agent_cfg = dict(cfg['agent'], step_limit=H, cost_limit=0.0, wall_time_limit_seconds=WALL_S)
    agent = DefaultAgent(model, env, **agent_cfg)
    t0 = time.time()
    exit_status, submission, err = None, '', None
    try:
        info = agent.run(row['problem_statement'])
        exit_status = info.get('exit_status')
        if exit_status == 'Submitted':
            out = env.execute({'command': 'git -c core.fileMode=false diff'})
            submission = out.get('output', '')
    except Exception as e:  # noqa: BLE001  retained, never dropped
        exit_status, err = type(e).__name__, str(e)[:500]
    wall = time.time() - t0
    try:
        env.cleanup()
    except Exception:  # noqa: BLE001
        pass
    run_dir = OUT / ('%s__%s' % (args.instance, args.backend))
    run_dir.mkdir(parents=True, exist_ok=True)
    agent.save(run_dir / 'trajectory.json', {'info': {'exit_status': exit_status, 'error': err}})
    (run_dir / 'submission.diff').write_text(submission)
    n_calls = getattr(agent, 'n_calls', None)
    rec = dict(kind='REAL-AGENT pipeline smoke episode (fixed backend, no routing); not a policy estimate, not CONFIRM',
               authorization='author 2026-09-22', instance_id=args.instance, backend=args.backend, backend_alias=be['alias'],
               server=dict(port=be['port'], total_slots=props.get('total_slots'), n_ctx_per_slot=props.get('default_generation_settings', {}).get('n_ctx'),
                           model_file=Path(props.get('model_path') or '').name),   # file name only (no local paths)
               pins=dict(mini_swe_agent='04d809ceab9df28f9adaed044884180159172930', default_yaml_sha256=DEFAULT_YAML_SHA,
                         image_ref=image_ref, image_id=image_id),
               settings=dict(step_limit=H, cost_limit=0.0, wall_time_limit_seconds=WALL_S, temperature=0.0, max_tokens=1536, command_timeout_s=60,
                             max_consecutive_format_errors=agent_cfg.get('max_consecutive_format_errors', 3)),
               workspace_binding='on Submitted: tracked-file git diff of /testbed from the same container (candidate, lead review)',
               template_platform_binding='v2: container uname (not host) for {{system}}/{{release}}/{{version}}/{{machine}}',
               container_platform=env.container_platform(),
               host=dict(arch=platform.machine(), os=platform.platform()),
               exit_status=exit_status, error=err, n_model_calls=n_calls, wall_seconds=wall,
               submission_sha256=sha(submission), submission_bytes=len(submission), submission_empty=not submission.strip())
    (run_dir / 'episode.json').write_text(json.dumps(rec, indent=1) + '\n')
    print(json.dumps({k: rec[k] for k in ('backend', 'exit_status', 'n_model_calls', 'wall_seconds', 'submission_bytes', 'error')}, indent=1))


if __name__ == '__main__':
    main()
