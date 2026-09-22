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
import argparse, copy, hashlib, json, platform, re, signal, subprocess, sys, time
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
CONFIGURATION_BINDING = 'yaml-v1'
MINI_SWE_AGENT_PIN = '04d809ceab9df28f9adaed044884180159172930'
EPISODE_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()


def build_effective_config(cfg, *, alias, port, image_id, executable=DOCKER):
    """Preserve all three pinned YAML sections; apply only the declared pilot runtime overrides."""
    effective = {section: copy.deepcopy(cfg[section]) for section in ('agent', 'model', 'environment')}
    effective['agent'].update(step_limit=H, cost_limit=0.0, wall_time_limit_seconds=WALL_S)
    model = effective['model']
    model.update(model_name='openai/' + alias, cost_tracking='ignore_errors')
    model.setdefault('model_kwargs', {}).update(api_base='http://127.0.0.1:%d/v1' % port, api_key='none',
                                               temperature=0.0, max_tokens=MAX_TOKENS,
                                               timeout=REQUEST_TIMEOUT_S, num_retries=0)
    effective['environment'].update(image=image_id, cwd='/testbed', executable=executable, timeout=CMD_TIMEOUT,
                                     run_args=['--rm', '--platform', 'linux/amd64'])
    return effective


def effective_config_receipt(arguments, resolved):
    payload = dict(configuration_binding=CONFIGURATION_BINDING, mini_swe_agent=MINI_SWE_AGENT_PIN,
                   default_yaml_sha256=DEFAULT_YAML_SHA, episode_source_sha256=EPISODE_SOURCE_SHA256,
                   constructor_arguments=arguments, resolved=resolved)
    digest = sha(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False))
    return dict(payload, effective_config_sha256=digest)


class EpisodeDeadline(TimeoutError):
    pass


def request_timeout(deadline, now=None):
    left = deadline - (time.time() if now is None else now)
    if left <= 0:
        raise EpisodeDeadline('episode inference deadline reached')
    return min(REQUEST_TIMEOUT_S, left)


def append_attempt(path, record):
    """A start is durable before dispatch, and its result is a separate append; interrupted requests stay visible."""
    with Path(path).open('a') as fh:
        fh.write(json.dumps(record) + '\n')
        fh.flush()
        os.fsync(fh.fileno())


