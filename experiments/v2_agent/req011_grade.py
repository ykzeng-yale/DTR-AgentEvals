"""DTR-REQ-011: strict grading of ONE episode run directory, launched by req011_pair.py after the model server stopped.

    work/venvs/swebench_f7bbbb2/bin/python experiments/v2_agent/req011_grade.py <control>/grade_control.json

The decision is grade_identity.grade_flow unchanged (hash check before the zero decision; non-Submitted or empty ->
operational zero without the evaluator; image identity; unique no-clobber evaluator run IDs; report acceptance only for
the identical patch; strict declared_outcome), with the stock f7bbbb2 command of grade_submission.py. Added here only:
  * a wall budget per evaluator attempt, min(1800 s, pair deadline - 300 s - now); an attempt starts only if that budget
    is >= 600 s, otherwise the grade is 'ungraded: pair cap' (never imputed);
  * process containment: the parent starts this grader as a session and process-group leader, and the stock evaluator
    runs INSIDE that group (as grade_submission.py's subprocess.run does), so the parent's group kill at the pair cap or
    on an operator signal always reaches it and anything it starts. After every attempt, however it ends (normal exit,
    wall budget, or SIGINT/SIGTERM/SIGHUP -> S.Interrupted), the evaluator is stopped (SIGTERM, 20 s, SIGKILL) and only
    its own stock container 'sweb.eval.<instance>.<evaluator run id>' is removed (exact name), before anything else;
  * the lead's retry rule over grade_flow's single identical retry: retry only after a stock timeout, an attempt killed
    at its wall budget, or test output without a report; a setup failure (no test output: image build or patch
    application), an unusable present report, or an evaluator whose termination is unconfirmed is a recorded diagnosis;
  * the instance image ID must equal the pin before grading and after it (a changed image after grading invalidates the
    grade status).
The outcome record is <control>/grade_result.json (write-once); grade_flow writes <run_dir>/grade.json itself.
"""
from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / 'experiments/v2_adapter', ROOT / 'experiments/v2_agent'):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import req010_sentinel as S  # noqa: E402
import grade_submission as GS  # noqa: E402  frozen; its module-level pieces are reused, its main() is not run

GI = GS.GI
RETRYABLE = ('timeout', 'missing_report', 'wall_timeout')
SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


class Ungraded(Exception):
    """An evaluator attempt could not start inside the pair cap."""


class NoRetry(Exception):
    """The previous attempt's outcome is not retryable under the lead's rule (a diagnosis, not a grade)."""


def harness_cmd(iid, run_id, preds, work, python=sys.executable):
    """grade_submission.py's stock command, argument for argument."""
    return [python, '-m', 'swebench.harness.run_evaluation', '--dataset_name', str(GS.DATA), '--split', 'train',
            '--predictions_path', str(preds), '--instance_ids', iid, '--run_id', run_id, '--namespace', 'none',
            '--max_workers', '1', '--timeout', '1800', '--cache_level', 'instance', '--report_dir', str(work)]


def evaluator_container(iid, run_id):
    return 'sweb.eval.%s.%s' % (iid, run_id)


def remove_container(name, env, run=S.sh):
    """docker rm -f of exactly this stock container name, only while listed; then a relist."""
    def listed():
        rc, out, _ = run(['docker', 'ps', '-a', '--format', '{{.Names}}'], env=env, timeout=30)
        return (name in out.split()) if rc == 0 else None
    found = listed()
    rm_rc = run(['docker', 'rm', '-f', name], env=env, timeout=60)[0] if found else None
    remaining = listed() if found else found
    return OrderedDict(name=name, found=found, rm_rc=rm_rc, remaining=remaining, complete=remaining is False)


def stop_evaluator(p, grace=S.KILL_GRACE_SECONDS):
    """SIGTERM, grace, SIGKILL to the evaluator (our unreaped child, so its PID cannot have been reused); returns
    whether it is confirmed exited. Anything it started shares this grader's process group, which the parent kills."""
    for sig, wait in ((signal.SIGTERM, grace), (signal.SIGKILL, 10)):
        if p.poll() is not None:
            return True
        try:
            p.send_signal(sig)
        except ProcessLookupError:
            pass
        try:
            p.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            pass
    return p.poll() is not None


def make_run_harness(iid, alias, work, pair_deadline, caps, log, env, *, clock=time.time, popen=subprocess.Popen,
                     run=S.sh):
    def run_harness(run_id, preds):
        if log and log[-1].get('classification') not in RETRYABLE:
            raise NoRetry('attempt %d classified %s: not retried (retry only after a timeout or a missing report)'
                          % (len(log), log[-1].get('classification')))
        if log and not log[-1].get('evaluator_stopped'):
            raise NoRetry('attempt %d: evaluator termination unconfirmed; no second evaluator is started' % len(log))
        budget = min(caps['evaluator_attempt_max_s'], pair_deadline - caps['evaluator_end_reserve_s'] - clock())
        if budget < caps['evaluator_min_start_budget_s']:
            raise Ungraded('evaluator attempt %s not started: %.0f s left inside the pair cap (< %d s)'
                           % (run_id, budget, caps['evaluator_min_start_budget_s']))
        t0, wall, p = clock(), False, None
        row = OrderedDict(attempt=len(log) + 1, evaluator_run_id=run_id, budget_s=round(budget, 1))
        log.append(row)                                   # before the spawn: an interrupted attempt is still recorded
        try:
            with open(Path(work) / (run_id + '.harness_stdout.txt'), 'x') as out:
                p = popen(harness_cmd(iid, run_id, preds, work), cwd=str(work), env=env, stdout=out,
                          stderr=subprocess.STDOUT)      # same process group as this grader (no new session)
                try:
                    S.wait_wall(p, t0 + budget, clock=clock)
                except subprocess.TimeoutExpired:
                    wall = True
        finally:                                          # every exit, including S.Interrupted, stops and cleans first
            row.update(evaluator_stopped=True if p is None else stop_evaluator(p),
                       returncode=None if p is None else p.poll(), wall_timeout=wall,
                       container_cleanup=remove_container(evaluator_container(iid, run_id), env, run),
                       seconds=round(clock() - t0, 1))
        cls = 'wall_timeout' if wall else S.classify_stock(Path(work) / 'logs/run_evaluation' / run_id / alias / iid)
        row['classification'] = cls
        if cls == 'setup_failure':
            raise NoRetry('stock setup failure (no test output: image build or patch application); recorded as a '
                          'diagnosis, not retried')
        return dict(returncode=p.returncode, wall_timeout=wall, classification=cls)
    return run_harness


