#!/usr/bin/env python3
"""Audit immutable qualification records against the pinned Parquet rows (requires pyarrow).
No benchmark code, evaluator, container, or model execution. Input is the already downloaded dataset.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import subprocess
import pyarrow
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '600e143d635ec5c5ed833c0a6a6c8fecfa17f7f4'
DATA = 'work/benchmark_inputs/swebench_verified_c104f840/test-00000-of-00001.parquet'
DATA_SHA = 'a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd'
CHECKS = 0
SOURCES = {}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def check(ok, label):
    global CHECKS
    if not ok:
        raise AssertionError(label)
    CHECKS += 1


def blob(path):
    raw = subprocess.run(['git', 'show', f'{COMMIT}:{path}'], cwd=ROOT,
                         capture_output=True, check=True).stdout
    SOURCES[path] = sha(raw)
    return raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    check(sha((ROOT / DATA).read_bytes()) == DATA_SHA, 'pinned dataset bytes')
    rows = {r['instance_id']: r for r in pq.read_table(ROOT / DATA).to_pylist()}
    manifest = json.loads(blob('configs/v2_runtime_smoke_expansion_20260922.json'))
    m01raw = blob(manifest['source'])
    check(sha(m01raw) == manifest['source_sha256'], 'M01 pin')
    m01 = {r['instance_id']: r for r in map(json.loads, m01raw.splitlines())}
    adapter_sha = sha(blob('experiments/v2_adapter/control_adapter.py'))
    tasks = ['matplotlib__matplotlib-13989', 'mwaskom__seaborn-3069', 'psf__requests-1142',
             'pydata__xarray-2905', 'pylint-dev__pylint-4551', 'pytest-dev__pytest-10051',
             'scikit-learn__scikit-learn-10297']
    evidence = {}
    for iid in tasks:
        row = rows[iid]
        check(sha(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()) == m01[iid]['content_sha256'], iid + ': row pin')
        f2p, p2p = (json.loads(row[k]) for k in ['FAIL_TO_PASS', 'PASS_TO_PASS'])
        check(len(set(f2p + p2p)) == len(f2p + p2p), iid + ': unique disjoint required parser identities')
        prefix = 'results/v2_adapter/qualification_20260922/' + iid
        sraw = blob(prefix + '/summary.json')
        s = json.loads(sraw)
        check(s['required_tests'] == dict(fail_to_pass=len(f2p), pass_to_pass=len(p2p)), iid + ': denominators')
        check(s['finished_utc'] > s['started_utc'], iid + ': terminal times')
        check(s['platform']['evaluator_commit'] == 'f7bbbb2ccdf479001d6467c9e34af59e44a840f9', iid + ': evaluator')
        parsed, logs, counts = {}, {}, {}
        for key, stem in [('stock', 'stock_gold'), ('adapter_reference', 'adapter_reference_attempt1'),
                          ('adapter_no_change', 'adapter_no_change_attempt1')]:
            raw = blob(prefix + '/' + stem + '_test_output.txt')
            text = logs[key] = raw.decode()
            check('>>>>> Start Test Output' in text and '>>>>> End Test Output' in text, iid + key + ': markers')
            # Match printed status lines independently; preserve the pinned dataset's tokenized identities.
            smap = {m[2]: m[1] for m in re.finditer(r'^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\s+(\S+)', text, re.M)}
            parsed[key] = {t: smap.get(t) for t in f2p + p2p}
            counts[key] = {kind: dict(collections.Counter(smap.get(t, 'MISSING') for t in ids))
                           for kind, ids in [('F2P', f2p), ('P2P', p2p)]}
            if key != 'stock':
                a = s[key]
                check(len(a['attempts']) == 1 and a['attempts'][0]['completion_ok'], iid + key + ': single completed attempt')
                check(sha(raw) == a['attempts'][0]['log_sha256'], iid + key + ': log hash')
                check(a['image_digests'] == s['image_digests'], iid + key + ': image identity')
                check(a['eval_script_sha256'] == m01[iid]['eval_script_sha256'], iid + key + ': script pin')
                check(a['adapter_source_sha256'] == adapter_sha, iid + key + ': adapter pin')
                check(a['patch_sha256'] == (sha(row['patch'].encode()) if key == 'adapter_reference' else None), iid + key + ': prediction identity')
                for t, value in parsed[key].items():
                    check(value == a['attempts'][0]['per_test_status'].get(t), iid + key + ': ' + t)
        check(parsed['stock'] == parsed['adapter_reference'], iid + ': stock/reference required agreement')
        check(set(parsed['stock'].values()) == {'PASSED'}, iid + ': reference required pass')
        nc = parsed['adapter_no_change']
        qualified = all(nc.get(t) == 'PASSED' for t in p2p) and all(nc.get(t) in ['PASSED', 'FAILED'] for t in f2p) and any(nc.get(t) == 'FAILED' for t in f2p)
        check(qualified == s['qualified'], iid + ': independently reconstructed qualification')
        evidence[iid] = dict(summary_sha256=sha(sraw), required_counts=counts, qualified=qualified,
                             eval_script_sha256=m01[iid]['eval_script_sha256'], image_digests=s['image_digests'])
        if iid.startswith('pylint'):
            check('collected 0 items / 1 error' in logs['adapter_no_change'], 'pylint: collection failed')
            check("cannot import name 'get_annotation'" in logs['adapter_no_change'], 'pylint: missing symbol')
            check('+from pylint.pyreverse.utils import get_annotation, get_visibility, infer_node' in row['test_patch'], 'pylint: test patch import')
            check('+def get_annotation(' in row['patch'] and '+def infer_node(' in row['patch'], 'pylint: reference introduces API')
            full_cases = re.findall(r'^PASSED (.+)$', logs['stock'], re.M)
            check(len(full_cases) == len(set(full_cases)) == 18, 'pylint: 18 distinct printed passed cases')
            check(len({t.split()[0] for t in full_cases}) == 10, 'pylint: collapse to 10 parser identities')
            evidence[iid]['diagnosis'] = 'Patched tests require new API absent at baseline; collection error, not ten observed per-test failures. Empty P2P; 18 passing reference cases collapse to 10 declared parser identities.'
    result = dict(reviewed_commit=COMMIT, scope='Independent saved-log and pinned-row audit; no runtime rerun',
                  dependency=dict(pyarrow=pyarrow.__version__), dataset=dict(path=DATA, sha256=DATA_SHA),
                  checks=CHECKS, evidence=evidence, source_sha256=SOURCES)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(checks=CHECKS, sources=len(SOURCES), tasks=len(tasks), qualified=sum(x['qualified'] for x in evidence.values()))))


if __name__ == '__main__':
    main()
