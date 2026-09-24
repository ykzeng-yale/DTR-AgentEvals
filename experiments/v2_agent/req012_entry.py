"""DTR-REQ-012 (lead 40b4db2, docs/theory_feedback_20260924_req011_decision.md): ONE 'baseline' episode under the
versioned DEVELOPMENT configuration yaml-v1-repair1, launched by req012_pair.py in the pinned mini-swe-agent venv.

    work/venvs/minisweagent_04d809c/bin/python experiments/v2_agent/req012_entry.py <control>/entry.json

yaml-v1-repair1 is the frozen yaml-v1 configuration with three declared changes. They are installed in THIS process
only, after admission and before the validated cue_episode.run_episode (unchanged) builds anything:
  (a) pilot_episode.build_effective_config is wrapped. The config it returns gets PROMPT_ADDITION as item 4 at the end
      of the instance template's "## Important Rules" list, and the agent container gets RUN_ARGS (--network none);
  (b) minisweagent.agents.default.DefaultAgent becomes RepeatedFailureGuardAgent. Before each model query, and before
      the frozen limit checks, its query() raises RepeatedFailureStall (exit status 'RepeatedFailureStall', submission
      '') if the last two recorded turns have the same normalized command, the same NONZERO return code and the same
      output fingerprint (whitespace-normalized output with object addresses and durations masked; STALL_RULE). It
      makes no model call, shows nothing to the model and fabricates no submission.
Everything else is the REQ-011 path: settings, receipts, the Submitted-only endpoint, all-exit capture and cleanup.
Before the first query the agent records the episode container's docker NetworkMode once. After the episode, the
recorded effective_config.json is checked against the expected repair1 config. The overrides, the guard's turn record
and that check are written to <control>/repair_record.json.

The entry refuses (entry_refused.json, exit 3, nothing else written) on the same grounds as req011_entry, using this
manifest and the budget rule min(48, 48 - counted_before). It also refuses when the pinned default.yaml does not yield
the manifest's prompt bytes.
"""
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import cue_episode as CE  # noqa: E402  FIRST: its pilot_episode import sets MSWEA_* before minisweagent loads

import argparse  # noqa: E402
import copy  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import signal  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
import urllib.request  # noqa: E402

A, WC, PE = CE.A, CE.WC, CE.PE
ROOT = HERE.parents[1]
REL = 'experiments/v2_agent/'
SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
REQUEST = 'DTR-REQ-012'
MANIFEST_REL = 'configs/v2_req012_repair_probe_20260924.json'
CONFIGURATION = 'yaml-v1-repair1'
EXIT_REFUSED = 3
PER_EPISODE_PHYSICAL, PROBE_PHYSICAL = 48, 48
RULES_HEADING, RULES_END = '## Important Rules\n', '<system_information>'
RULES_ANCHOR = ('   However, you can prefix any action with `MY_ENV_VAR=MY_VALUE cd /path/to/working/dir && ...` or '
                'write/load environment variables from files\n')           # the last line of rule 3 (default.yaml)
PROMPT_ADDITION = ('4. The repository to fix is checked out at /testbed, which is the working directory for every '
                   'action. It is installed in editable (development) mode in the active Python environment, so '
                   'importing the package runs the code in /testbed and your edits there take effect immediately. '
                   'The environment has no network access.')
