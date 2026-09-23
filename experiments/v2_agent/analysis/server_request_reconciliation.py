"""Retrospective check (DTR-REQ-005 transport finding): did hidden SDK retry layers or redirects add wire sends to the two
completed pilot cohorts? The frozen drivers log one attempts.jsonl record per tenacity-level (L0) attempt, not per HTTP send.
The committed llama-server logs are server-side evidence: the pinned server writes one `launch_slot_` line per completion
request it processes, including requests it then rejects for context size (`send_error ... exceeds the available context`).
Expected if no hidden sends occurred: launch_slot lines == ledger answered + ledger failed + non-task preflight probes.
Read-only over committed records; no model, server or container.
"""
import glob, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COHORTS = ('pilot_20260922', 'pilot_20260922_yaml_v1')


def cohort(name):
    base = ROOT / 'results/v2_agent' / name
    logs = sorted(base.glob('server_*.log'))
    text = [p.read_text() for p in logs]
    slots = sum(len(re.findall(r'launch_slot_:', t)) for t in text)
    ctx = sum(len(re.findall(r'send_error: .*exceeds the available context', t)) for t in text)
    answered = failed = 0
    for a in sorted(base.glob('*/attempts.jsonl')):
        for line in a.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get('event') == 'start':
                continue
            answered += r.get('ok') is True
            failed += r.get('ok') is False
    probes = sum(len(json.loads(p.read_text()).get('probes', {})) for p in sorted(base.glob('preflight_*.json')))
    expected = answered + failed + probes
    return dict(cohort=name, server_logs=len(logs), server_launch_slot_lines=slots, server_context_rejections=ctx,
                ledger_answered=answered, ledger_failed=failed, preflight_probes=probes,
                expected_if_no_hidden_sends=expected, unexplained_server_requests=slots - expected,
                ledger_failed_equals_server_context_rejections=failed == ctx)


def main():
    rows = [cohort(c) for c in COHORTS]
    rec = dict(request='DTR-REQ-005', kind='retrospective server-side reconciliation of wire sends (read-only)',
               method=__doc__.strip(), cohorts=rows,
               conclusion=('No unexplained server-processed requests in either cohort' if all(r['unexplained_server_requests'] == 0 for r in rows)
                           else 'UNEXPLAINED server-processed requests present'),
               limits=['Counts requests the server processed; a send refused or lost before reaching the server would not appear.',
                       'Relies on the pinned llama-server logging exactly one launch_slot_ per processed completion request; the two cohorts\' 5 context rejections each show one launch_slot_ followed by one send_error, consistent with that.',
                       'Covers only these two completed cohorts; it does not bound future runs, which the cue-v1 capture now counts per send.'])
    out = ROOT / 'results/v2_agent/analysis_20260922/server_request_reconciliation_20260923.json'
    with open(out, 'x') as fh:
        fh.write(json.dumps(rec, indent=1) + '\n')
    print(json.dumps([{k: r[k] for k in ('cohort', 'server_launch_slot_lines', 'expected_if_no_hidden_sends', 'unexplained_server_requests')} for r in rows]))


if __name__ == '__main__':
    main()
