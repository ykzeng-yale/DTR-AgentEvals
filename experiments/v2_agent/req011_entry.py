"""DTR-REQ-011: ONE fixed-backend 'baseline' episode, launched by req011_pair.py in the pinned mini-swe-agent venv.

    work/venvs/minisweagent_04d809c/bin/python experiments/v2_agent/req011_entry.py <control>/entry.json

It adds only an admission of THIS process and then calls the validated cue_episode.run_episode unchanged: REQ-005
pre-dispatch receipts, the Submitted-only wc2 endpoint written before the supervised all-exit diagnostic, and cleanup on
every exit. tests/test_req011_pair.py runs this entry and the frozen yaml-v1 pilot_episode driver on the same stub
scripts and requires byte-identical request bodies, identical trajectory messages, submission.diff, exit status,
physical request count and effective configuration (apart from the fixture's docker path). cue_episode.main is not used
because its admission is the cue-v1 queue's.

Refused (entry_refused.json in the control directory, exit 3, nothing else written) unless: every bound source this
process runs, and every admitted source on disk, equals the digest the parent admitted; the pinned SDK and
mini-swe-agent files are the bound bytes; the arm is 'baseline'; the binding digest is the committed manifest's sha256
and the instance, expected image and (assignment, order, backend, port, alias, model sha256) are the manifest's; the
request budget follows min(48, 96 - counted_before); run_dir exists, is a real directory and is empty; there is no
proxy and no LITELLM_* / EXPERIMENTAL_OPENAI_BASE_LLM_HTTP_HANDLER variable.
"""
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import cue_episode as CE  # noqa: E402  FIRST: its pilot_episode import sets MSWEA_* before minisweagent loads

import argparse  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import signal  # noqa: E402
import time  # noqa: E402
import urllib.request  # noqa: E402

A, WC = CE.A, CE.WC
ROOT = HERE.parents[1]
REL = 'experiments/v2_agent/'
SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
EXIT_REFUSED = 3
PER_EPISODE_PHYSICAL, PAIR_PHYSICAL = 48, 96
MANIFEST_REL = 'configs/v2_req011_competence_pair_20260924.json'


def running_digests():
    return dict(CE.running_module_digests(), **{'req011_entry.py': SOURCE_SHA256})


def manifest_reasons(control, root=ROOT):
    """The parent's control record is cross-checked against the committed manifest (itself an admitted source)."""
    try:
        raw = (root / MANIFEST_REL).read_bytes()
        m = json.loads(raw)
        rows = [(a['assignment_id'], a['order'], a['backend'], a['port'], a['alias'], a['gguf_sha256'])
                for a in m['assignments']]
        instance, image = m['instance_id'], m['images']['instance']['id']
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
    return reasons


def refusals(control, environ=None, proxies=None):
    environ = os.environ if environ is None else environ
    ns, admitted, reasons = control['namespace'], control['admitted_sources'], []
    running = running_digests()
    for name in CE.RUNNING_MODULES + ('req011_entry',):
        if running.get(name + '.py') is None or running[name + '.py'] != admitted.get(REL + name + '.py'):
            reasons.append('running %s.py is not the admitted source' % name)
    changed = [rel for rel, digest in sorted(admitted.items())
               if hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != digest]
    if changed:
        reasons.append('sources changed since admission: %s' % changed)
    if ns.get('arm') != 'baseline':
        reasons.append('arm %r: DTR-REQ-011 runs the baseline arm only (no cue)' % ns.get('arm'))
    reasons += manifest_reasons(control)
    counted = ns.get('counted_before')
    if type(counted) is not int or counted < 0 or ns.get('request_limit') != max(
            0, min(PER_EPISODE_PHYSICAL, PAIR_PHYSICAL - counted)):
        reasons.append('request budget arguments differ from min(48, 96 - counted_before)')
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
    WC.write_once(cdir / 'entry_admitted.json', json.dumps(dict(
        admitted=True, request='DTR-REQ-011', running_sources=running_digests(), validated_utc=A.utc()), indent=1) + '\n')
    ns = argparse.Namespace(**control['namespace'])
    deadline = min(ns.episode_deadline, ns.block_deadline)

    def alarm(_signum, _frame):                       # exactly cue_episode.main's inference alarm
        raise CE.PE.EpisodeDeadline('absolute inference deadline reached; cleanup only')
    signal.signal(signal.SIGALRM, alarm)
    CE.PE.request_timeout(deadline)
    signal.setitimer(signal.ITIMER_REAL, max(1e-6, deadline - time.time()))
    return CE.run_episode(ns, A.Layout(), dict(binding_sha256=control['binding_sha256']),
                          dict(assignment_id=control['assignment_id'], model_sha256=control['model_sha256']), deadline)


if __name__ == '__main__':
    sys.exit(main())