INSERTED = PROMPT_ADDITION + '\n'
FROZEN_RUN_ARGS = ['--rm', '--platform', 'linux/amd64']
RUN_ARGS = FROZEN_RUN_ARGS + ['--network', 'none']
STALL = 'RepeatedFailureStall'
AGENT_CLASS = 'req012_entry.RepeatedFailureGuardAgent'
STALL_RULE = ('A turn is recorded only when the agent executed exactly one action: (normalized command, return code, '
              'output fingerprint); normalized command = the command stripped with whitespace runs collapsed to one '
              'space; output fingerprint = sha256 of the output with whitespace runs collapsed to one space and '
              'stripped, then two volatile token kinds masked (Python re): hexadecimal literals 0x[0-9a-fA-F]+ '
              '(per-process object addresses, e.g. in pip retry warnings) -> 0x_ and decimal-second durations '
              '\\b[0-9]+\\.[0-9]+s\\b (e.g. pytest \'in 3.21s\') -> _s. A FormatError turn or a turn with a '
              'number of actions other than one is recorded as a chain reset. Before each model query, before the '
              'frozen limit checks and before n_calls is incremented: if the last two recorded turns are equal and '
              'their return code is nonzero, raise RepeatedFailureStall carrying the exit message; the frozen run() '
              'records it as the exit with an empty submission. No model call, nothing shown to the model.')
OVERRIDES = ['pilot_episode.build_effective_config -> repair_config(<the frozen function\'s result>)',
             'minisweagent.agents.default.DefaultAgent -> ' + AGENT_CLASS]
GUARDS = []                                        # every guarded agent constructed in this process
_WS = re.compile(r'\s+')
VOLATILE = ((re.compile(r'0x[0-9a-fA-F]+'), '0x_'), (re.compile(r'\b[0-9]+\.[0-9]+s\b'), '_s'))


def sha(text):
    return hashlib.sha256(text.encode('utf-8', 'surrogateescape')).hexdigest()


# ---------------------------------------------------------------- repair1 configuration (pure)
def repair_template(template):
    """The frozen instance template with PROMPT_ADDITION appended as the last item of its Important Rules list."""
    head, end = template.find(RULES_HEADING), template.find(RULES_END)
    at = template.find(RULES_ANCHOR)
    if template.count(RULES_ANCHOR) != 1 or not 0 <= head < at < end:
        raise ValueError('the Important Rules anchor must occur once, inside the Important Rules list')
    return template.replace(RULES_ANCHOR, RULES_ANCHOR + INSERTED, 1)


def repair_config(effective):
    """pilot_episode.build_effective_config's result -> the yaml-v1-repair1 config (only these two fields change)."""
    out = copy.deepcopy(effective)
    if out['environment'].get('run_args') != FROZEN_RUN_ARGS:
        raise ValueError('the base environment run_args are not the frozen yaml-v1 ones')
    out['agent']['instance_template'] = repair_template(out['agent']['instance_template'])
    out['environment']['run_args'] = list(RUN_ARGS)
    return out


def prompt_bytes(frozen_template):
    after = repair_template(frozen_template)
    return dict(default_yaml_sha256=PE.DEFAULT_YAML_SHA, instance_template_frozen_sha256=sha(frozen_template),
                instance_template_frozen_bytes=len(frozen_template.encode()),
                instance_template_repair1_sha256=sha(after), instance_template_repair1_bytes=len(after.encode()),
                inserted_text=INSERTED, inserted_sha256=sha(INSERTED), inserted_bytes=len(INSERTED.encode()))


def stall_message():
    return {'role': 'exit', 'content': STALL, 'extra': {'exit_status': STALL, 'submission': ''}}


def repair1_record():
    """The code-derived repair1 section of the manifest."""
    return dict(configuration=CONFIGURATION, base_configuration='yaml-v1', section=RULES_HEADING.strip(),
                prompt_addition=PROMPT_ADDITION, inserted_after=RULES_ANCHOR, run_args_frozen=FROZEN_RUN_ARGS,
                run_args=RUN_ARGS, agent_class=AGENT_CLASS,
                agent_base='minisweagent.agents.default.DefaultAgent (mini-swe-agent 04d809c, unmodified)',
                stall_exit_message=stall_message(), stall_rule=STALL_RULE, runtime_overrides=OVERRIDES)


def frozen_template():
    import yaml
    raw = (PE.MSWEA / 'src/minisweagent/config/default.yaml').read_bytes()
    if PE.sha(raw) != PE.DEFAULT_YAML_SHA:
        raise ValueError('default.yaml differs from the pin')
    return yaml.safe_load(raw.decode())['agent']['instance_template']


