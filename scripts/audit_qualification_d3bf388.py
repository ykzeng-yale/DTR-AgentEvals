#!/usr/bin/env python3
"""Saved-artifact checks only; no evaluator, container, or model execution."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
COMMIT = 'd3bf38877ca6cc188d038bc92bfbca08d8f39f72'
SOURCES = {}
CHECKS = 0


def check(ok, label):
    global CHECKS
    if not ok:
        raise AssertionError(label)
    CHECKS += 1


def blob(path):
    raw = subprocess.run(['git', 'show', f'{COMMIT}:{path}'], cwd=ROOT,
                         capture_output=True, check=True).stdout
    SOURCES[path] = hashlib.sha256(raw).hexdigest()
    return raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    m01 = {r['instance_id']: r for r in map(json.loads, blob(
        'results/v2_adapter/m01_c104f840_f7bbbb2/instances.jsonl').splitlines())}
    adapter_sha = hashlib.sha256(blob('experiments/v2_adapter/control_adapter.py')).hexdigest()
    evidence = {}
    for iid in ['astropy__astropy-12907', 'django__django-10097']:
        prefix = f'results/v2_adapter/qualification_20260922/{iid}'
        summary = json.loads(blob(prefix + '/summary.json'))
        check(summary['required_tests'] == {
            'fail_to_pass': m01[iid]['n_fail_to_pass'],
            'pass_to_pass': m01[iid]['n_pass_to_pass']}, iid + ': declared counts')
        logs = {}
        for mode in ['stock_gold', 'adapter_reference_attempt1', 'adapter_no_change_attempt1']:
            raw = blob(prefix + '/' + mode + '_test_output.txt')
            text = raw.decode()
            logs[mode] = text
            check('>>>>> Start Test Output' in text and '>>>>> End Test Output' in text,
                  iid + mode + ': output markers')
            if mode != 'stock_gold':
                rec = summary[mode.removesuffix('_attempt1')]
                check(len(rec['attempts']) == 1, iid + mode + ': one attempt')
                check(hashlib.sha256(raw).hexdigest() == rec['attempts'][0]['log_sha256'],
                      iid + mode + ': saved log hash')
                check(rec['image_digests'] == summary['image_digests'], iid + mode + ': image identity')
                check(rec['eval_script_sha256'] == m01[iid]['eval_script_sha256'], iid + mode + ': script pin')
                check(rec['adapter_source_sha256'] == adapter_sha, iid + mode + ': adapter pin')
                check(rec['attempts'][0]['completion_ok'], iid + mode + ': reported completion')
        if iid.startswith('astropy'):
            parsed = {}
            for mode, text in logs.items():
                statuses = dict((m[2], m[1]) for m in re.finditer(
                    r'^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS) (\S+)', text, re.M))
                check(len(statuses) == 15, mode + ': 15 raw test identities')
                if mode != 'stock_gold':
                    check(statuses == summary[mode.removesuffix('_attempt1')]['attempts'][0]['per_test_status'],
                          mode + ': raw map equals saved map')
                parsed[mode] = statuses
            check(parsed['stock_gold'] == parsed['adapter_reference_attempt1'], 'astropy: stock/reference raw agreement')
            check(set(parsed['stock_gold'].values()) == {'PASSED'}, 'astropy: reference all passes')
            check(collections.Counter(parsed['adapter_no_change_attempt1'].values()) == {'PASSED': 13, 'FAILED': 2},
                  'astropy: baseline contrast')
            check(all(summary['acceptance'].values()) and summary['qualified'], 'astropy: scoped qualification')
            evidence[iid] = dict(raw_status_counts={k: dict(collections.Counter(v.values())) for k, v in parsed.items()},
                                 qualified=True, scope='15 raw status identities independently reconstructed in each of three logs')
        else:
            errors = [k for k, v in summary['adapter_reference']['attempts'][0]['per_test_status'].items()
                      if 'generic_inline_admin' in k and v == 'ERROR']
            check(len(errors) == 5, 'django: five generic inline admin errors')
            templates = {}
            for mode, text in logs.items():
                for test in errors:
                    match = re.search(r'^ERROR: ' + re.escape(test) + r'\n-+\n(.*?)(?=^={5,}|\Z)', text, re.M | re.S)
                    check(match is not None, mode + ': traceback ' + test)
                    template = 'admin/delete_confirmation.html' if test.startswith('test_delete ') else 'admin/change_form.html'
                    templates[test] = template
                    check(template in match[1] and 'TemplateDoesNotExist' in match[1],
                          mode + ': template failure ' + test)
                    check('/site-packages/Django-2.2.' in match[1], mode + ': installed Django traceback')
            check(not summary['qualified'], 'django: failure retained')
            check(summary['stock']['required_status_counts'] == {'PASSED': 1865, 'ERROR': 5},
                  'django: inspected required status totals (not independently reparsed)')
            evidence[iid] = dict(qualified=False, raw_traceback_errors_verified=templates,
                required_status_counts_inspected=summary['stock']['required_status_counts'],
                scope='Five named template-error tracebacks verified in all three logs; full 1870-test required map is inspected, not independently reconstructed',
                diagnosis='Template lookup fails in installed Django for stock, reference and no-change. Missing packaged files versus loader/path mismatch, mutable dependency drift and translation effects are not isolated.')
    result = dict(reviewed_commit=COMMIT, scope='Deterministic retrospective saved-artifact audit; no runtime rerun',
                  checks=CHECKS, evidence=evidence, source_sha256=SOURCES)
    out = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(out)
    print(json.dumps(dict(checks=CHECKS, sources=len(SOURCES), tasks=list(evidence))))


if __name__ == '__main__':
    main()
