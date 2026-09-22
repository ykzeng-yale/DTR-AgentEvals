"""DTR-REQ-002 M03 part 1 EXECUTED: the pinned upstream grader (SWE-bench f7bbbb2) run offline on the G01-G11 grading
fixtures. Authorized by the author on 2026-09-22 ("yes" to running the pinned SWE-bench code). No container, no
generated eval script and no benchmark: this exercises upstream Python grading/log-parsing functions only.

Runs ONLY in the isolated venv work/venvs/swebench_f7bbbb2 (as M01). For one real instance chosen deterministically
(the first eligible row, in dataset order, whose repo maps to the stock parse_log_pytest parser), a real TestSpec is
built with make_test_spec. Each fixture's status map is then graded two ways:
  direct   get_eval_tests_report(status_map, {F2P, P2P}) -> get_resolution_status == FULL
  log path a constructed log (START/END test-output markers, one "<STATUS> <test>" line per entry; G10 adds the
           TESTS_ERROR marker) -> get_logs_eval(test_spec, log) -> (status map, found) -> graded as above; found=False
           means not resolved (get_eval_report L278-L279)
The executed result is compared with the SOURCE-DERIVED upstream column of grading_conformance.FIXTURES (written before
any execution) and with our declared M03 strict rule. Constructed logs are fixtures, NOT recorded runtime logs: the
runtime part of M03 (recorded logs from the controls) still needs a container runtime.
  work/venvs/swebench_f7bbbb2/bin/python experiments/v2_adapter/m03_upstream_grader_run.py
"""
from __future__ import annotations
import hashlib, json, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import grading_conformance as GC  # noqa: E402

DATA = ROOT / 'work/benchmark_inputs/swebench_verified_c104f840/test-00000-of-00001.parquet'
DATA_SHA = 'a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd'
OUT = ROOT / 'results/v2_adapter/m03_upstream_grader_run_20260922'


def main():
    import pandas as pd
    import swebench
    from swebench.harness.constants import (END_TEST_OUTPUT, FAIL_TO_PASS, KEY_INSTANCE_ID, PASS_TO_PASS, START_TEST_OUTPUT,
                                            TESTS_ERROR, ResolvedStatus)
    from swebench.harness.grading import get_eval_tests_report, get_logs_eval, get_resolution_status
    from swebench.harness.log_parsers import MAP_REPO_TO_PARSER
    from swebench.harness.log_parsers.python import parse_log_pytest
    from swebench.harness.test_spec.test_spec import make_test_spec

    raw = DATA.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DATA_SHA:
        raise SystemExit('dataset checksum mismatch')
    rows = pd.read_parquet(DATA).to_dict('records')
    import qualify_instances as Q
    inst = None
    for row in rows:
        r = {k: (v if not hasattr(v, 'item') else v.item()) for k, v in row.items()}
        if MAP_REPO_TO_PARSER.get(r['repo']) is parse_log_pytest and Q.qualify(r)['status'] == 'eligible':
            inst = r
            break
    if inst is None:
        raise SystemExit('no eligible instance with the stock pytest parser')
    ts = make_test_spec(inst)
    ref = {KEY_INSTANCE_ID: ts.instance_id, FAIL_TO_PASS: GC.F2P, PASS_TO_PASS: GC.P2P}

    def grade(sm):
        return get_resolution_status(get_eval_tests_report(sm, ref)) == ResolvedStatus.FULL.value

    rows_out = []
    with tempfile.TemporaryDirectory() as tmp:
        for fid, sm, log_ok, declared, upstream_src in GC.FIXTURES:
            direct = grade(sm)
            lines = [START_TEST_OUTPUT] + ['%s %s' % (v, k) for k, v in sm.items()] + [END_TEST_OUTPUT]
            if not log_ok:
                lines.insert(1, TESTS_ERROR)
            fp = Path(tmp) / (fid + '.log')
            fp.write_text('\n'.join(lines) + '\n')
            parsed, found = get_logs_eval(ts, str(fp))
            via_log = grade(parsed) if found else False
            expected_up = upstream_src.startswith('resolved')
            rows_out.append(dict(id=fid, status_map=sm, log_ok=log_ok, declared_rule=declared, upstream_source_derived=upstream_src,
                                 upstream_executed_direct=direct, upstream_executed_via_log=via_log, log_found=found,
                                 parsed_equals_fixture=(parsed == sm) if found else None,
                                 source_derived_confirmed=(direct == expected_up == via_log) if log_ok else (via_log == expected_up)))
    agree = sum(r['source_derived_confirmed'] for r in rows_out)
    summ = dict(request='DTR-REQ-002 M03 part 1 executed: pinned upstream grader on G01-G11 (offline, no container)',
                authorization='author, 2026-09-22 ("yes" to running the pinned SWE-bench code)',
                evaluator=dict(commit='f7bbbb2ccdf479001d6467c9e34af59e44a840f9', package_version=swebench.__version__),
                dataset=dict(sha256=DATA_SHA), instance_used=dict(instance_id=inst['instance_id'], repo=inst['repo'], version=inst['version'],
                                                                 parser='parse_log_pytest (stock)'),
                fixtures=len(rows_out), source_derived_upstream_confirmed=agree,
                counts_as_pass_upstream_but_not_declared=[r['id'] for r in rows_out if r['upstream_executed_via_log'] and r['declared_rule'] != 'resolved'],
                rows=rows_out,
                not_done=['recorded runtime logs (M03 runtime part)', 'other repo-specific parsers (django, sympy, astropy, ...)',
                          'any container, generated eval script or benchmark'])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'summary.json').write_text(json.dumps(summ, indent=1) + '\n')
    print(json.dumps({k: summ[k] for k in ('instance_used', 'fixtures', 'source_derived_upstream_confirmed',
                                           'counts_as_pass_upstream_but_not_declared')}, indent=1))
    for r in rows_out:
        print(r['id'], 'declared=%s' % r['declared_rule'], 'upstream(src)=%s' % r['upstream_source_derived'].split(' ')[0],
              'exec direct=%s via_log=%s found=%s parsed_ok=%s confirmed=%s' % (r['upstream_executed_direct'], r['upstream_executed_via_log'],
                                                                               r['log_found'], r['parsed_equals_fixture'], r['source_derived_confirmed']))


if __name__ == '__main__':
    main()