# ---------------------------------------------------------------- the stall guard
def normalize(text):
    return _WS.sub(' ', text).strip()


def fingerprint(output):
    """sha256 of the normalized output with the declared volatile tokens masked (STALL_RULE)."""
    text = normalize(output)
    for pattern, mask in VOLATILE:
        text = pattern.sub(mask, text)
    return sha(text)


def turn_of(message, observations):
    """(normalized command, return code, output fingerprint) of a turn with exactly one executed action, else None."""
    actions = (message.get('extra') or {}).get('actions') or []
    if len(actions) != 1 or len(observations) != 1 or not isinstance(actions[0], dict) \
            or not isinstance(actions[0].get('command'), str):
        return None
    extra = observations[0].get('extra') or {}
    rc, output = extra.get('returncode'), extra.get('raw_output')
    if type(rc) is not int or not isinstance(output, str):
        return None
    return normalize(actions[0]['command']), rc, fingerprint(output)


def stalled(turns):
    return len(turns) >= 2 and turns[-1] is not None and turns[-1] == turns[-2] and turns[-1][1] != 0


def make_guarded_agent(base, interrupt, format_error, on_start=None):
    """The guarded subclass of `base` (DefaultAgent) and its InterruptAgentFlow subclass (`interrupt`)."""

    class RepeatedFailureStall(interrupt):
        """Two consecutive identical failing turns: an observational operational stop (never a submission)."""

    class RepeatedFailureGuardAgent(base):
        def __init__(self, model, env, **kwargs):
            super().__init__(model, env, **kwargs)
            self.guard = dict(turns=[], fired_before_call=None, network=on_start(env) if on_start else None)
            GUARDS.append(self)

        def query(self):
            if stalled(self.guard['turns']):
                self.guard['fired_before_call'] = self.n_calls + 1
                raise RepeatedFailureStall(stall_message())
            try:
                return super().query()
            except format_error:
                self.guard['turns'].append(None)
                raise

        def execute_actions(self, message):
            observations = super().execute_actions(message)
            self.guard['turns'].append(turn_of(message, observations))
            return observations

    RepeatedFailureStall.__module__ = RepeatedFailureGuardAgent.__module__ = 'req012_entry'
    return RepeatedFailureGuardAgent, RepeatedFailureStall


def observe_network(env):
    """The live episode container's docker NetworkMode, recorded once (observational; failures are recorded)."""
    out = dict(container_id=getattr(env, 'container_id', None), run_args=list(env.config.run_args))
    try:
        r = subprocess.run([env.config.executable, 'container', 'inspect', '--format', '{{.HostConfig.NetworkMode}}',
                            out['container_id']], capture_output=True, text=True, timeout=10)
        out.update(returncode=r.returncode, network_mode=r.stdout.strip()[:100] if r.returncode == 0 else None)
    except Exception as e:  # noqa: BLE001  recorded, never raised into the episode
        out.update(network_mode=None, error='%s: %s' % (type(e).__name__, str(e)[:200]))
    return out


def install_overrides():
    """The two declared runtime overrides (this process only). Returns the frozen build_effective_config."""
    import minisweagent.agents.default as D
    from minisweagent.exceptions import FormatError, InterruptAgentFlow
    frozen_build = PE.build_effective_config
    agent_class, _ = make_guarded_agent(D.DefaultAgent, InterruptAgentFlow, FormatError, on_start=observe_network)

    def build_repair1(cfg, **kwargs):
        return repair_config(frozen_build(cfg, **kwargs))
    PE.build_effective_config = build_repair1
    D.DefaultAgent = agent_class
    return frozen_build


# ---------------------------------------------------------------- admission of this process
def running_digests():
    return dict(CE.running_module_digests(), **{'req012_entry.py': SOURCE_SHA256})


