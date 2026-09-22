"""DTR-REQ-002 grading-identity repair (lead e360831). Pure helpers used by grade_submission.py; no docker, no harness.

  * evaluator run ID = eval-<immutable episode run_id>-<first 16 hex of the submission SHA-256>, so two episodes of
    the same task/backend with different patches can never share predictions, harness logs, reports or grades
  * eligibility: only an explicit Submitted episode with a non-empty submission whose SHA-256 equals the episode
    record, and whose pinned image ID equals the image the evaluator will use
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


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def evaluator_run_id(episode, submission):
    if not episode.get('run_id'):
        raise GradeRefused('episode has no immutable run_id (pre-wc2 episode): not gradeable under the repaired identity')
    return 'eval-%s-%s' % (episode['run_id'], sha(submission)[:16])


def eligibility(episode, submission, current_image_id):
    if episode.get('exit_status') != 'Submitted':
        raise GradeRefused('not a Submitted episode (%s): operational zero, not evaluated' % episode.get('exit_status'))
    if not submission.strip():
        raise GradeRefused('empty submission: operational zero, not evaluated')
    if sha(submission) != episode.get('submission_sha256'):
        raise GradeRefused('saved submission hash differs from the episode record')
    if episode.get('pins', {}).get('image_id') != current_image_id:
        raise GradeRefused('image identity mismatch: episode %s vs evaluator %s' % (episode.get('pins', {}).get('image_id'), current_image_id))


def preflight(preds_path, harness_log_dir, grade_path):
    for p in (preds_path, harness_log_dir, grade_path):
        if Path(p).exists():
            raise GradeRefused('refusing to reuse existing output: %s' % p)


def accept_report(harness_log_dir, instance_id, submission):
    d = Path(harness_log_dir)
    pd, rp = d / 'patch.diff', d / 'report.json'
    if not pd.exists() or sha(pd.read_text()) != sha(submission):
        raise GradeRefused('stale or mismatched report: evaluated patch differs from the submission')
    if not rp.exists():
        return None                                   # evaluator produced no report: unknown_evaluator_failure upstream
    rep = json.loads(rp.read_text())
    if instance_id not in rep:
        raise GradeRefused('report is not keyed by %s' % instance_id)
    return rep
