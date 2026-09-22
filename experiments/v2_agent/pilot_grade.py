"""DTR-REQ-002 pilot grading after an accelerator block (CPU/VM only): runs grade_submission.py (repaired grade_flow:
identity-bound evaluator run IDs, durable classifications, one identical-patch retry) on every terminal pilot episode
that has no grade.json yet, serially, in frame order. Existing grades are never touched.
  work/venvs/swebench_f7bbbb2/bin/python experiments/v2_agent/pilot_grade.py
"""
import json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_runner as PR  # noqa: E402
import pilot_report as RP  # noqa: E402


def grade_pass(frame, out, run_grade):
    """Prevalidate the complete queue, then grade pending terminals only.

    Existing grades must bind to the episode and patch before they can be skipped.
    A failed grading subprocess without grade.json remains explicitly ungraded.
    run_grade(directory) is injectable for deterministic tests.
    """
    out = Path(out)
    states = [(item, PR.episode_state(out, item)) for item in PR.episode_queue(frame)]
    for item, (state, done, _) in states:
        if state == 'completed':
            RP.episode_summary(out / done[0], item)
    results = []
    for item, (state, done, _) in states:
        result = dict(instance_id=item['instance_id'], backend=item['backend'])
        if state != 'completed':
            results.append(dict(result, state='incomplete' if state == 'incomplete' else 'unstarted'))
            continue
        directory = out / done[0]
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
    frame = json.loads(PR.FRAME.read_text())
    def run_grade(directory):
        return subprocess.run([sys.executable, str(ROOT / 'experiments/v2_agent/grade_submission.py'), str(directory)],
                              capture_output=True, text=True)
    results = grade_pass(frame, PR.OUT, run_grade)
    stamp = time.strftime('%Y%m%dT%H%M%S', time.gmtime()) + '-%d' % time.time_ns()
    with open(PR.OUT / ('grading_pass_' + stamp + '.json'), 'x') as fh:
        json.dump(dict(kind='grading process receipt; absent grades remain ungraded', episodes=results), fh, indent=1)
        fh.write('\n')
    for result in results:
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