def manifest_reasons(control, root=ROOT):
    try:
        raw = (root / MANIFEST_REL).read_bytes()
        m = json.loads(raw)
        rows = [(a['assignment_id'], a['order'], a['backend'], a['port'], a['alias'], a['gguf_sha256'])
                for a in m['assignments']]
        instance, image, recorded = m['instance_id'], m['images']['instance']['id'], m['prompt_bytes']
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return ['the manifest cannot be read: %s' % type(exc).__name__]
    ns, reasons = control['namespace'], []
    if hashlib.sha256(raw).hexdigest() != control.get('binding_sha256'):
        reasons.append('binding_sha256 is not the sha256 of %s' % MANIFEST_REL)
    if ns.get('instance') != instance or ns.get('expected_image') != image:
        reasons.append('instance or expected image differs from the manifest')
    if (control.get('assignment_id'), ns.get('position'), ns.get('backend'), ns.get('port'), ns.get('alias'),
            control.get('model_sha256')) not in rows:
        reasons.append('the assignment (id, order, backend, port, alias, model sha256) is not a manifest assignment')
    try:
        if prompt_bytes(frozen_template()) != recorded:
            reasons.append('the pinned default.yaml does not yield the manifest prompt bytes')
    except (OSError, ValueError, KeyError, ImportError) as exc:
        reasons.append('the repair1 prompt bytes cannot be computed: %s' % type(exc).__name__)
    return reasons


def refusals(control, environ=None, proxies=None):
    environ = os.environ if environ is None else environ
    ns, admitted, reasons = control['namespace'], control['admitted_sources'], []
    running = running_digests()
    for name in CE.RUNNING_MODULES + ('req012_entry',):
        if running.get(name + '.py') is None or running[name + '.py'] != admitted.get(REL + name + '.py'):
            reasons.append('running %s.py is not the admitted source' % name)
    changed = [rel for rel, digest in sorted(admitted.items())
               if not (ROOT / rel).is_file() or hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != digest]
    if changed:
        reasons.append('sources changed since admission: %s' % changed)
    if ns.get('arm') != 'baseline':
        reasons.append('arm %r: DTR-REQ-012 runs the baseline arm only (no cue)' % ns.get('arm'))
    reasons += manifest_reasons(control)
    counted = ns.get('counted_before')
    if type(counted) is not int or counted < 0 or ns.get('request_limit') != max(
            0, min(PER_EPISODE_PHYSICAL, PROBE_PHYSICAL - counted)):
        reasons.append('request budget arguments differ from min(48, 48 - counted_before)')
    if type(ns.get('host_reserve_bytes')) is not int or ns['host_reserve_bytes'] < 0:
        reasons.append('the host reserve must be a non-negative integer')
    run_dir = Path(ns['run_dir'])
    if run_dir.is_symlink() or not run_dir.is_dir() or any(run_dir.iterdir()):
        reasons.append('run_dir must exist, be a real directory and be empty')
    found = sorted(k for k in (urllib.request.getproxies() if proxies is None else proxies) if k != 'no')
    if found:
        reasons.append('proxies configured: %s' % found)
    bad = sorted(k for k in environ if k.startswith('LITELLM_') or k == 'EXPERIMENTAL_OPENAI_BASE_LLM_HTTP_HANDLER')
    if bad:
        reasons.append('environment variables set: %s' % bad)
    return reasons


