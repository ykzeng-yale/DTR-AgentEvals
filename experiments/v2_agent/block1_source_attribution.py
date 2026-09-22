"""Correct saved block-1 attribution without recreating worker filesystem evidence.

Reads the immutable worker report and published episode artifacts only. Worker-reported
stdout-file birth times precede Popen in the pinned runner; they are not observed process
execution times. Run-ID timestamps likewise describe recorded naming, not interpreter reads.
The output is additive and write-once; neither original attribution nor episodes are changed.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'results/v2_agent/pilot_20260922'
SOURCE = OUT / 'block1_source_attribution.json'
CORRECTED = OUT / 'block1_source_attribution_correction.json'
NEW_KEYS = ('known_prompt_tokens', 'known_completion_tokens', 'container_cleanup', 'cleanup_error', 'incomplete_attempt_results')
NEW_FILES = ('container_ownership.json', 'container_cleanup.json', 'call9_history.json')
SOURCE_PINS = {
    '11a7344': {'pilot_episode.py': '780c945aa0c5254b34540bde3e83d50a4f4aef3e2a9558acaf780e15e3c6faee',
                'pilot_runner.py': 'ecd84068e111edd4dad758314cacf179d324ca2a716feee8c9b73598b340c02f'},
    'a64d81e': {'pilot_episode.py': 'cabcaae90da863fcbac107df6514198c4e8d5530cc5f77f97267650d8a286935'}
}


def run_id_timestamp(run_id):
    """The final double-underscore segment holds timestamp-randomsuffix, not the stage label."""
    match = re.fullmatch(r'(\d{8}T\d{6}Z)-[0-9a-f]+', run_id.rsplit('__', 1)[-1])
    if match is None:
        raise ValueError('run ID lacks a final timestamp-randomsuffix segment: ' + run_id)
    stamp = match.group(1)
    utc = dt.datetime.strptime(stamp, '%Y%m%dT%H%M%SZ').strftime('%Y-%m-%dT%H:%M:%SZ')
    return stamp, utc


def inspect_archive(directory):
    episode = json.loads((directory / 'episode.json').read_text())
    ledger = [json.loads(line) for line in (directory / 'attempts.jsonl').read_text().splitlines() if line.strip()]
    grade = json.loads((directory / 'grade.json').read_text())
    patch_sha = hashlib.sha256((directory / 'submission.diff').read_bytes()).hexdigest()
    keys = [key for key in NEW_KEYS if key in episode]
    files = [name for name in NEW_FILES if (directory / name).exists()]
    event = any('event' in record for record in ledger)
    return dict(instance_id=episode['instance_id'], backend=episode['backend'], ledger_records=len(ledger),
                ledger_has_event_key=event, episode_has_a64d81e_only_keys=keys, a64d81e_only_files_present=files,
                consistent_with_11a7344_child_schema=not event and not keys and not files,
                episode_run_id_matches=episode.get('run_id') == directory.name,
                submission_hash_matches=episode.get('submission_sha256') == patch_sha,
                grade_identity_matches=(grade.get('episode_run_id') == directory.name and
                                        grade.get('submission_sha256') == patch_sha and
                                        grade.get('instance_id') == episode['instance_id'] and
                                        grade.get('backend') == episode['backend']))


def correct_saved_attribution(saved, archive, source_sha256):
    """Recheck published schemas; keep unavailable raw/worker filesystem evidence explicitly reported."""
    archive = Path(archive)
    rows = saved['episodes']
    run_ids = [row['run_id'] for row in rows]
    actual = {d.name for d in archive.iterdir() if d.is_dir() and (d / 'episode.json').exists()}
    if len(run_ids) != len(set(run_ids)) or set(run_ids) != actual:
        raise ValueError('saved attribution episode IDs do not match the published terminal archive')
    interval = saved['replacement_interval_utc']
    corrected = []
    for row in rows:
        run_id = row['run_id']
        stamp, utc = run_id_timestamp(run_id)
        birth = row.get('spawn_utc_runner_stdout_birth')
        observed = inspect_archive(archive / run_id)
        if any(row.get(key) != observed[key] for key in ('instance_id', 'backend', 'ledger_records', 'ledger_has_event_key')):
            raise ValueError('saved attribution disagrees with published episode: ' + run_id)
        corrected.append(dict(run_id=run_id, run_id_timestamp=stamp, run_id_timestamp_utc=utc,
                              run_id_timestamp_inside_reported_replacement_interval=interval[0] <= utc <= interval[1],
                              worker_reported_stdout_file_birth_utc=birth,
                              worker_reported_stdout_file_birth_inside_interval=None if birth is None else interval[0] <= birth <= interval[1],
                              **observed))
    # The original field was a set complement, not a comparison with raw files.
    unlisted = saved['identity_binding']['published_equals_raw']
    raw_claims = [name for name in unlisted if Path(name).parent.name in actual and
                  Path(name).name in ('episode.json', 'attempts.jsonl', 'submission.diff', 'grade.json')]
    return dict(request='DTR-REQ-002', kind='additive retrospective correction of block-1 source-attribution evidence',
                supersedes_claims_in='block1_source_attribution.json', original_attribution_sha256=source_sha256,
                source_pins_inspected=SOURCE_PINS, worker_reported_replacement_interval_utc=interval,
                episodes=corrected,
                all_16_consistent_with_11a7344_child_schema=len(corrected) == 16 and all(r['consistent_with_11a7344_child_schema'] for r in corrected),
                run_ids_timestamped_inside_reported_interval=[r['run_id'] for r in corrected if r['run_id_timestamp_inside_reported_replacement_interval']],
                worker_reported_stdout_births_inside_interval=[r['run_id'] for r in corrected if r['worker_reported_stdout_file_birth_inside_interval']],
                evidence_boundary=dict(
                    published_archive='Episode IDs, legacy schemas, and local episode/submission/grade identity fields are independently inspectable.',
                    timestamps='Run-ID timestamps are recorded naming times. Stdout-file birth times and replacement interval are worker-reported, not independently verified here. The pinned runner creates stdout before Popen; neither timestamp establishes when the interpreter read the child source.',
                    source_inference='Conditional on the pinned 11a7344 runner launch arguments and unaltered output artifacts, the exact a64d81e child cannot explain these records: required --episode-deadline/--block-deadline arguments are absent, so argparse exits before its episode output. This supports legacy-schema consistency, not exact executed-byte attribution; a third or modified source is not excluded.',
                    raw_identity='Raw worker-local files were not available for independent comparison. Absence from a sanitization manifest does not prove raw/published equality; later derived reports are not raw episode artifacts.'),
                identity_binding=dict(
                    files_not_listed_for_sanitization=unlisted,
                    worker_reported_unchanged_episode_artifact_paths=raw_claims,
                    worker_reported_sanitized_file_hashes=saved['identity_binding']['published_differs_from_raw'],
                    raw_bytes_independently_compared=False, sanitization_transform_independently_verified=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-attribution', type=Path, default=SOURCE)
    parser.add_argument('--archive', type=Path, default=OUT)
    parser.add_argument('--out', type=Path, default=CORRECTED)
    args = parser.parse_args(argv)
    if args.out.resolve() == args.source_attribution.resolve():
        raise ValueError('correction must not overwrite the source attribution')
    raw = args.source_attribution.read_bytes()
    corrected = correct_saved_attribution(json.loads(raw), args.archive, hashlib.sha256(raw).hexdigest())
    with args.out.open('x') as fh:
        fh.write(json.dumps(corrected, indent=1) + '\n')
    print(json.dumps(dict(episodes=len(corrected['episodes']),
                         all_16_consistent_with_11a7344_child_schema=corrected['all_16_consistent_with_11a7344_child_schema'])))


if __name__ == '__main__':
    main()
