"""DTR-REQ-002 block 1: descriptive exposure counts for the binding defect (finding 98895fe) and for command repetition,
computed from the COMPLETE committed block-1 trajectories/ledgers. Counts only; no interpretation or re-grading.

Definitions (fixed here, before being computed):
  * long observation: a tool-output message whose text exceeds 10,000 characters. The pinned default.yaml observation
    template (not applied in block 1) would have shown only a head/tail excerpt of such an output.
  * a context exit "follows a long observation" if any long observation precedes the failing call in that episode
  * repeated command: an action string identical to an earlier action in the same episode; distinct_commands counts
    unique action strings; max_repeat is the highest count of any single action string
  * prompt tokens at the last answered call come from the attempt ledger
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'results/v2_agent/pilot_20260922'
LIMIT = 10000


def episode(d):
    ep = json.loads((d / 'episode.json').read_text())
    msgs = json.loads((d / 'trajectory.json').read_text()).get('messages', [])
    ledger = [json.loads(l) for l in (d / 'attempts.jsonl').read_text().splitlines() if l.strip()]
    obs = [m for m in msgs if m.get('role') == 'user' and isinstance(m.get('extra'), dict) and 'returncode' in m['extra']]
    lengths = [len(str(m.get('content') or '')) for m in obs]
    cmds = [a.get('command', '') for m in msgs if m.get('role') == 'assistant' for a in ((m.get('extra') or {}).get('actions') or [])]
    counts = {}
    for c in cmds:
        counts[c] = counts.get(c, 0) + 1
    ok = [a for a in ledger if a.get('ok') is True]
    return dict(instance_id=ep['instance_id'], backend=ep['backend'], run_id=ep['run_id'], exit_status=ep['exit_status'],
                observations=len(obs), long_observations=sum(n > LIMIT for n in lengths), max_observation_chars=max(lengths, default=0),
                context_exit_after_long_observation=(ep['exit_status'] == 'ContextWindowExceededError' and any(n > LIMIT for n in lengths)),
                commands=len(cmds), distinct_commands=len(counts), repeated_commands=len(cmds) - len(counts),
                max_repeat=max(counts.values(), default=0),
                last_answered_prompt_tokens=ok[-1].get('prompt_tokens') if ok else None)


def main():
    rows = [episode(d) for d in sorted(OUT.iterdir()) if d.is_dir() and (d / 'episode.json').exists()]
    assert len(rows) == 16, len(rows)
    agg = {}
    for be in ('small', 'large'):
        r = [x for x in rows if x['backend'] == be]
        agg[be] = dict(episodes=len(r), episodes_with_long_observation=sum(x['long_observations'] > 0 for x in r),
                       long_observations=sum(x['long_observations'] for x in r),
                       context_exits=sum(x['exit_status'] == 'ContextWindowExceededError' for x in r),
                       context_exits_after_long_observation=sum(x['context_exit_after_long_observation'] for x in r),
                       commands=sum(x['commands'] for x in r), repeated_commands=sum(x['repeated_commands'] for x in r),
                       episodes_with_a_command_repeated_5_or_more=sum(x['max_repeat'] >= 5 for x in r))
    rec = dict(request='DTR-REQ-002', artifact='block 1 (harness binding before fix 86a0010)', definitions=__doc__.split('Definitions')[1].strip(),
               by_backend=agg, episodes=rows, scope='descriptive counts from committed records; no model call, no re-grading, no interpretation')
    dst = OUT / 'block1_harness_exposure.json'
    with open(dst, 'x') as fh:
        fh.write(json.dumps(rec, indent=1) + '\n')
    print(json.dumps(agg, indent=1))


if __name__ == '__main__':
    main()
