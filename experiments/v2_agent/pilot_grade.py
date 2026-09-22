"""DTR-REQ-002 pilot grading after an accelerator block (CPU/VM only): runs grade_submission.py (repaired grade_flow:
identity-bound evaluator run IDs, durable classifications, one identical-patch retry) on every terminal pilot episode
that has no grade.json yet, serially, in frame order. Existing grades are never touched.
  work/venvs/swebench_f7bbbb2/bin/python experiments/v2_agent/pilot_grade.py
"""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_runner as PR  # noqa: E402


def main():
    frame = json.loads(PR.FRAME.read_text())
    for it in PR.episode_queue(frame):
        state, done, _ = PR.episode_state(PR.OUT, it)
        if state != 'completed' or (PR.OUT / done[0] / 'grade.json').exists():
            continue
        p = subprocess.run([sys.executable, str(ROOT / 'experiments/v2_agent/grade_submission.py'), str(PR.OUT / done[0])],
                           capture_output=True, text=True)
        print(it['instance_id'], it['backend'], p.returncode, (p.stdout.strip().splitlines() or [''])[-1][:300], flush=True)


if __name__ == '__main__':
    main()
