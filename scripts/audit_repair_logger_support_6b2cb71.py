"""Read-only counterexample audit of the archived final-only support labels."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = '6b2cb71c3b5633480634708394bc8672144538c0'
SOURCE = 'experiments/v2_sim/repair_logger_v1.json'
raw = subprocess.check_output(['git', 'show', f'{REF}:{SOURCE}'], cwd=ROOT)
report = json.loads(raw)
bad = []
unsupported = final_only = claimed = 0
for cell in report['cells']:
    for policy, row in cell['policies'].items():
        for logger, values in row['loggers'].items():
            times = values['unsupported_at_opportunities']
            if not times:
                continue
            unsupported += 1
            is_final_only = all(t == cell['K'] for t in times)
            final_only += is_final_only
            claims_final_only = values['status']['cost'].startswith('identified')
            claimed += claims_final_only
            if claims_final_only != is_final_only:
                bad.append(dict(K=cell['K'], effect=cell['action_effect'], feedback=cell['feedback'],
                                policy=policy, logger=logger, unsupported_times=times))
assert unsupported == 120 and final_only == 12 and claimed == 72 and len(bad) == 60
print(json.dumps(dict(reviewed_commit=REF, source=SOURCE, source_sha256=hashlib.sha256(raw).hexdigest(),
                     verdict='repair required: max(times)==K does not imply all times equal K',
                     unsupported_rows=unsupported, claimed_final_only=claimed, actual_final_only=final_only,
                     incorrect_labels=len(bad), counterexamples=bad,
                     scope='Label logic and archived unsupported times; not independent IPW reconstruction'), indent=2))
