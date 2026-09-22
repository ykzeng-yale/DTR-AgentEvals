"""DTR-REQ-002 grading-identity repair (lead e360831). Pure helpers used by grade_submission.py; no docker, no harness.

  * evaluator run ID = eval-<immutable episode run_id>-<first 16 hex of the submission SHA-256>, so two episodes of
    the same task/backend with different patches can never share predictions, harness logs, reports or grades
  * eligibility: only an explicit Submitted episode with a non-empty submission whose SHA-256 equals the episode
    record, and whose pinned image ID equals the image the evaluator will use; the hash is checked BEFORE the
    empty/non-Submitted zero decision, so a tampered file is an integrity refusal, never a valid zero (lead 7cb2062)
  * no-clobber preflight: the predictions file, the harness log directory for that run ID and the grade file must not
    already exist (a cached report can therefore never be reused)
  * report acceptance: the harness's own patch.diff in that run's log directory must hash to the submission and the
    report must be keyed by the instance; anything else is rejected as stale/mismatched
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path


class GradeRefused(RuntimeError):
    pass


class OperationalZero(GradeRefused):
    """Genuine prespecified operational zero: non-Submitted or empty submission (valid grade, not evaluated)."""


class IntegrityRefusal(GradeRefused):
    """Hash/image/identity mismatch or a stale report: NOT an observed model failure (grade_valid=false, grade unknown)."""


class EvaluatorUnknown(RuntimeError):
    """Evaluator produced no patch.diff/report (e.g. pre-container failure): algorithmic correctness unknown."""


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def evaluator_run_id(episode, submission):
    if not episode.get('run_id'):
        raise IntegrityRefusal('episode has no immutable run_id (pre-wc2 episode): not gradeable under the repaired identity')
    return 'eval-%s-%s' % (episode['run_id'], sha(submission)[:16])


def hash_check(episode, submission):
    if sha(submission) != episode.get('submission_sha256'):
        raise IntegrityRefusal('saved submission hash differs from the episode record')


def image_check(episode, current_image_id):
    if episode.get('pins', {}).get('image_id') != current_image_id:
        raise IntegrityRefusal('image identity mismatch: episode %s vs evaluator %s' % (episode.get('pins', {}).get('image_id'), current_image_id))


def eligibility(episode, submission, current_image_id):
    hash_check(episode, submission)
    if episode.get('pins', {}).get('image_id') != current_image_id:
        raise IntegrityRefusal('image identity mismatch: episode %s vs evaluator %s' % (episode.get('pins', {}).get('image_id'), current_image_id))


def operational(episode, submission):
    if episode.get('exit_status') != 'Submitted':
        raise OperationalZero('not a Submitted episode (%s): operational zero, not evaluated' % episode.get('exit_status'))
    if not submission.strip():
        raise OperationalZero('empty submission: operational zero, not evaluated')


def preflight(preds_path, harness_log_dir, grade_path):
    for p in (preds_path, harness_log_dir, grade_path):
        if Path(p).exists():
            raise GradeRefused('refusing to reuse existing output: %s' % p)


def accept_report(harness_log_dir, instance_id, submission):
    d = Path(harness_log_dir)
    pd, rp = d / 'patch.diff', d / 'report.json'
    if not pd.exists():
        raise EvaluatorUnknown('no patch.diff: evaluator failed before the container applied the patch')
    if sha(pd.read_text()) != sha(submission):
        raise IntegrityRefusal('stale or mismatched report: evaluated patch differs from the submission')
    if not rp.exists():
        raise EvaluatorUnknown('no report.json: evaluator failure after patch application')
    try:
        rep = json.loads(rp.read_text())
    except ValueError as e:
        raise EvaluatorUnknown('malformed report.json (%s): algorithmic correctness unknown' % type(e).__name__)
    if not isinstance(rep, dict) or instance_id not in rep:
        raise IntegrityRefusal('report is not keyed by %s (keys %s): not this instance\'s grade' % (
            instance_id, sorted(rep)[:5] if isinstance(rep, dict) else type(rep).__name__))
    if not isinstance(rep[instance_id], dict):
        raise IntegrityRefusal('report payload for %s is %s, expected an object' % (instance_id, type(rep[instance_id]).__name__))
    return rep


def diagnostics(harness_log_dir):
    """Raw evidence kept with every attempt: name, size and SHA-256 of each file the evaluator left (never parsed)."""
    d = Path(harness_log_dir)
    return {f.name: dict(bytes=f.stat().st_size, sha256=hashlib.sha256(f.read_bytes()).hexdigest())
            for f in sorted(d.glob('*')) if f.is_file()} if d.is_dir() else {}


def grade_flow(episode, submission, image_id, work, grade_path, run_harness, strict_fn, alias, max_attempts=2):
    """Complete grading decision with durable records (lead fd5f42c). run_harness(run_id, preds_path) runs the pinned
    evaluator; strict_fn(log_dir) -> (strict_outcome, required_status). Returns and writes (no-clobber) the grade."""
    iid = episode['instance_id']
    base = dict(instance_id=iid, backend=episode.get('backend'), exit_status=episode.get('exit_status'), episode_run_id=episode.get('run_id'),
                submission_sha256=sha(submission), image_id=image_id, evaluator_commit='f7bbbb2ccdf479001d6467c9e34af59e44a840f9')

    def write(g):
        with open(grade_path, 'x') as fh:
            fh.write(json.dumps(g, indent=1, default=str) + '\n')
        return g
    def refuse(e):
        return write(dict(base, classification='integrity_refusal', grade_valid=False, evaluated=False, operational_resolved=None,
                          algorithmic_correctness=None, reason=str(e)))
    try:
        hash_check(episode, submission)          # BEFORE the empty-zero decision (lead 7cb2062): a tampered-empty file is not a zero
    except IntegrityRefusal as e:
        return refuse(e)
    try:
        operational(episode, submission)
    except OperationalZero as e:
        return write(dict(base, classification='operational_zero', grade_valid=True, evaluated=False, operational_resolved=0,
                          algorithmic_correctness='not_evaluated', reason=str(e)))
    try:
        image_check(episode, image_id)
        root_id = evaluator_run_id(episode, submission)
    except IntegrityRefusal as e:
        return refuse(e)
    work = Path(work)
    attempts = []
    for a in range(1, max_attempts + 1):
        rid = '%s-a%d' % (root_id, a)
        preds, runroot = work / (rid + '.preds.json'), work / 'logs/run_evaluation' / rid
        preflight(preds, runroot, grade_path)
        with open(preds, 'x') as fh:
            fh.write(json.dumps({iid: dict(model_name_or_path=alias, instance_id=iid, model_patch=submission)}))
        hres = run_harness(rid, preds)
        logd = runroot / alias / iid
        try:
            report = accept_report(logd, iid, submission)
        except EvaluatorUnknown as e:
            attempts.append(dict(attempt=a, evaluator_run_id=rid, status='unknown_evaluator_failure', reason=str(e), harness=hres,
                                 raw=diagnostics(logd)))
            continue
        except IntegrityRefusal as e:
            attempts.append(dict(attempt=a, evaluator_run_id=rid, status='integrity_refusal', reason=str(e), harness=hres,
                                 raw=diagnostics(logd)))
            return write(dict(base, classification='integrity_refusal', grade_valid=False, evaluated=True, operational_resolved=None,
                              algorithmic_correctness=None, reason=str(e), attempts=attempts))
        strict, required = strict_fn(logd)
        attempts.append(dict(attempt=a, evaluator_run_id=rid, status='completed', harness=hres))
        return write(dict(base, classification='evaluated', grade_valid=True, evaluated=True, upstream_report=report,
                          upstream_resolved=bool(report.get(iid, {}).get('resolved')), strict_outcome=strict,
                          operational_resolved=int(strict == 'resolved'), algorithmic_correctness=strict, required_status=required,
                          attempts=attempts))
    return write(dict(base, classification='unknown_evaluator_failure', grade_valid=True, evaluated=False, operational_resolved=0,
                      algorithmic_correctness='unknown', reason='evaluator produced no usable report in %d attempts' % len(attempts),
                      attempts=attempts))
