"""DTR-REQ-014 (lead b9ffb29, docs/theory_feedback_20260924_req013_capacity_decision.md): the REQ-012 entry, unchanged,
bound to the REQ-014 manifest for its one 14B assignment. req014_pair.py launches it in the pinned mini-swe-agent venv:

    work/venvs/minisweagent_04d809c/bin/python experiments/v2_agent/req014_entry.py <control>/entry.json

req013_entry.py cannot be reused unchanged: it binds the REQ-013 manifest, whose sha256 the entry compares with the
control's binding. This shim therefore rebinds req013_entry's two constants (MANIFEST_REL, REQUEST) to REQ-014's in
this process only and then calls the unedited req013_entry.bind(), which rebinds req012_entry exactly as for REQ-013
(manifest, label, and req013_entry.py in the admitted-source check). It adds this file's own sha256 to that check.
req012_entry.main then runs unedited with the same yaml-v1-repair1 overrides, guard, refusals and records. No source
file is edited.

The capacity-stop latch (manifest supervision.entry_latch). The parent's capacity stop is one SIGALRM, which runs the
frozen alarm handler (EpisodeDeadline). The pinned DockerEnvironment.execute turns ANY Exception raised during a
container command into a returncode -1 observation, so a SIGALRM that lands during a command is swallowed and the agent
queries again; after the natural deadline the frozen pilot_episode.request_timeout refuses that query, but after a
capacity stop the deadline has not passed. Three overrides of THIS process close that gap without touching a request
byte (install_latch):
  (1) pilot_episode.request_timeout: the frozen function first (its own deadline refusal and value are unchanged), then,
      once any SIGALRM has been received, pilot_episode.EpisodeDeadline, so CueModel.query/_query refuse before dispatch
      exactly as after the natural deadline;
  (2) the SIGALRM handler installed by req012_entry.main is chained at the first request_timeout call (req012_entry.main
      makes it right after installing the handler): every signal is counted, then the frozen handler runs, except
  (3) after the inference phase has ended (cue_terminal.run_terminal_phase has been entered; the frozen timer is
      disarmed there, so only an external signal can arrive), when the signal is only counted and the terminal phase
      and the records run unharmed.
The latch record control/capacity_latch.json is written once when the entry leaves, if the chain was installed. The
natural deadline is unchanged: its SIGALRM runs the frozen handler, and the frozen request_timeout refuses first.
entry_admitted.json and repair_record.json keep req012_entry's two repair1 runtime_overrides; these three are
declared in the manifest (supervision.entry_latch) and listed in the latch record.
"""
import hashlib
import json
import signal
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import req013_entry as E13  # noqa: E402  FIRST: it imports req012_entry (and cue_episode) before minisweagent loads

REQUEST = 'DTR-REQ-014'
MANIFEST_REL = 'configs/v2_req014_14b_capacity_probe_20260924.json'
SOURCE_REL = E13.R.REL + 'req014_entry.py'
SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
LATCH_RECORD = 'capacity_latch.json'
LATCH_MESSAGE = ('a SIGALRM was received before the inference deadline (capacity stop): no further inference; '
                 'cleanup only')
LATCH_OVERRIDES = [
    'pilot_episode.request_timeout -> req014_entry latch: the frozen function first, then, once a SIGALRM has been '
    'received, pilot_episode.EpisodeDeadline (no request is dispatched after the signal)',
    "the SIGALRM handler installed by req012_entry.main -> req014_entry chain (installed at the first request_timeout "
    "call): the signal is counted, then the frozen handler raises EpisodeDeadline; after the inference phase has "
    "ended the signal is only counted",
    'cue_terminal.run_terminal_phase -> req014_entry marker: records the end of the inference phase, then the frozen '
    'function']


def bind():
    """req013_entry.bind() with its manifest and label rebound to REQ-014's, plus this file in the source check."""
    E13.MANIFEST_REL, E13.REQUEST = MANIFEST_REL, REQUEST
    module = E13.bind()
    base_refusals, base_digests = module.refusals, module.running_digests

    def running_digests():
        return dict(base_digests(), **{'req014_entry.py': SOURCE_SHA256})

    def refusals(control, environ=None, proxies=None):
        reasons = base_refusals(control, environ, proxies)
        if (control.get('admitted_sources') or {}).get(SOURCE_REL) != SOURCE_SHA256:
            reasons.append('running req014_entry.py is not the admitted source')
        return reasons
    module.running_digests, module.refusals = running_digests, refusals
    return module


def install_latch(module, clock=time.time):
    """The three latch overrides (module docstring) in this process; returns the live latch state."""
    PE, T = module.CE.PE, module.CE.T
    frozen_timeout, frozen_terminal = PE.request_timeout, T.run_terminal_phase
    state = dict(installed=False, overrides=LATCH_OVERRIDES, sigalrm_received=0, first_sigalrm_utc=None,
                 first_sigalrm_after_inference_end=None, sigalrm_counted_only=0, inference_end_utc=None,
                 queries_refused_by_latch=0)
    frozen_handler = []

    def utc():
        return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(clock()))

    def on_alarm(signum, frame):
        state['sigalrm_received'] += 1
        ended = state['inference_end_utc'] is not None
        if state['first_sigalrm_utc'] is None:
            state.update(first_sigalrm_utc=utc(), first_sigalrm_after_inference_end=ended)
        if ended:
            state['sigalrm_counted_only'] += 1
            return None
        return frozen_handler[0](signum, frame)

    def request_timeout(deadline, now=None):
        if not frozen_handler:
            handler = signal.getsignal(signal.SIGALRM)
            if callable(handler):
                frozen_handler.append(handler)
                signal.signal(signal.SIGALRM, on_alarm)
                state['installed'] = True
        left = frozen_timeout(deadline, now)          # the frozen refusal once the deadline has passed, unchanged
        if state['sigalrm_received']:
            state['queries_refused_by_latch'] += 1
            raise PE.EpisodeDeadline(LATCH_MESSAGE)
        return left

    def run_terminal_phase(**kwargs):
        state['inference_end_utc'] = utc()
        return frozen_terminal(**kwargs)
    PE.request_timeout, T.run_terminal_phase = request_timeout, run_terminal_phase
    return state


def main(argv=None):
    module = bind()
    latch = install_latch(module)
    path = Path((sys.argv[1:] if argv is None else argv)[0])
    try:
        return module.main(argv)
    finally:
        if latch['installed']:
            try:                                      # evidence only: a failed write never replaces the exit
                module.WC.write_once(path.parent / LATCH_RECORD, json.dumps(dict(
                    request=REQUEST, entry_source_sha256=SOURCE_SHA256, **latch), indent=1) + '\n')
            except OSError:
                pass


if __name__ == '__main__':
    sys.exit(main())