# ---------------------------------------------------------------- after the episode
def verify_effective(run_dir, ns, frozen_build):
    """effective_config.json (written by run_episode) against the expected repair1 config."""
    import yaml
    path = run_dir / 'effective_config.json'
    if not path.exists():
        return dict(verified=None, problems=['effective_config.json was not written (the episode ended earlier)'])
    rec = json.loads(path.read_text())
    cfg = yaml.safe_load((PE.MSWEA / 'src/minisweagent/config/default.yaml').read_text())
    expected = json.loads(json.dumps(repair_config(frozen_build(cfg, alias=ns.alias, port=ns.port,
                                                                image_id=ns.expected_image))))
    resolved, problems = rec.get('resolved') or {}, []
    if rec.get('constructor_arguments') != expected:
        problems.append('constructor_arguments differ from the expected repair1 config')
    if (resolved.get('agent') or {}).get('instance_template') != expected['agent']['instance_template']:
        problems.append('the resolved instance_template is not the repair1 template')
    if (resolved.get('environment') or {}).get('run_args') != RUN_ARGS:
        problems.append('the resolved run_args are not %s' % RUN_ARGS)
    return dict(verified=not problems, problems=problems, effective_config_sha256=rec.get('effective_config_sha256'),
                instance_template_sha256=sha((resolved.get('agent') or {}).get('instance_template') or ''),
                run_args=(resolved.get('environment') or {}).get('run_args'))


def repair_record(ns, frozen_build):
    rec = dict(request=REQUEST, configuration=CONFIGURATION, entry_source_sha256=SOURCE_SHA256,
               runtime_overrides=OVERRIDES, stall_rule=STALL_RULE, guard=dict(agents_constructed=len(GUARDS)))
    if GUARDS:
        g = GUARDS[-1]
        rec['guard'].update(
            agent_type='%s.%s' % (type(g).__module__, type(g).__name__), fired=g.guard['fired_before_call'] is not None,
            fired_before_call=g.guard['fired_before_call'], n_model_calls=g.n_calls, network=g.guard['network'],
            turns=[None if t is None else dict(command_sha256=sha(t[0]), command_chars=len(t[0]), returncode=t[1],
                                               output_fingerprint=t[2]) for t in g.guard['turns']])
    try:
        rec['effective_config'] = verify_effective(Path(ns.run_dir), ns, frozen_build)
    except Exception as e:  # noqa: BLE001  recorded; the episode records are already written
        rec['effective_config'] = dict(verified=False, problems=['verification failed: %s: %s'
                                                                 % (type(e).__name__, str(e)[:300])])
    return rec


def main(argv=None):
    path = Path((sys.argv[1:] if argv is None else argv)[0])
    control, cdir = json.loads(path.read_text()), path.parent
    reasons = refusals(control)
    if not reasons:
        import httpx
        import minisweagent
        try:
            A.check_running_runtime(dict(runtime=control['runtime']),
                                    site_packages=Path(httpx.__file__).resolve().parents[1],
                                    mswea_package=Path(minisweagent.__file__).resolve().parent)
        except A.AdmissionRefused as exc:
            reasons = exc.reasons
    if reasons:
        WC.write_once(cdir / 'entry_refused.json', json.dumps(dict(admitted=False, reasons=reasons), indent=1) + '\n')
        return EXIT_REFUSED
    frozen_build = install_overrides()
    WC.write_once(cdir / 'entry_admitted.json', json.dumps(dict(
        admitted=True, request=REQUEST, configuration=CONFIGURATION, running_sources=running_digests(),
        runtime_overrides=OVERRIDES, entry_source_sha256=SOURCE_SHA256, validated_utc=A.utc()), indent=1) + '\n')
    ns = argparse.Namespace(**control['namespace'])
    deadline = min(ns.episode_deadline, ns.block_deadline)

    def alarm(_signum, _frame):                       # exactly cue_episode.main's inference alarm
        raise CE.PE.EpisodeDeadline('absolute inference deadline reached; cleanup only')
    signal.signal(signal.SIGALRM, alarm)
    CE.PE.request_timeout(deadline)
    signal.setitimer(signal.ITIMER_REAL, max(1e-6, deadline - time.time()))
    try:
        return CE.run_episode(ns, A.Layout(), dict(binding_sha256=control['binding_sha256']),
                              dict(assignment_id=control['assignment_id'], model_sha256=control['model_sha256']),
                              deadline)
    finally:
        WC.write_once(cdir / 'repair_record.json', json.dumps(repair_record(ns, frozen_build), indent=1,
                                                              default=str) + '\n')


if __name__ == '__main__':
    sys.exit(main())
