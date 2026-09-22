#!/usr/bin/env python3
"""Deterministic saved-record audit; no containers, inference, or new sampling.

Usage: python scripts/audit_smoke_075b2f0.py --output docs/audits/smoke_075b2f0.json
The program works from either scripts/ or ignored work/. It inspects immutable
Git blobs from the reviewed commit, not later mutable working-tree files.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

COMMIT = '075b2f03667f3a1ef0591ebb9e5a9063781e01ab'
ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'results/v2_adapter/smoke_flask_20260922'
COUNT = 0
SOURCES = {}


def check(condition, label):
    global COUNT
    if not condition:
        raise AssertionError(label)
    COUNT += 1


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(path):
    data = subprocess.run(['git', 'show', f'{COMMIT}:{path}'], cwd=ROOT,
                          check=True, capture_output=True).stdout
    SOURCES[path] = sha(data)
    return data


def git_fixture():
    """Reproduce loss from the committed runner's plain git diff command."""
    with tempfile.TemporaryDirectory(prefix='dtr-smoke-diff-audit-') as tmp:
        p = Path(tmp)
        def git(*args):
            return subprocess.run(['git', '-c', 'user.name=Yukang Zeng', '-c',
                                   'user.email=ykzeng2019@gmail.com', *args], cwd=p,
                                  check=True, capture_output=True, text=True,
                                  env={**os.environ, 'GIT_AUTHOR_NAME': 'Yukang Zeng',
                                       'GIT_AUTHOR_EMAIL': 'ykzeng2019@gmail.com',
                                       'GIT_COMMITTER_NAME': 'Yukang Zeng',
                                       'GIT_COMMITTER_EMAIL': 'ykzeng2019@gmail.com'}).stdout
        git('init', '-q')
        (p / 'tracked').write_text('baseline\n')
        git('add', 'tracked')
        git('commit', '-qm', 'base')
        base = git('rev-parse', 'HEAD').strip()
        (p / 'tracked').write_text('changed\n')
        git('add', 'tracked')
        (p / 'new').write_text('new\n')
        plain_staged = git('-c', 'core.fileMode=false', 'diff')
        base_staged = git('diff', base)
        check(plain_staged == '', 'plain diff silently omits staged change')
        check('+changed' in base_staged, 'base diff captures staged change')
        check('diff --git a/new b/new' not in base_staged,
              'base diff alone still omits untracked new file')
        git('add', 'new')
        git('commit', '-qm', 'agent commit')
        plain_committed = git('-c', 'core.fileMode=false', 'diff')
        base_committed = git('diff', base)
        check(plain_committed == '', 'plain diff silently omits committed edits')
        check('+changed' in base_committed and '+new' in base_committed,
              'base diff captures committed existing and new file edits')
        return dict(scope='Temporary local Git fixture; no benchmark/runtime execution',
                    plain_diff_after_staged_change_and_untracked_file_bytes=len(plain_staged.encode()),
                    base_diff_after_staged_change_bytes=len(base_staged.encode()),
                    base_diff_alone_includes_untracked_file=False,
                    plain_diff_after_agent_commit_bytes=len(plain_committed.encode()),
                    base_diff_after_agent_commit_bytes=len(base_committed.encode()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    summ = json.loads(blob(PREFIX + '/summary.json'))
    evidence = {}
    for name, key in [('stock_gold', 'stock'),
                      ('adapter_reference_attempt1', 'adapter_reference'),
                      ('adapter_no_change_attempt1', 'adapter_no_change')]:
        path = PREFIX + '/logs/' + name + '_test_output.txt'
        raw = blob(path)
        text = raw.decode()
        rec = summ[key] if key == 'stock' else summ[key]['attempts'][0]
        check(sha(raw) == rec['log_sha256'], name + ': raw log hash')
        parsed = {}
        for line in text.splitlines():
            match = re.match(r'^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS) (\S+)', line)
            if match:
                test, status = match[2], match[1]
                check(test not in parsed, name + ': unique status identity ' + test)
                parsed[test] = status
        stored = rec.get('required_status', rec.get('per_test_status'))
        check(set(parsed) == set(stored), name + ': complete test identity set')
        for test, status in stored.items():
            check(parsed[test] == status, name + ': test status ' + test)
        check('>>>>> Start Test Output' in text, name + ': start marker')
        check('>>>>> End Test Output' in text, name + ': end marker')
        evidence[name] = dict(log_sha256=sha(raw), parsed_tests=len(parsed),
                              status_counts=dict(collections.Counter(parsed.values())))
    check(sha(blob('experiments/v2_adapter/control_adapter.py')) ==
          summ['pins']['adapter_source_sha256'], 'adapter source hash')
    m01 = next(json.loads(line) for line in
               blob('results/v2_adapter/m01_c104f840_f7bbbb2/instances.jsonl').decode().splitlines()
               if json.loads(line)['instance_id'] == summ['instance_id'])
    check(m01['eval_script_sha256'] == summ['pins']['eval_script_sha256'], 'M01 script hash')
    check(summ['required_tests'] == dict(fail_to_pass=m01['n_fail_to_pass'],
                                       pass_to_pass=m01['n_pass_to_pass']), 'M01 required counts')
    ref, nc = summ['adapter_reference'], summ['adapter_no_change']
    sm = summ['stock']['required_status']
    rm, nm = ref['attempts'][0]['per_test_status'], nc['attempts'][0]['per_test_status']
    check(set(sm) == set(rm), 'stock/reference required identity set')
    for test in sm:
        check(sm[test] == rm[test], 'stock/reference status ' + test)
    check(set(nm) == set(sm), 'no-change required identity set')
    check([k for k, v in nm.items() if v != 'PASSED'] ==
          ['tests/test_blueprints.py::test_empty_name_not_allowed'], 'sole no-change failure')
    check(nc['attempts'][0]['patch_application'] == 'not_applicable' and
          not any(event[0] == 'apply_patch' for event in nc['runtime_events']),
          'no-change applies no prediction')
    check(len(ref['attempts']) == len(nc['attempts']) == 1, 'one attempt per adapter')
    check(ref['image_digests'] == nc['image_digests'] == summ['image_digests'], 'common recorded digests')
    for name, rec in [('reference', ref), ('no_change', nc)]:
        check(rec['runtime_events'][0][2] == summ['image_digests']['instance'], name + ': start image ID')
    fixture = git_fixture()
    result = dict(audit='smoke_flask_075b2f0_saved_record_audit', reviewed_commit=COMMIT,
                  validation_scope='Independent saved-log parsing, hashes, cross-record consistency, and local Git capture fixture; no runtime or model rerun',
                  passed=True, assertion_count=COUNT, source_sha256=SOURCES,
                  instance_id=summ['instance_id'], required_tests=summ['required_tests'],
                  log_evidence=evidence, image_digests=summ['image_digests'],
                  recorded_acceptance=summ['acceptance'], git_submission_fixture=fixture,
                  verdict='Accept task/environment-specific functional smoke as artifact-supported; repair prospective submission capture and no-clobber semantics',
                  limitations=['Runtime installation and original container execution not independently rerun.',
                               'Image identities and platform metadata are recorded worker evidence, not independently inspected local runtime state.',
                               'No representative benchmark qualification, model-effect estimate, routing benefit, or confirmatory inference established.',
                               'Plain git diff omits staged, untracked, and committed changes; base diff still needs explicit new-file inclusion.',
                               'The agent runner reuses task/backend output paths and can overwrite prior artifacts.'])
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
