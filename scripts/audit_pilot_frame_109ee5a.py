#!/usr/bin/env python3
"""Immutable saved-record/hash and independent pilot-selection audit.
No runtime, model, evaluator, or container calls. Local dataset must already exist.
Works from either work/ or scripts/. --output writes the resulting audit JSON.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '109ee5aa5ea52c63a7e710960b38b43954373e86'
N = 0
FIRST_PUBLICATION_CHECKS = 0
SOURCES = {}
FIRST_PUBLICATION = {}


def blob(path, commit=COMMIT):
    data = subprocess.run(['git', 'show', commit + ':' + path], cwd=ROOT,
                          check=True, capture_output=True).stdout
    if commit == COMMIT:
        SOURCES[path] = sha(data)
    return data


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def check(condition, label):
    global N
    if not condition:
        raise AssertionError(label)
    N += 1


def main():
    global FIRST_PUBLICATION_CHECKS
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    frame = json.loads(blob('results/v2_agent/pilot_frame_20260922.json'))
    specraw = blob(frame['spec']); spec = json.loads(specraw)
    mraw = blob(frame['qualification_manifest']); man = json.loads(mraw)
    lraw = blob(frame['legacy_hash_manifest']); legacy = json.loads(lraw)
    m01raw = blob(man['source'])
    m01 = {v['instance_id']: v for v in map(json.loads, m01raw.splitlines())}
    expected = dict(manifest_sha256=sha(mraw), source_sha256=sha(m01raw),
                    dataset_sha256='a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd',
                    evaluator_commit='f7bbbb2ccdf479001d6467c9e34af59e44a840f9')
    check(frame['spec_sha256'] == sha(specraw), 'spec SHA')
    check(frame['legacy_hash_manifest_sha256'] == sha(lraw), 'legacy SHA')
    check(man['source_sha256'] == sha(m01raw), 'M01 SHA')
    check(frame['expected_identity'] == legacy['expected_identity'] == expected, 'full expected identities')
    dataset = ROOT / 'work/benchmark_inputs/swebench_verified_c104f840/test-00000-of-00001.parquet'
    check(sha(dataset.read_bytes()) == expected['dataset_sha256'], 'dataset SHA')
    ids = [t['instance_id'] for t in man['tasks']]
    ft = frame['frame']['tasks']
    by = {t['instance_id']: t for t in ft}
    old = {t['instance_id']: t for t in legacy['records']}
    check(len(ids) == len(set(ids)) == 12, '12 unique manifest IDs')
    check([t['instance_id'] for t in ft] == ids, 'entire original frame exactly preserved')
    check(len(old) == 11 and set(old) == set(ids) - {'pallets__flask-5014'}, '11 legacy originals plus reused Flask')
    for t in ft:
        iid = t['instance_id']; raw = blob(t['record']); s = json.loads(raw)
        expected_path = ('results/v2_adapter/smoke_flask_20260922/summary.json' if iid == 'pallets__flask-5014'
                         else 'results/v2_adapter/qualification_20260922/' + iid + '/summary.json')
        check(t['record'] == expected_path, iid + ': original flat record')
        check(t['record_sha256'] == sha(raw), iid + ': record SHA')
        check(t['instance_image'] == s['image_digests']['instance'], iid + ': instance pin')
        check(t['eval_script_sha256'] == m01[iid]['eval_script_sha256'], iid + ': M01 script')
        check(t['qualified'] == all(s['acceptance'].values()) == s.get('qualified', s.get('smoke_check_passed')), iid + ': verdict')
        check(t['failed_acceptance'] == [k for k, v in s['acceptance'].items() if not v], iid + ': failed acceptance')
        if iid in old:
            check(old[iid]['sha256'] == sha(raw), iid + ': legacy bound SHA')
            check(old[iid]['qualified'] == t['qualified'] and old[iid]['terminal'] == 'verdict', iid + ': terminal verdict')
            check(old[iid]['summary'] == iid + '/summary.json', iid + ': legacy original path')
            check(bool(s['finished_utc']) and s['platform']['evaluator_commit'] == expected['evaluator_commit'], iid + ': terminal/evaluator')
        for mode in ['adapter_reference', 'adapter_no_change']:
            a = s[mode]
            check(a['image_digests'] == s['image_digests'], iid + ': ' + mode + ' image relation')
            check(a['eval_script_sha256'] == t['eval_script_sha256'], iid + ': ' + mode + ' evalscript')
            check(a['adapter_source_sha256'] == sha(blob('experiments/v2_adapter/control_adapter.py')), iid + ': adapter source')
            base = expected_path.rsplit('/', 1)[0]
            log = base + ('/logs/' if iid == 'pallets__flask-5014' else '/') + mode + '_attempt1_test_output.txt'
            check(sha(blob(log)) == a['attempts'][0]['log_sha256'], iid + ': ' + mode + ' logSHA')
    qualified = [i for i in ids if by[i]['qualified']]
    eligible = [i for i in qualified if i != 'pallets__flask-5014']
    seed = spec['selection']['seed_label']
    rank = lambda i: sha((seed + '\n' + i).encode())
    ordered = sorted(eligible, key=lambda i: (rank(i), i))
    chosen = ordered[:min(8, len(ordered))]
    check(frame['frame']['qualified'] == len(qualified) == 10, '10 qualified')
    check(frame['frame']['diagnosed_unqualified'] == ['django__django-10097', 'pylint-dev__pylint-4551'], 'unfavorable preserved')
    check(frame['pilot']['K'] == len(eligible) == 9 and frame['pilot']['N'] == len(chosen) == 8, 'K9 N8')
    check([p['instance_id'] for p in frame['pilot']['tasks']] == chosen, 'exact salted selection')
    check(frame['pilot']['episodes_max'] == 2 * len(chosen) == 16, '16 episodes')
    check(frame['pilot']['ranked_eligible'] == [dict(instance_id=i, rank_sha256=rank(i), selected=i in chosen) for i in ordered], 'all9 ranks')
    for p in frame['pilot']['tasks']:
        iid = p['instance_id']; bit = int(sha((seed + '\n' + iid + '\norder').encode()), 16) & 1
        first = 'large' if bit else 'small'
        check(p['rank_sha256'] == rank(iid), iid + ': rank')
        check(p['first_backend'] == first and p['backend_order'] == [first, 'large' if first == 'small' else 'small'], iid + ': lowbitorder')
        check(p['record_sha256'] == by[iid]['record_sha256'], iid + ': bound record')
        check(p['instance_image'] == by[iid]['instance_image'] == p['local_image_id'] and p['local_image_matches_record'], iid + ': recorded local image consistency')
        check(p['local_image_tag'] == 'sweb.eval.x86_64.' + iid.lower() + ':latest', iid + ': recorded image tag')
    for t in ft:
        path = t['record']
        first = subprocess.run(['git', 'log', COMMIT, '--diff-filter=A', '--format=%H', '--', path], cwd=ROOT,
                               check=True, capture_output=True, text=True).stdout.strip().splitlines()[-1]
        digest = sha(blob(path, first))
        if digest != t['record_sha256']:
            raise AssertionError(path + ': original record differs from first-publication blob')
        FIRST_PUBLICATION_CHECKS += 1
        FIRST_PUBLICATION[path] = dict(commit=first, sha256=digest)
    full_commit = subprocess.run(['git', 'rev-parse', COMMIT], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    result = dict(reviewed_commit=full_commit, passed=True, assertion_count=N,
                  first_publication_hash_checks=FIRST_PUBLICATION_CHECKS,
                  total_checks=N + FIRST_PUBLICATION_CHECKS,
                  frame_size=len(ids), qualified=len(qualified), K=len(eligible), N=len(chosen),
                  selected=[dict(instance_id=p['instance_id'], first_backend=p['first_backend']) for p in frame['pilot']['tasks']],
                  omitted=ordered[8:], source_identity_matches=True, expected_identity=expected,
                  source_sha256=SOURCES, first_publication=FIRST_PUBLICATION,
                  scope='Immutable records, hashes, recorded image consistency and independent salted selection; no runtime inspection',
                  limitations=['Current local image availability is worker-reported; only recorded identity consistency is checked.',
                               'Freeze-before-model-outcome timing is worker-reported, not independently observed execution.',
                               'This validates the concrete frozen frame, not unresolved general grading/restart boundary handling.',
                               'No model/resource/shared-host launch conditions are waived by this frame audit.'])
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
    print(json.dumps({k: result[k] for k in ['reviewed_commit', 'passed', 'assertion_count', 'first_publication_hash_checks', 'total_checks', 'K', 'N']}))


if __name__ == '__main__':
    main()