def cleanup_owned_container(container_id, deadline, run=None):
    """Synchronously stop only the recorded episode container; an observed stopped/absent state confirms release."""
    rec = dict(container_id=container_id, confirmed=False, state='unknown', commands=[])
    if not isinstance(container_id, str) or not re.fullmatch(r'[0-9a-f]{64}', container_id):
        return dict(rec, reason='no verified full episode-owned container ID')
    run = subprocess.run if run is None else run
    def call(args, limit):
        left = deadline - time.time()
        if left <= 0:
            rec['reason'] = 'cleanup deadline exhausted'
            return None
        try:
            result = run([DOCKER, *args], capture_output=True, text=True, timeout=min(left, limit))
            rec['commands'].append(dict(args=args, returncode=result.returncode, stdout=result.stdout[-300:], stderr=result.stderr[-300:]))
            return result
        except Exception as e:
            rec['commands'].append(dict(args=args, error=type(e).__name__, detail=str(e)[:300]))
            return None
    def inspect():
        result = call(['container', 'inspect', '--format', '{{.State.Running}}', container_id], 10)
        if result is None:
            return False
        if result.returncode == 0 and result.stdout.strip() == 'false':
            rec.update(confirmed=True, state='stopped')
        elif result.returncode != 0 and container_id in result.stderr and any(
                s in result.stderr.lower() for s in ('no such container', 'no such object')):
            rec.update(confirmed=True, state='absent')
        elif result.returncode == 0 and result.stdout.strip() == 'true':
            rec['state'] = 'running'
        return rec['confirmed']
    call(['stop', '--time', '10', container_id], 20)
    if not inspect():
        call(['rm', '-f', container_id], 20)
        inspect()
    if not rec['confirmed']:
        rec.setdefault('reason', 'container termination could not be confirmed before cleanup deadline')
    return rec


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
    ap.add_argument('--episode-deadline', required=True, type=float)
    ap.add_argument('--block-deadline', required=True, type=float)
    args = ap.parse_args()
    deadline = min(args.episode_deadline, args.block_deadline)
    def alarm(_signum, _frame):
        raise EpisodeDeadline('absolute inference deadline reached; cleanup only')
    signal.signal(signal.SIGALRM, alarm)
    request_timeout(deadline)
    signal.setitimer(signal.ITIMER_REAL, max(1e-6, deadline - time.time()))
    import pandas as pd
    import requests
    import yaml
    from minisweagent.agents.default import DefaultAgent
    from minisweagent.environments.docker import DockerEnvironment
    from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel

    run_dir = Path(args.run_dir)
    attempts_path = run_dir / 'attempts.jsonl'
    WC.write_once(attempts_path, '')
    cfg_path = MSWEA / 'src/minisweagent/config/default.yaml'
    if sha(cfg_path.read_bytes()) != DEFAULT_YAML_SHA:
        raise SystemExit('default.yaml differs from the lead pin')
    cfg = yaml.safe_load(cfg_path.read_text())
    row = next(r for r in pd.read_parquet(DATA).to_dict('records') if r['instance_id'] == args.instance)
    image_ref = 'sweb.eval.x86_64.%s:latest' % args.instance
    image_id = subprocess.run([DOCKER, 'image', 'inspect', '--format', '{{.Id}}', image_ref], capture_output=True, text=True, check=True).stdout.strip()
    if image_id != args.expected_image:
        raise SystemExit('image %s is %s, frozen frame pins %s' % (image_ref, image_id, args.expected_image))
    effective_cfg = build_effective_config(cfg, alias=args.alias, port=args.port, image_id=image_id)
    props = requests.get('http://127.0.0.1:%d/props' % args.port, timeout=10).json()
    attempts = []

    class AccountedModel(LitellmTextbasedModel):
        """Logs every PHYSICAL attempt; the logical call index is the agent's model.query count."""
        abort_exceptions = LitellmTextbasedModel.abort_exceptions + [EpisodeDeadline]
        def __init__(self, **kw):
            super().__init__(**kw)
            self.logical = 0
            self.attempt = 0

        def query(self, messages, **kw):
            request_timeout(deadline)
            self.logical += 1
            self.attempt = 0
            if self.logical == 9:
                WC.write_once(run_dir / 'call9_history.json', json.dumps(dict(call=9, messages=messages, captured_at=time.time())) + '\n')
            return super().query(messages, **kw)

        def _query(self, messages, **kw):
            timeout = request_timeout(deadline)
            self.attempt += 1
            rec = dict(call=self.logical, attempt=self.attempt, t_start=time.time(), request_timeout_s=timeout)
            append_attempt(attempts_path, dict(rec, event='start'))
            attempts.append(rec)
            try:
                r = super()._query(messages, **dict(kw, timeout=request_timeout(deadline)))
            except BaseException as e:  # noqa: BLE001  logged, then re-raised to the unmodified retry/agent logic
                rec.update(t_end=time.time(), ok=False, error=type(e).__name__, detail=str(e)[:300])
                append_attempt(attempts_path, dict(rec, event='result'))
                raise
            u = getattr(r, 'usage', None)
            rec.update(t_end=time.time(), ok=True, prompt_tokens=getattr(u, 'prompt_tokens', None),
                       completion_tokens=getattr(u, 'completion_tokens', None), finish_reason=r.choices[0].finish_reason)
            append_attempt(attempts_path, dict(rec, event='result'))
            return r

    model = AccountedModel(**effective_cfg['model'])

    class ContainerPlatformDockerEnvironment(DockerEnvironment):
        """cp2 binding (accepted): the CONTAINER's uname in the prompt templates, not the macOS host's."""
        def _start_container(self):
            super()._start_container()
            WC.write_once(run_dir / 'container_ownership.json', json.dumps(dict(container_id=self.container_id, run_id=args.run_id)) + '\n')

        def cleanup(self):
            if not hasattr(self, '_cleanup_receipt'):
                self._cleanup_receipt = cleanup_owned_container(getattr(self, 'container_id', None), deadline + 120)
                WC.write_once(run_dir / 'container_cleanup.json', json.dumps(self._cleanup_receipt) + '\n')
            return self._cleanup_receipt       # upstream __del__ is now idempotent and never launches an async shell

        def container_platform(self):
            if not hasattr(self, '_cplat'):
                self._cplat = {k: self.execute({'command': 'uname -%s' % f}).get('output', '').strip() for k, f in
                               (('system', 's'), ('release', 'r'), ('version', 'v'), ('machine', 'm'))}
            return self._cplat

        def get_template_vars(self, **kwargs):
            return {**super().get_template_vars(**kwargs), **self.container_platform()}

    env = ContainerPlatformDockerEnvironment(**effective_cfg['environment'])
    ex = lambda cmd: (lambda o: (o.get('returncode'), o.get('output', '')))(env.execute({'command': cmd}))
    base_tree, capture_error = None, None
    try:
        base_tree = WC.tree(ex)
    except WC.CaptureError as e:
        capture_error = 'base: %s' % e
    agent_cfg = effective_cfg['agent']
    agent = DefaultAgent(model, env, **agent_cfg)
    config_record = effective_config_receipt(effective_cfg, dict(agent=agent.config.model_dump(mode='json'),
                      model=model.config.model_dump(mode='json'), environment=env.config.model_dump(mode='json')))
    WC.write_once(run_dir / 'effective_config.json', json.dumps(config_record, indent=1) + '\n')
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
    signal.setitimer(signal.ITIMER_REAL, 0)          # no inference remains; runner retains the separate cleanup bound
    wall = time.time() - t0
    cleanup_error = None
    container_cleanup = dict(confirmed=False, state='unknown')
    try:
        container_cleanup = env.cleanup()
        if not container_cleanup['confirmed']:
            cleanup_error = container_cleanup.get('reason', 'container cleanup unconfirmed')
    except Exception as e:  # noqa: BLE001
        cleanup_error = '%s: %s' % (type(e).__name__, str(e)[:500])
    agent.save(run_dir / 'trajectory.json', {'info': {'exit_status': exit_status, 'error': err}})
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
               pins=dict(mini_swe_agent=MINI_SWE_AGENT_PIN, default_yaml_sha256=DEFAULT_YAML_SHA,
                         image_ref=image_ref, image_id=image_id),
               configuration_binding=CONFIGURATION_BINDING, effective_config_file='effective_config.json',
               effective_config_status='recorded', effective_config_sha256=config_record['effective_config_sha256'],
               episode_source_sha256=config_record['episode_source_sha256'],
               settings=dict(step_limit=H, cost_limit=0.0, wall_time_limit_seconds=WALL_S, temperature=0.0, max_tokens=MAX_TOKENS,
                             command_timeout_s=CMD_TIMEOUT, physical_attempts_per_call_max=ATTEMPTS_PER_CALL, request_timeout_s=REQUEST_TIMEOUT_S,
                             max_consecutive_format_errors=agent_cfg.get('max_consecutive_format_errors')),
               workspace_binding='wc2', template_platform_binding='cp2', container_platform=env.container_platform(),
               base_tree=base_tree, final_tree=final_tree, capture_error=capture_error, cleanup_error=cleanup_error,
               container_cleanup=container_cleanup,
               host=dict(arch=platform.machine(), os=platform.platform()),
               exit_status=exit_status, error=err, n_model_calls=getattr(agent, 'n_calls', None), wall_seconds=wall,
               physical_requests=len(attempts), max_attempts_on_one_call=max(per_call.values()) if per_call else 0,
               failed_attempts=sum(a.get('ok') is False for a in attempts),
               prompt_tokens=(sum(a['prompt_tokens'] for a in attempts) if all(a.get('prompt_tokens') is not None for a in attempts) else None),
               completion_tokens=(sum(a['completion_tokens'] for a in attempts) if all(a.get('completion_tokens') is not None for a in attempts) else None),
               known_prompt_tokens=sum(a.get('prompt_tokens') or 0 for a in attempts),
               known_completion_tokens=sum(a.get('completion_tokens') or 0 for a in attempts),
               incomplete_attempt_results=sum('ok' not in a for a in attempts),
               submission_sha256=sha(submission), submission_bytes=len(submission), submission_empty=not submission.strip())
    WC.write_once(run_dir / 'episode.json', json.dumps(rec, indent=1) + '\n')
    print(json.dumps({k: rec[k] for k in ('instance_id', 'backend', 'exit_status', 'n_model_calls', 'physical_requests', 'wall_seconds', 'submission_bytes')}))


if __name__ == '__main__':
    main()
