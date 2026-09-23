"""Independent deterministic audit of the published yaml-v1 cohort at 4927adc.

Reads immutable Git blobs, never imports the runner/reporter or contacts a model,
container, host process, network, or worker-local raw archive. Writes only an explicit
--out destination, exclusively. Run with --out - to reproduce JSON on stdout.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
COMMIT = '4927adc9fd28f2bea2a21a2751337f83b2e60dbf'
COHORT = 'results/v2_agent/pilot_20260922_yaml_v1'
AMENDMENT = 'configs/v2_fixed_backend_development_pilot_yaml_v1_20260922.json'
FRAME = 'results/v2_agent/pilot_frame_20260922.json'
CONVERSION = 'results/v2_agent/coder_conversion_20260922.json'
BASE = 'configs/v2_fixed_backend_development_pilot_20260922.json'
SOURCE_DIR = 'experiments/v2_agent'
SOURCES = ('pilot_episode.py', 'pilot_runner.py', 'pilot_cohort.py')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def audit():
    paths = [COHORT, AMENDMENT, FRAME, CONVERSION, BASE, *[SOURCE_DIR + '/' + name for name in SOURCES]]
    raw_tar = subprocess.check_output(['git', 'archive', COMMIT, '--', *paths], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(raw_tar)) as archive:
        blobs = {member.name: archive.extractfile(member).read() for member in archive.getmembers() if member.isfile()}
    consumed = {}
    def raw(path):
        value = blobs[path]
        consumed[path] = sha(value)
        return value
    def read(path):
        return json.loads(raw(path))
    frame, amendment, conversion = read(FRAME), read(AMENDMENT), read(CONVERSION)
    binding = read(COHORT + '/cohort_binding.json')
    block = read(COHORT + '/block_1.json')
    start = read(COHORT + '/block_1_start.json')
    worker_report = read(COHORT + '/report_yaml_v1_block1_final.json')
    manifest = read(COHORT + '/sanitization_yaml_v1_block1.json')
    checks = {}
    def check(name, value):
        checks[name] = bool(value)
    check('cohort_name', binding['cohort'] == block['cohort'] == 'yaml-v1')
    sources = {name: dict(expected=binding['sources'][name], observed_tracked_sha256=sha(raw(SOURCE_DIR + '/' + name)))
               for name in SOURCES}
    check('all_frozen_source_hashes', all(v['expected'] == v['observed_tracked_sha256'] for v in sources.values()))
    check('amendment_hash', binding['amendment_sha256'] == block['amendment_sha256'] == sha(raw(AMENDMENT)))
    for field, path in (('base_spec_sha256', BASE), ('frame_sha256', FRAME), ('conversion_record_sha256', CONVERSION)):
        check('amendment_' + field, amendment[field] == sha(raw(path)))
    check('block_input_and_source_pins', block['frame_sha256'] == sha(raw(FRAME)) and
          block['conversion_record_sha256'] == sha(raw(CONVERSION)) and
          block['runner_source_sha256'] == binding['sources']['pilot_runner.py'] and
          block['episode_source_sha256'] == binding['sources']['pilot_episode.py'])
    expected = [(t['instance_id'], backend) for t in sorted(frame['pilot']['tasks'], key=lambda t: t['position'])
                for backend in t['backend_order']]
    images = {t['instance_id']: t['instance_image'] for t in frame['pilot']['tasks']}
    episode_paths = sorted(path for path in blobs if path.startswith(COHORT + '/') and path.endswith('/episode.json'))
    check('sixteen_unique_assignments', len(expected) == len(set(expected)) == len(episode_paths) == 16)
    manifest_by_path = {item['file']: item for item in manifest['files']}
    check('59_unique_sanitized_entries', len(manifest_by_path) == len(manifest['files']) == 59)
    sanitized = [dict(file=item['file'], published_sha256=item['published_sha256'],
                      observed_sha256=sha(raw(COHORT + '/' + item['file'])),
                      worker_reported_raw_sha256=item['raw_sha256']) for item in manifest['files']]
    check('all_59_published_hashes', all(r['published_sha256'] == r['observed_sha256'] for r in sanitized))
    rows = []
    settings = dict(step_limit=24, cost_limit=0.0, wall_time_limit_seconds=1800, temperature=0.0,
                    max_tokens=1536, command_timeout_s=60, physical_attempts_per_call_max=2, request_timeout_s=900)
    for path in episode_paths:
        directory = path.rsplit('/', 1)[0]
        run_id = directory.rsplit('/', 1)[-1]
        episode = read(path)
        grade = read(directory + '/grade.json')
        patch = raw(directory + '/submission.diff')
        receipt = read(directory + '/effective_config.json')
        records = [json.loads(line) for line in raw(directory + '/attempts.jsonl').splitlines() if line.strip()]
        starts, results = {}, {}
        errors = []
        for record in records:
            event = record.get('event')
            key = (record.get('call'), record.get('attempt'))
            if event not in ('start', 'result') or any(type(n) is not int or n < 1 for n in key):
                errors.append('invalid event or call/attempt index')
                continue
            target = starts if event == 'start' else results
            if key in target:
                errors.append('duplicate ' + event)
            target[key] = record
        if set(starts) != set(results):
            errors.append('unmatched start/result keys')
        calls = sorted({call for call, _ in starts})
        if calls != list(range(1, episode['n_model_calls'] + 1)):
            errors.append('dispatched calls do not reproduce episode logical count')
        per_call = Counter(call for call, _ in starts)
        failures = sum(r.get('ok') is False for r in results.values())
        if any(r.get('ok') not in (True, False) for r in results.values()):
            errors.append('unknown physical result status')
        if any(key not in starts or r['t_start'] != starts[key]['t_start'] or r['t_end'] < r['t_start'] for key, r in results.items()):
            errors.append('result timestamp does not match start')
        if (len(starts) != episode['physical_requests'] or failures != episode['failed_attempts'] or
                max(per_call.values(), default=0) != episode['max_attempts_on_one_call']):
            errors.append('episode counters differ from ledger')
        usage = {}
        for metric in ('prompt_tokens', 'completion_tokens'):
            known = [r[metric] for r in results.values() if r.get('ok') is True and
                     type(r.get(metric)) in (int, float) and r[metric] >= 0]
            missing = len(starts) - len(known)
            usage[metric] = dict(known_subtotal=sum(known), missing_attempts=missing,
                                 full_total=sum(known) if missing == 0 else None)
            if episode.get('known_' + metric) != sum(known) or episode.get(metric) != usage[metric]['full_total']:
                errors.append('episode ' + metric + ' differs from ledger')
        patch_sha = sha(patch)
        identity = (episode['run_id'] == run_id and grade['episode_run_id'] == run_id and
                    episode['instance_id'] == grade['instance_id'] and episode['backend'] == grade['backend'] and
                    episode['submission_sha256'] == grade['submission_sha256'] == patch_sha and
                    episode['submission_bytes'] == len(patch) and episode['submission_empty'] == (not patch.strip()) and
                    episode['pins']['image_id'] == grade['image_id'] == images[episode['instance_id']])
        model = conversion['backends'][episode['backend']]['q4_k_m']
        model_match = (episode['served']['model_sha256'] == model['sha256'] and
                       episode['served']['model_file'] == Path(model['file']).name and
                       episode['served']['llama_cpp'] == conversion['llama_cpp']['commit'] and
                       episode['server']['n_ctx_per_slot'] == 16384 and episode['server']['total_slots'] == 1)
        limits_match = all(episode['settings'].get(k) == v for k, v in settings.items())
        limits_observed = len(calls) <= 24 and len(starts) <= 48 and max(per_call.values(), default=0) <= 2 and episode['wall_seconds'] <= 1800
        recorded_digest = receipt['effective_config_sha256']
        payload = {k: v for k, v in receipt.items() if k != 'effective_config_sha256'}
        computed_digest = sha(canonical(payload))
        entry = manifest_by_path[directory[len(COHORT) + 1:] + '/effective_config.json']
        constructor_match = all(isinstance(receipt['constructor_arguments'].get(section), dict) and
                                isinstance(receipt['resolved'].get(section), dict) and
                                all(receipt['resolved'][section].get(k) == v for k, v in receipt['constructor_arguments'][section].items())
                                for section in ('agent', 'model', 'environment'))
        receipt_metadata_match = (receipt['configuration_binding'] == episode['configuration_binding'] == 'yaml-v1' and
                                  receipt['episode_source_sha256'] == episode['episode_source_sha256'] == binding['sources']['pilot_episode.py'] and
                                  receipt['mini_swe_agent'] == episode['pins']['mini_swe_agent'] and
                                  receipt['default_yaml_sha256'] == episode['pins']['default_yaml_sha256'])
        runner_cleanup, container_cleanup = read(directory + '/runner_cleanup.json'), read(directory + '/container_cleanup.json')
        row = dict(run_id=run_id, instance_id=episode['instance_id'], backend=episode['backend'], exit_status=episode['exit_status'],
                   ledger_records=len(records), logical_calls=len(calls), physical_requests=len(starts), successful_physical_responses=len(starts)-failures,
                   failed_attempts=failures, max_attempts_per_call=max(per_call.values(), default=0), ledger_errors=errors,
                   usage=usage, wall_seconds=episode['wall_seconds'], patch_bytes=len(patch), submitted=episode['exit_status'] == 'Submitted',
                   patch_grade_episode_identity_matches=identity, grade_classification=grade['classification'],
                   grade_valid_reported=grade['grade_valid'], operational_resolved=grade['operational_resolved'],
                   algorithmic_correctness=grade['algorithmic_correctness'], evaluated=grade['evaluated'],
                   operational_zero_supported=not patch.strip() and grade['grade_valid'] is True and grade['classification'] == 'operational_zero' and
                                              grade['operational_resolved'] == 0 and grade['evaluated'] is False and grade['algorithmic_correctness'] == 'not_evaluated',
                   model_pin_matches=model_match, declared_settings_match=limits_match, observed_limits_within_caps=limits_observed,
                   call9_issued=any(call == 9 for call, _ in starts), call9_snapshot_present=directory + '/call9_history.json' in blobs,
                   configuration=dict(recorded_raw_payload_digest=recorded_digest, observed_published_payload_digest=computed_digest,
                                      published_payload_matches_recorded_raw_digest=computed_digest == recorded_digest,
                                      episode_embedded_digest_matches=episode['effective_config_sha256'] == recorded_digest,
                                      published_payload_matches_manifest=computed_digest == entry['published_payload_canonical_sha256'],
                                      manifest_recorded_digest_matches=recorded_digest == entry['recorded_effective_config_sha256'],
                                      constructor_resolved_subset_matches=constructor_match, source_and_pin_metadata_match=receipt_metadata_match,
                                      raw_digest_independently_reproduced=False),
                   runner_termination_reported=runner_cleanup.get('termination_confirmed'), container_stop_reported=container_cleanup.get('confirmed'))
        rows.append(row)
    rows.sort(key=lambda r: expected.index((r['instance_id'], r['backend'])))
    check('all_selected_ids_once', [(r['instance_id'], r['backend']) for r in rows] == expected)
    check('all_ledger_counters_reproduced', all(not r['ledger_errors'] for r in rows))
    for name, field in [('all_patch_grade_episode_identities', 'patch_grade_episode_identity_matches'),
                        ('all_operational_zeros_supported', 'operational_zero_supported'), ('all_model_pins', 'model_pin_matches'),
                        ('all_declared_settings', 'declared_settings_match'), ('all_observed_caps', 'observed_limits_within_caps')]:
        check(name, all(r[field] for r in rows))
    check('all_configuration_metadata_and_published_canonical_digests', all(
        all(r['configuration'][k] for k in ('episode_embedded_digest_matches', 'published_payload_matches_manifest',
                                            'manifest_recorded_digest_matches', 'constructor_resolved_subset_matches', 'source_and_pin_metadata_match'))
        for r in rows))
    check('frozen_block_assignment_order', [(r['instance_id'], r['backend']) for r in block['ran']] == expected)
    check('block_physical_total_matches', block['physical_requests_total'] == sum(r['physical_requests'] for r in rows))
    check('cohort_physical_request_cap', sum(r['physical_requests'] for r in rows) <= amendment['fixed_budget']['physical_requests_cohort_max'])
    check('published_worker_exit_counts_match', all(worker_report['backends'][backend]['exit_status'] ==
          dict(Counter(r['exit_status'] for r in rows if r['backend'] == backend)) for backend in ('small', 'large')))
    def summarize(selected):
        result = dict(assignments=len(selected), exit_counts=dict(Counter(r['exit_status'] for r in selected)),
                      logical_calls=sum(r['logical_calls'] for r in selected), physical_requests=sum(r['physical_requests'] for r in selected),
                      failed_attempts=sum(r['failed_attempts'] for r in selected),
                      submitted=sum(r['submitted'] for r in selected), nonempty_submitted_patches=sum(r['submitted'] and r['patch_bytes'] > 0 for r in selected),
                      operational_resolved=sum(r['operational_resolved'] for r in selected), evaluated=sum(r['evaluated'] for r in selected),
                      algorithmic_eligible_nonempty_submitted=sum(r['submitted'] and r['patch_bytes'] > 0 and r['patch_grade_episode_identity_matches'] for r in selected),
                      call9_issued=sum(r['call9_issued'] for r in selected),
                      wall_seconds_sum=sum(r['wall_seconds'] for r in selected))
        for metric in ('prompt_tokens', 'completion_tokens'):
            missing = sum(r['usage'][metric]['missing_attempts'] for r in selected)
            known = sum(r['usage'][metric]['known_subtotal'] for r in selected)
            result[metric] = dict(known_subtotal=known, missing_attempts=missing, full_total=known if missing == 0 else None)
        return result
    return dict(kind='independent deterministic retrospective audit of published DEVELOPMENT artifacts, not a new experiment',
                reviewed_commit=COMMIT, cohort='yaml-v1', audit_script_sha256=sha(Path(__file__).read_bytes()),
                checks=checks, failed_checks=[name for name, passed in checks.items() if not passed],
                source_and_amendment_binding=dict(sources=sources, amendment_sha256=sha(raw(AMENDMENT))),
                totals=summarize(rows), backends={b: summarize([r for r in rows if r['backend'] == b]) for b in ('small', 'large')},
                configuration_provenance=dict(
                    published_receipts=len(rows), raw_payload_digest_reproduced_from_published_bytes=sum(r['configuration']['published_payload_matches_recorded_raw_digest'] for r in rows),
                    published_payload_manifest_matches=sum(r['configuration']['published_payload_matches_manifest'] for r in rows),
                    worker_report_terminal_status_counts=worker_report['configuration_provenance']['terminal_status_counts'],
                    finding='All published effective receipts differ from their embedded raw-payload digest after reported path sanitization. Published file/payload hashes are reproducible; they do not attest raw bytes or establish that sanitization was the only change. The prepublication validated=16 claim is not independently reproducible from the published receipts alone.'),
                sanitization=dict(entries=len(sanitized), published_hash_matches=sum(r['published_sha256'] == r['observed_sha256'] for r in sanitized),
                                  raw_bytes_compared=False, transformation_independently_verified=False, files=sanitized),
                historical_release=dict(block_start_utc=block['block_start_utc'], block_end_utc=block['block_end_utc'], released_utc=block['released_utc'],
                                        block_hard_end_utc=block['block_hard_end_utc'], non_task_probe_requests_reported=block['non_task_probe_requests'],
                                        runner_terminations_reported=sum(r['runner_termination_reported'] is True for r in rows),
                                        container_stops_reported=sum(r['container_stop_reported'] is True for r in rows),
                                        current_host_process_state_checked=False, start_receipt_is_current_running_evidence=False),
                evidence_boundary=['Frozen Git bytes, published hash agreements, ledger arithmetic and identity linkage were independently recomputed.',
                                   'Worker-local raw receipts and sanitization transformations were not available and were not reconstructed or assumed.',
                                   'All 16 operational zeros are retained; no nonempty Submitted artifact exists, so algorithmic correctness was not evaluated.',
                                   'Task/backend totals are descriptive on the frozen exposed development frame, not a routing effect or population efficacy estimate.',
                                   'Known token subtotals omit unknown usage on two failed physical requests; they are not complete cost totals.',
                                   'Release records are historical reports. No live process, server, container or model was contacted.'],
                episodes=rows, input_file_sha256=dict(sorted(consumed.items())))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default='-')
    args = parser.parse_args()
    result = audit()
    output = json.dumps(result, indent=2) + '\n'
    if args.out == '-':
        print(output, end='')
    else:
        with Path(args.out).open('x') as handle:
            handle.write(output)
        print(json.dumps(dict(output=args.out, failed_checks=result['failed_checks'], totals=result['totals'],
                              configuration_provenance=result['configuration_provenance'])))
    if result['failed_checks']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
