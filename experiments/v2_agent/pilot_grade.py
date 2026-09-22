"""DTR-REQ-002 pilot grading after an accelerator block (CPU/VM only): runs grade_submission.py (repaired grade_flow:
identity-bound evaluator run IDs, durable classifications, one identical-patch retry) on every terminal pilot episode
that has no grade.json yet, serially, in frame order. Existing grades are never touched.
  work/venvs/swebench_f7bbbb2/bin/python experiments/v2_agent/pilot_grade.py
"""
import argparse, json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_runner as PR  # noqa: E402
import pilot_report as RP  # noqa: E402


def grade_pass(frame, out, run_grade, *, expected_binding=None, expected_source=None):
    """Prevalidate the complete queue, then grade pending terminals only.

    Existing grades must bind to the episode and patch before they can be skipped.
    A failed grading subprocess without grade.json remains explicitly ungraded.
    run_grade(directory) is injectable for deterministic tests.
    """
    out = Path(out)
    states = [(item, PR.episode_state(out, item)) for item in PR.episode_queue(frame)]
    admissions = {}
    for item, (state, done, _) in states:
        if state == 'completed':
            admissions[done[0]] = RP.episode_summary(out / done[0], item, expected_binding=expected_binding,
                                                    expected_source=expected_source)
    results = []
    for item, (state, done, _) in states:
        result = dict(instance_id=item['instance_id'], backend=item['backend'])
        if state != 'completed':
            results.append(dict(result, state='incomplete' if state == 'incomplete' else 'unstarted'))
            continue
        directory = out / done[0]
        provenance = admissions[done[0]]['configuration_provenance']
        result['configuration_provenance'] = provenance
        if expected_binding is not None and provenance['status'] != 'validated':
            results.append(dict(result, state='configuration_refusal', run_id=done[0],
                                reason='preserved outcome; reconcile effective configuration before grading'))
            continue
        if (directory / 'grade.json').exists():
            results.append(dict(result, state='already_graded', run_id=done[0]))
            continue
        process = run_grade(directory)
        result.update(run_id=done[0], returncode=process.returncode,
                      stderr_tail=(process.stderr or '')[-1000:])
        if (directory / 'grade.json').exists():
            row = RP.episode_summary(directory, item)
            result.update(state='graded', classification=row['classification'])
        else:
            result.update(state='ungraded', reason='grading process left no durable grade; no outcome imputed')
        results.append(result)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cohort', choices=tuple(PR.PC.COHORTS), default='legacy')
    args = ap.parse_args()
    out = PR.PC.cohort_output(args.cohort)
    frame = json.loads(PR.FRAME.read_text())
    def run_grade(directory):
        return subprocess.run([sys.executable, str(ROOT / 'experiments/v2_agent/grade_submission.py'), str(directory)],
                              capture_output=True, text=True)
    provenance = RP.cohort_metadata(args.cohort, out)
    results = grade_pass(frame, out, run_grade, expected_binding='yaml-v1' if args.cohort == 'yaml-v1' else None,
                         expected_source=provenance['expected_episode_source_sha256'])
    stamp = time.strftime('%Y%m%dT%H%M%S', time.gmtime()) + '-%d' % time.time_ns()
    with open(out / ('grading_pass_' + stamp + '.json'), 'x') as fh:
        json.dump(dict(kind='grading process receipt; absent grades remain ungraded', cohort=args.cohort, cohort_provenance=provenance, episodes=results), fh, indent=1)
        fh.write('\n')
    for result in results:
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
