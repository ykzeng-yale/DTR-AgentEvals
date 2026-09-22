"""DTR-REQ-002 fixed-backend DEVELOPMENT pilot: ONE episode (spec configs/v2_fixed_backend_development_pilot_20260922.json,
frozen frame results/v2_agent/pilot_frame_20260922.json accepted by lead 23b0ddc). Launched by pilot_runner.py.

Same pinned stack and bindings as the accepted smoke episode (agent_smoke_episode.py): mini-swe-agent 04d809c unmodified
DefaultAgent + LitellmTextbasedModel + DockerEnvironment with the cp2 container-platform template binding, wc2 workspace
capture on an explicit Submitted exit only (no salvage), H=24 logical calls, T=0, max_tokens 1,536, command timeout 60 s,
episode wall 1,800 s (mini-swe-agent's own check between steps), digest-pinned instance image.
Physical-attempt accounting (spec): at most 2 physical attempts per logical call (tenacity stop via
MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT=2; litellm num_retries=0), so at most 48 per episode; EVERY attempt is logged with
wall times, prompt/completion tokens, finish reason or error type. The model is never redrawn on retry.
"""
from __future__ import annotations
import os
os.environ['MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT'] = '2'
os.environ['MSWEA_COST_TRACKING'] = 'ignore_errors'
import argparse, hashlib, json, platform, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workspace_capture as WC  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MSWEA = ROOT / 'work/upstream/mini-swe-agent-04d809ceab9df28f9adaed044884180159172930'
DEFAULT_YAML_SHA = '112aa58328f478a41cc2630702a4b89ef459e912870e05065157ed221f56701f'
DATA = ROOT / 'work/benchmark_inputs/swebench_verified_c104f840/test-00000-of-00001.parquet'
DOCKER = str(Path.home() / '.local/dtr-runtime/bin/docker')
H, WALL_S, MAX_TOKENS, CMD_TIMEOUT, ATTEMPTS_PER_CALL = 24, 1800, 1536, 60, 2
REQUEST_TIMEOUT_S = 900


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--instance', required=True)
    ap.add_argument('--backend', choices=('small', 'large'), required=True)
    ap.add_argument('--port', type=int, required=True)
    ap.add_argument('--alias', required=True)
    ap.add_argument('--run-dir', required=True)
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--expected-image', required=True)
    ap.add_argument('--served', required=True, help='JSON: served model file name/sha256/load record from the runner')
    args = ap.parse_args()
    import pandas as pd
    import requests
    import yaml
    from minisweagent.agents.default import DefaultAgent
    from minisweagent.environments.docker import DockerEnvironment
    from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel

    run_dir = Path(args.run_dir)
    cfg_path = MSWEA / 'src/minisweagent/config/default.yaml'
    if sha(cfg_path.read_bytes()) != DEFAULT_YAML_SHA:
        raise SystemExit('default.yaml differs from the lead pin')
    cfg = yaml.safe_load(cfg_path.read_text())
    row = next(r for r in pd.read_parquet(DATA).to_dict('records') if r['instance_id'] == args.instance)
    image_ref = 'sweb.eval.x86_64.%s:latest' % args.instance
    image_id = subprocess.run([DOCKER, 'image', 'inspect', '--format', '{{.Id}}', image_ref], capture_output=True, text=True, check=True).stdout.strip()
    if image_id != args.expected_image:
        raise SystemExit('image %s is %s, frozen frame pins %s' % (image_ref, image_id, args.expected_image))
    props = requests.get('http://127.0.0.1:%d/props' % args.port, timeout=10).json()
    attempts = []

    class AccountedModel(LitellmTextbasedModel):
        """Logs every PHYSICAL attempt; the logical call index is the agent's model.query count."""
        def __init__(self, **kw):
            super().__init__(**kw)
            self.logical = 0
            self.attempt = 0

        def query(self, messages, **kw):
            self.logical += 1
            self.attempt = 0
            return super().query(messages, **kw)

        def _query(self, messages, **kw):
            self.attempt += 1
            rec = dict(call=self.logical, attempt=self.attempt, t_start=time.time())
            try:
                r = super()._query(messages, **kw)
            except BaseException as e:  # noqa: BLE001  logged, then re-raised to the unmodified retry/agent logic
                rec.update(t_end=time.time(), ok=False, error=type(e).__name__, detail=str(e)[:300])
                attempts.append(rec)
                raise
            u = getattr(r, 'usage', None)
            rec.update(t_end=time.time(), ok=True, prompt_tokens=getattr(u, 'prompt_tokens', None),
                       completion_tokens=getattr(u, 'completion_tokens', None), finish_reason=r.choices[0].finish_reason)
            attempts.append(rec)
            return r

    model = AccountedModel(model_name='openai/' + args.alias, cost_tracking='ignore_errors',
                           model_kwargs=dict(api_base='http://127.0.0.1:%d/v1' % args.port, api_key='none', temperature=0.0,
                                             max_tokens=MAX_TOKENS, timeout=REQUEST_TIMEOUT_S, num_retries=0))

    class ContainerPlatformDockerEnvironment(DockerEnvironment):
        """cp2 binding (accepted): the CONTAINER's uname in the prompt templates, not the macOS host's."""
        def container_platform(self):
            if not hasattr(self, '_cplat'):
                self._cplat = {k: self.execute({'command': 'uname -%s' % f}).get('output', '').strip() for k, f in
                               (('system', 's'), ('release', 'r'), ('version', 'v'), ('machine', 'm'))}
            return self._cplat

        def get_template_vars(self, **kwargs):
            return {**super().get_template_vars(**kwargs), **self.container_platform()}

    env = ContainerPlatformDockerEnvironment(image=image_id, cwd='/testbed', executable=DOCKER, timeout=CMD_TIMEOUT,
                                             run_args=['--rm', '--platform', 'linux/amd64'], env=dict(PAGER='cat', MANPAGER='cat'))
    ex = lambda cmd: (lambda o: (o.get('returncode'), o.get('output', '')))(env.execute({'command': cmd}))
    base_tree, capture_error = None, None
    try:
        base_tree = WC.tree(ex)
    except WC.CaptureError as e:
        capture_error = 'base: %s' % e
    agent_cfg = dict(cfg['agent'], step_limit=H, cost_limit=0.0, wall_time_limit_seconds=WALL_S)
    agent = DefaultAgent(model, env, **agent_cfg)
    t0 = time.time()
    exit_status, submission, err, final_tree = None, '', None, None
    try:
        info = agent.run(row['problem_statement'])
        exit_status = info.get('exit_status')
        if exit_status == 'Submitted':
            if base_tree is None:
                exit_status = 'SubmissionCaptureFailed'
            else:
                try:
                    cap = WC.patch(ex, base_tree)
                    submission, final_tree = cap['patch'], cap['final_tree']
                except WC.CaptureError as e:
                    exit_status, capture_error = 'SubmissionCaptureFailed', 'final: %s' % e
    except Exception as e:  # noqa: BLE001  retained, never dropped
        exit_status, err = type(e).__name__, str(e)[:500]
    wall = time.time() - t0
    try:
        env.cleanup()
    except Exception:  # noqa: BLE001
        pass
    agent.save(run_dir / 'trajectory.json', {'info': {'exit_status': exit_status, 'error': err}})
    WC.write_once(run_dir / 'attempts.jsonl', ''.join(json.dumps(a) + '\n' for a in attempts))
    WC.write_once(run_dir / 'submission.diff', submission)
    per_call = {}
    for a in attempts:
        per_call[a['call']] = per_call.get(a['call'], 0) + 1
    rec = dict(kind='fixed-backend DEVELOPMENT pilot episode (no routing); not a policy estimate, not CONFIRM',
               request='DTR-REQ-002', frame='results/v2_agent/pilot_frame_20260922.json (lead 23b0ddc)',
               instance_id=args.instance, backend=args.backend, backend_alias=args.alias, run_id=args.run_id,
               served=json.loads(args.served),
               server=dict(port=args.port, total_slots=props.get('total_slots'), n_ctx_per_slot=props.get('default_generation_settings', {}).get('n_ctx'),
                           model_file=Path(props.get('model_path') or '').name),
               pins=dict(mini_swe_agent='04d809ceab9df28f9adaed044884180159172930', default_yaml_sha256=DEFAULT_YAML_SHA,
                         image_ref=image_ref, image_id=image_id),
               settings=dict(step_limit=H, cost_limit=0.0, wall_time_limit_seconds=WALL_S, temperature=0.0, max_tokens=MAX_TOKENS,
                             command_timeout_s=CMD_TIMEOUT, physical_attempts_per_call_max=ATTEMPTS_PER_CALL, request_timeout_s=REQUEST_TIMEOUT_S,
                             max_consecutive_format_errors=agent_cfg.get('max_consecutive_format_errors')),
               workspace_binding='wc2', template_platform_binding='cp2', container_platform=env.container_platform(),
               base_tree=base_tree, final_tree=final_tree, capture_error=capture_error,
               host=dict(arch=platform.machine(), os=platform.platform()),
               exit_status=exit_status, error=err, n_model_calls=getattr(agent, 'n_calls', None), wall_seconds=wall,
               physical_requests=len(attempts), max_attempts_on_one_call=max(per_call.values()) if per_call else 0,
               failed_attempts=sum(not a['ok'] for a in attempts),
               prompt_tokens=sum(a.get('prompt_tokens') or 0 for a in attempts),
               completion_tokens=sum(a.get('completion_tokens') or 0 for a in attempts),
               submission_sha256=sha(submission), submission_bytes=len(submission), submission_empty=not submission.strip())
    WC.write_once(run_dir / 'episode.json', json.dumps(rec, indent=1) + '\n')
    print(json.dumps({k: rec[k] for k in ('instance_id', 'backend', 'exit_status', 'n_model_calls', 'physical_requests', 'wall_seconds', 'submission_bytes')}))


if __name__ == '__main__':
    main()