def strict_fn(iid):
    """grade_submission.py's strict rule, rebuilt from its module-level pieces."""
    def strict(logd):
        import pandas as pd
        from swebench.harness.grading import get_logs_eval
        from swebench.harness.test_spec.test_spec import make_test_spec
        row = next(r for r in pd.read_parquet(GS.DATA).to_dict('records') if r['instance_id'] == iid)
        inst = {k: (v if not hasattr(v, 'item') else v.item()) for k, v in row.items()}
        (f2p, _), (p2p, _) = GS.Q.parse_test_list(inst, 'FAIL_TO_PASS'), GS.Q.parse_test_list(inst, 'PASS_TO_PASS')
        log_fp = Path(logd) / 'test_output.txt'
        if not log_fp.exists():
            return 'unknown_evaluator_failure', None
        smap, found = get_logs_eval(make_test_spec(inst), str(log_fp))
        return GS.declared_outcome(f2p, p2p, smap, log_ok=found), {t: smap.get(t) for t in list(f2p) + list(p2p)}
    return strict


def grade(control, *, run=S.sh, popen=subprocess.Popen, clock=time.time, strict=None):
    run_dir, work = Path(control['run_dir']), Path(control['work'])
    rec = json.loads((run_dir / 'episode.json').read_text())
    submission = (run_dir / 'submission.diff').read_text()
    iid, alias = rec['instance_id'], rec.get('backend_alias', 'model')
    env = S.scrub_env(S.docker_env())[0]

    def image():
        return run(['docker', 'image', 'inspect', '--format', '{{.Id}}', 'sweb.eval.x86_64.%s:latest' % iid],
                   env=env)[1].strip()
    log = []
    out = dict(request='DTR-REQ-011', run_id=rec.get('run_id'), image_pin=control['image_pin'], image_before=None,
               attempts=log, status=None, reason=None)
    try:
        out['image_before'] = image()
        if out['image_before'] != control['image_pin']:
            out.update(status='refused: instance image differs from the pin before grading')
            return out
        work.mkdir(parents=True, exist_ok=True)
        harness = make_run_harness(iid, alias, work, control['pair_deadline'], control['caps'], log, env, clock=clock,
                                   popen=popen, run=run)
        g = GI.grade_flow(rec, submission, out['image_before'], work, run_dir / 'grade.json', harness,
                          strict or strict_fn(iid), alias, max_attempts=control['caps']['evaluator_max_attempts'])
        out['status'] = 'graded: %s' % g['classification']
    except S.Interrupted as e:                      # the attempt's finally already stopped the evaluator and cleaned
        out.update(status='ungraded: interrupted (%s)' % e, reason='signalled during grading; no image re-check')
        return out
    except Ungraded as e:
        out.update(status='ungraded: pair cap', reason=str(e))
    except NoRetry as e:
        out.update(status='diagnosis: no strict grade (evaluator result not retryable)', reason=str(e))
    except Exception as e:  # noqa: BLE001  recorded, never imputed
        out.update(status='error: no grade', reason='%s: %s' % (type(e).__name__, str(e)[:300]))
    out['image_after'] = image()
    out['image_after_equals_pin'] = out['image_after'] == control['image_pin']
    if not out['image_after_equals_pin']:
        out['status'] = 'invalid: instance image differs from the pin after grading (was %s)' % out['status']
    return out


def main(argv=None, **grade_kw):
    """Signals are armed before anything else: the first SIGINT/SIGTERM/SIGHUP raises S.Interrupted (later ones are
    ignored), so the running attempt's finally stops the evaluator and removes its container, and grade_result.json is
    still written."""
    old = {sig: signal.signal(sig, S.raise_interrupted) for sig in SIGNALS}
    try:
        path = Path((sys.argv[1:] if argv is None else argv)[0])
        control = json.loads(path.read_text())
        changed = [s for s, h in sorted(control['admitted_sources'].items()) if S.sha_file(ROOT / s) != h]
        if changed:
            out = dict(request='DTR-REQ-011', status='refused: sources changed since admission', changed=changed)
        else:
            try:
                out = grade(control, **grade_kw)
            except S.Interrupted as e:              # outside an attempt (e.g. the image inspection)
                out = dict(request='DTR-REQ-011', status='ungraded: interrupted (%s)' % e)
        with open(path.parent / 'grade_result.json', 'x') as fh:
            fh.write(json.dumps(out, indent=1, default=str) + '\n')
        print(json.dumps({k: out.get(k) for k in ('run_id', 'status')}))
        return 3 if changed else 0
    finally:
        for sig, handler in old.items():
            signal.signal(sig, handler)


if __name__ == '__main__':
    sys.exit(main())
