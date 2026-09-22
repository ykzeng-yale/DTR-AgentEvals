"""DTR-REQ-002 block 1: per-episode execution-source evidence for the disclosed child-script replacement interval
(05:33:50Z-05:34:13Z, pilot_episode.py briefly replaced on disk under the live 11a7344 runner), plus the raw/published
identity binding of the sanitized files (lead 043bfd9 requests). Evidence only; nothing is re-run or rewritten.

Per episode:
  * spawn time: filesystem birth time of runner_stdout.txt (created by the runner immediately before Popen) and the
    run-ID timestamp
  * schema markers that distinguish the two child-script versions:
      - 11a7344 child (SHA-256 780c945a...): attempts.jsonl has one completed-attempt record per line, NO 'event' key;
        episode.json has no known_prompt_tokens/container_cleanup/cleanup_error/incomplete_attempt_results keys;
        no container_ownership.json / container_cleanup.json / call9_history.json files
      - a64d81e child (SHA-256 cabcaae9...): requires --episode-deadline/--block-deadline, which the 11a7344 runner
        never passes (argparse would exit 2 before any episode record), and writes start/result 'event' records,
        the extra episode keys and the extra files above
"""
import hashlib, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'results/v2_agent/pilot_20260922'
NEW_KEYS = ('known_prompt_tokens', 'known_completion_tokens', 'container_cleanup', 'cleanup_error', 'incomplete_attempt_results', 'yaml_binding')
NEW_FILES = ('container_ownership.json', 'container_cleanup.json', 'call9_history.json')
REPLACED = ('2026-09-22T05:33:50Z', '2026-09-22T05:34:13Z')


def birth_utc(p):
    out = subprocess.run(['stat', '-f', '%B', str(p)], capture_output=True, text=True, check=True).stdout.strip()
    import time
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(int(out)))


def main():
    rows = []
    for d in sorted(x for x in OUT.iterdir() if x.is_dir() and (x / 'episode.json').exists()):
        ep = json.loads((d / 'episode.json').read_text())
        ledger = [json.loads(l) for l in (d / 'attempts.jsonl').read_text().splitlines() if l.strip()]
        spawn = birth_utc(d / 'runner_stdout.txt')
        rows.append(dict(run_id=d.name, instance_id=ep['instance_id'], backend=ep['backend'], spawn_utc_runner_stdout_birth=spawn,
                         run_id_timestamp=d.name.split('__')[3][:16],
                         spawned_inside_replacement_interval=REPLACED[0] <= spawn <= REPLACED[1],
                         ledger_records=len(ledger), ledger_has_event_key=any('event' in r for r in ledger),
                         episode_has_a64d81e_only_keys=[k for k in NEW_KEYS if k in ep],
                         a64d81e_only_files_present=[f for f in NEW_FILES if (d / f).exists()],
                         consistent_with_11a7344_child=(not any('event' in r for r in ledger) and not any(k in ep for k in NEW_KEYS)
                                                        and not any((d / f).exists() for f in NEW_FILES))))
    raw = OUT / 'sanitization_block1.json'
    man = json.loads(raw.read_text())
    unchanged = sorted({str(p.relative_to(OUT)) for p in OUT.rglob('*') if p.is_file()} - {f['file'] for f in man['files']}
                       - {'sanitization_block1.json', 'block1_source_attribution.json'})
    rec = dict(request='DTR-REQ-002', kind='block-1 execution-source evidence and raw/published identity binding (evidence only)',
               replacement_interval_utc=REPLACED,
               child_scripts=dict(block1_11a7344='780c945aa0c5254b (SHA-256 prefix)', a64d81e='cabcaae90da863fc (SHA-256 prefix)'),
               runner_11a7344_passes_deadline_args=False,
               episodes=rows, all_16_consistent_with_11a7344_child=len(rows) == 16 and all(r['consistent_with_11a7344_child'] for r in rows),
               episodes_spawned_inside_interval=[r['run_id'] for r in rows if r['spawned_inside_replacement_interval']],
               limitation='Birth times and output schema are file-system/record evidence; they do not hash the bytes the interpreter '
                          'read. They exclude the a64d81e child for every episode (that child cannot run under the 11a7344 runner '
                          'arguments and would leave different records) but cannot exclude a third, unrecorded script.',
               identity_binding=dict(
                   published_equals_raw=unchanged,
                   published_differs_from_raw={f['file']: dict(raw_sha256=f['raw_sha256'], published_sha256=f['published_sha256']) for f in man['files']},
                   bindings=('episode.json submission_sha256 binds submission.diff bytes; grade.json binds episode run_id and submission_sha256; '
                             'attempts.jsonl, episode.json, submission.diff and grade.json are byte-identical raw vs published. '
                             'trajectory.json, runner_stdout.txt and the 11 server logs differ ONLY by the home-directory prefix -> "~"; '
                             'no committed identity hashes those files, so their raw hashes are the manifest raw_sha256 values and the raw '
                             'bytes stay worker-local under work/runs/pilot_20260922/raw_block1_prepublication.')))
    with open(OUT / 'block1_source_attribution.json', 'x') as fh:
        fh.write(json.dumps(rec, indent=1) + '\n')
    print(rec['all_16_consistent_with_11a7344_child'], rec['episodes_spawned_inside_interval'], len(unchanged), 'unchanged files')


if __name__ == '__main__':
    main()
