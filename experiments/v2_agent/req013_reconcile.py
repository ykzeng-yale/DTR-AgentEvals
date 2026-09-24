"""DTR-REQ-013 step 1a (lead 702e58a, docs/theory_feedback_20260924_req012_decision.md): reconcile the published
REQ-012 probe without a model, a server or a container.

    .venv/bin/python experiments/v2_agent/req013_reconcile.py

Every value is computed from the committed files under results/v2_agent/req012_repair_probe_20260924/probe and the
committed REQ-012 manifest. Each input must be tracked, unchanged from HEAD and equal to the published sha256 in the
probe's publication_manifest.json. The records must agree with each other: pair summary, ledger, episode, trajectory,
calls, attempts, receipts, submission, grade, stock report, grader result and repair record. Their values must also
equal the lead's review (EXPECTED). Only then is
results/v2_agent/req013_14b_discriminator_20260924/reconciliation.json written (write-once, sanitized). On any mismatch
the script exits 2 with the problems on stderr and writes nothing.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / 'experiments/v2_adapter') not in sys.path:
    sys.path.insert(0, str(ROOT / 'experiments/v2_adapter'))
import req010_sentinel as S  # noqa: E402  sha, sanitize, write-once JSON, username guard, sh

REQUEST = 'DTR-REQ-013'
PROBE = 'results/v2_agent/req012_repair_probe_20260924/probe'
MANIFEST12 = 'configs/v2_req012_repair_probe_20260924.json'
OUT = 'results/v2_agent/req013_14b_discriminator_20260924/reconciliation.json'
SUBMIT = 'echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT'
EXPECTED = OrderedDict(          # the lead's REQ-012 review (docs/theory_feedback_20260924_req012_decision.md)
    model_calls=3, executed_tool_commands=1, format_error_turns=1, format_error_proposed_actions=2,
    format_error_actions_executed=0, final_action=SUBMIT, exit_status='Submitted', request_receipts=3,
    outcome_receipts=3, submission_bytes=466, submission_files=['test_fits_card.py'],
    submission_new_files=['test_fits_card.py'], submission_source_files=[], fail_to_pass=[0, 1],
    pass_to_pass=[175, 175], strict_outcome='unresolved', upstream_resolved=False, image_equal_to_pin=True,
    stall_guard_fired=False)
DIFF_FILE = re.compile(r'^diff --git a/(\S+) b/(\S+)$', re.M)


class Mismatch(Exception):
    pass


def need(cond, what):
    if not cond:
        raise Mismatch(what)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Inputs:
    """Reads committed inputs: tracked, unchanged from HEAD and (under the probe) equal to the published sha256."""

    def __init__(self, root, run):
        self.root, self.run, self.read = Path(root), run, OrderedDict()
        self.published = self.json(PROBE + '/publication_manifest.json', check_manifest=False)

    def bytes(self, rel, check_manifest=True):
        data = (self.root / rel).read_bytes()
        need(self.run(['git', '-C', str(self.root), 'ls-files', '--error-unmatch', rel])[0] == 0, '%s is not tracked'
             % rel)
        need(self.run(['git', '-C', str(self.root), 'diff', '--quiet', 'HEAD', '--', rel])[0] == 0,
             '%s differs from HEAD' % rel)
        if check_manifest and rel.startswith(PROBE + '/'):
            entry = self.published.get(rel[len(PROBE) + 1:])
            need(isinstance(entry, dict) and entry.get('published_sha256') == sha(data),
                 '%s does not match its publication_manifest.json sha256' % rel)
        self.read[rel] = sha(data)
        return data

    def json(self, rel, check_manifest=True):
        return json.loads(self.bytes(rel, check_manifest))

    def lines(self, rel):
        return [json.loads(x) for x in self.bytes(rel).decode().splitlines() if x.strip()]


def proposed_action_facts(command):
    """Facts about a proposed (never executed) command: what it would write, define and replace."""
    return OrderedDict(
        command_sha256=sha(command.encode()), command_chars=len(command), first_line=command.splitlines()[0][:200],
        is_submit_command=command.strip() == SUBMIT,
        would_write_files=re.findall(r"cat <<'?\w+'? > (\S+)", command),
        would_run=re.findall(r'^python (\S+)\s*$', command, re.M),
        defines_python_functions=re.findall(r'^\s*def (\w+)\(', command, re.M),
        string_replace_calls=re.findall(r'\.replace\(([^)]*)\)', command),
        repository_source_paths=sorted(set(re.findall(r'\bastropy/[\w/.]+', command))), executed=False)


def facts(root=ROOT, run=S.sh):
    """The reconciled facts; raises Mismatch on any internal inconsistency."""
    src = Inputs(root, run)
    summary = src.json(PROBE + '/pair_summary.json')
    need(summary.get('status') == 'COMPLETED' and len(summary.get('assignments') or []) == 1,
         'pair_summary is not one completed assignment')
    row = summary['assignments'][0]
    run_id = row['run_id']
    need(re.fullmatch(r'[\w.-]+', run_id or '') is not None, 'run_id is not a plain name')
    d = PROBE + '/' + run_id
    ledger = src.lines(PROBE + '/ledger.jsonl')
    need([(e['event'], e['order'], e['run_id'], e.get('state')) for e in ledger] == [
        ('start', 1, run_id, None), ('end', 1, run_id, 'completed')], 'ledger is not one start and one completed end')
    pin = src.json(MANIFEST12)['images']['instance']['id']
    ep = src.json(d + '/episode.json')
    traj = src.json(d + '/trajectory.json')
    calls = src.lines(d + '/calls.jsonl')
    attempts = src.lines(d + '/attempts.jsonl')
    diff = src.bytes(d + '/submission.diff')
    grade = src.json(d + '/grade.json')
    result = src.json(d + '/control/grade_result.json')
    repair = src.json(d + '/control/repair_record.json')

    # ---------------- transcript: trajectory messages against calls.jsonl, attempts.jsonl and the episode record
    msgs = traj['messages']
    kind = lambda m: (m.get('extra') or {}).get('interrupt_type')  # noqa: E731
    assistants = [m for m in msgs if m['role'] == 'assistant']
    observations = [m for m in msgs if m['role'] == 'user' and 'returncode' in (m.get('extra') or {})]
    format_errors = [m for m in msgs if kind(m) == 'FormatError']
    need(msgs[-1]['role'] == 'exit', 'the trajectory does not end with an exit message')
    exit_status = msgs[-1]['extra']['exit_status']
    by_call = OrderedDict()
    for e in calls:
        by_call.setdefault(e['call'], []).append(e)
    shape = [[e['event'] for e in by_call[c]] for c in by_call]
    need(shape == [['open', 'transport', 'parsed_action', 'observation'], ['open', 'format_error', 'transport'],
                   ['open', 'transport', 'parsed_action']], 'calls.jsonl event sequence %s' % shape)
    model_calls = OrderedDict(episode_n_model_calls=ep['n_model_calls'], episode_logical_calls=ep['logical_calls'],
                              trajectory_api_calls=traj['info']['model_stats']['api_calls'],
                              calls_jsonl_opened=len(by_call),
                              attempt_results_ok=sum(a['event'] == 'result' and a.get('ok') is True for a in attempts),
                              assistant_messages_plus_format_errors=len(assistants) + len(format_errors))
    need(len(set(model_calls.values())) == 1, 'model call counts disagree: %s' % dict(model_calls))
    need(len(attempts) == 2 * len(by_call) and ep['physical_requests'] == len(by_call), 'attempt counts disagree')
    actions = [m['extra']['actions'] for m in assistants]
    need(all(len(a) == 1 for a in actions), 'an assistant message does not carry exactly one action')
    parsed = [e for c in by_call.values() for e in c if e['event'] == 'parsed_action']
    need([sha(a[0]['command'].encode()) for a in actions] == [e['command_sha256'] for e in parsed],
         'trajectory commands differ from calls.jsonl command_sha256')
    call_obs = [e for c in by_call.values() for e in c if e['event'] == 'observation']
    need(len(call_obs) == len(observations) and [e['returncode'] for e in call_obs] ==
         [m['extra']['returncode'] for m in observations], 'observations disagree between trajectory and calls.jsonl')
    order = [('A' if m['role'] == 'assistant' else 'O' if m in observations else 'F' if m in format_errors else '-')
             for m in msgs[2:-1]]
    need(order == ['A', 'O', 'F', 'A'], 'the transcript order is %s' % order)
    tool_command = actions[0][0]['command']
    final_action = actions[-1][0]['command'].strip()
    fe = format_errors[0]['extra']
    regex = traj['info']['config']['model']['action_regex']
    proposed = re.findall(regex, fe['model_response'], re.S)
    need(fe['model_response'] == fe['response']['choices'][0]['message']['content'],
         'the saved FormatError response text disagrees with the saved response object')
    need(len(proposed) == fe['n_actions'], 'the saved response does not parse into n_actions actions')
    turns = repair['guard']['turns']
    normalized = re.sub(r'\s+', ' ', tool_command).strip()
    need([None if t is None else t['command_sha256'] for t in turns] == [sha(normalized.encode()), None],
         'the stall guard turns are not [the executed command, a FormatError reset]')
    wrote = re.findall(r"cat <<'?\w+'? > (\S+)", tool_command)

    # ---------------- receipts
    rdir = root / d / 'receipts'
    req_names = sorted(p.name for p in rdir.glob('*.request.json'))
    out_names = sorted(p.name for p in rdir.glob('*.outcome.json'))
    need(sorted(p.name for p in rdir.iterdir()) == sorted(req_names + out_names), 'unexpected files in receipts/')
    requests = [src.json('%s/receipts/%s' % (d, n)) for n in req_names]
    outcomes = [src.json('%s/receipts/%s' % (d, n)) for n in out_names]
    keys = [e['attempts'][0]['attempt_keys'][0] for c in by_call.values() for e in c if e['event'] == 'transport']
    need([r['attempt_key'] for r in requests] == [o['attempt_key'] for o in outcomes] == keys,
         'receipt attempt keys disagree with calls.jsonl')
    need(all(o['outcome'] == 'ok' and o['http_status'] == 200 for o in outcomes), 'an outcome receipt is not ok/200')
    need(all(r['identity']['model']['alias'] == ep['backend_alias'] for r in requests), 'receipt model alias differs')

    # ---------------- submission
    files = DIFF_FILE.findall(diff.decode())
    need(all(a == b for a, b in files), 'a diff header renames a file')
    paths = [a for a, _ in files]
    blocks = re.split(r'(?m)^(?=diff --git )', diff.decode())[1:]
    new_files = [p for p, b in zip(paths, blocks) if re.search(r'(?m)^new file mode ', b)]
    body = [x for x in diff.decode().splitlines() if not x.startswith(('+++', '---'))]
    subs = [sha(diff), ep['submission_sha256'], grade['submission_sha256'], row['submission_sha256']]
    need(len(set(subs)) == 1, 'submission sha256 disagree: %s' % subs)
    need(len(diff) == ep['submission_bytes'], 'submission bytes differ from episode.json')

    # ---------------- grade, stock report, grader result
    report_rel = '%s/grading/logs/run_evaluation/%s/%s/%s/report.json' % (
        PROBE, grade['attempts'][-1]['evaluator_run_id'], ep['backend_alias'], ep['instance_id'])
    stock = src.json(report_rel)[ep['instance_id']]
    upstream = grade['upstream_report'][ep['instance_id']]
    need(stock == upstream, 'the stock report differs from the grade record')
    ts = upstream['tests_status']
    f2p, p2p = ts['FAIL_TO_PASS'], ts['PASS_TO_PASS']
    need(sorted(grade['required_status']) == sorted(f2p['success'] + f2p['failure'] + p2p['success'] + p2p['failure'])
         and all(grade['required_status'][t] == 'FAILED' for t in f2p['failure'])
         and all(grade['required_status'][t] == 'PASSED' for t in f2p['success'] + p2p['success']),
         'required_status disagrees with the tests_status lists')
    need(row['grade'].get('strict_outcome') == grade['strict_outcome'] and
         row['grade'].get('upstream_resolved') == grade['upstream_resolved'], 'pair_summary grade differs')
    need(result['status'] == 'graded: evaluated' and grade['classification'] == 'evaluated' and grade['grade_valid']
         is True, 'the grade is not a valid evaluated grade')

    return src.read, OrderedDict(
        run_id=run_id, image_pin=pin,
        transcript=OrderedDict(
            model_calls=ep['n_model_calls'], model_call_sources=model_calls,
            executed_tool_commands=len(observations), format_error_turns=len(format_errors),
            calls=[OrderedDict(call=1, kind='executed tool command', command_sha256=sha(tool_command.encode()),
                               command_chars=len(tool_command), wrote_files=wrote,
                               returncode=observations[0]['extra']['returncode'], observation_returned=True),
                   OrderedDict(call=2, kind='FormatError (no action executed)', n_actions=fe['n_actions'],
                               proposed_actions=[proposed_action_facts(c) for c in proposed]),
                   OrderedDict(call=3, kind='final submit', action=final_action, exit_status=exit_status,
                               observation_returned=False)],
            format_error_proposed_actions=len(proposed),
            format_error_actions_executed=0 if shape[1] == ['open', 'format_error', 'transport'] and turns[1] is None
            else None,
            final_action=final_action, exit_status=exit_status,
            not_executed_evidence='calls.jsonl has no parsed_action or observation event for call 2; the trajectory '
                                  'has no observation between the FormatError and the call-3 assistant message; the '
                                  'stall guard recorded the call-2 turn as a reset (null)'),
        receipts=OrderedDict(request_receipts=len(requests), outcome_receipts=len(outcomes), attempt_keys=keys),
        submission=OrderedDict(
            bytes=len(diff), sha256=sha(diff), equals_grade_submission_sha256=sha(diff) == grade['submission_sha256'],
            files=paths, new_files=new_files, modified_or_deleted_existing_files=[p for p in paths if p not in new_files],
            source_files=[p for p in paths if p.startswith('astropy/')],
            added_lines=sum(x.startswith('+') for x in body), removed_lines=sum(x.startswith('-') for x in body),
            written_by_the_call1_command=paths == wrote),
        grade=OrderedDict(
            fail_to_pass=[len(f2p['success']), len(f2p['success']) + len(f2p['failure'])],
            failing_fail_to_pass_tests=f2p['failure'],
            pass_to_pass=[len(p2p['success']), len(p2p['success']) + len(p2p['failure'])],
            strict_outcome=grade['strict_outcome'], upstream_resolved=grade['upstream_resolved'],
            patch_successfully_applied=upstream['patch_successfully_applied'], evaluator_commit=grade['evaluator_commit'],
            stock_report=report_rel, stock_report_equals_grade_record=True),
        image=OrderedDict(pin=pin, grade_image_id=grade['image_id'], before=result['image_before'],
                          after=result['image_after'], after_equals_pin_recorded=result['image_after_equals_pin'],
                          equal_to_pin=grade['image_id'] == result['image_before'] == result['image_after'] == pin
                          and result['image_after_equals_pin'] is True),
        stall_guard=OrderedDict(fired=repair['guard']['fired'], network_mode=repair['guard']['network']['network_mode'],
                                effective_config_verified=repair['effective_config']['verified']))


def observed(f):
    t, s, g = f['transcript'], f['submission'], f['grade']
    return OrderedDict(
        model_calls=t['model_calls'], executed_tool_commands=t['executed_tool_commands'],
        format_error_turns=t['format_error_turns'], format_error_proposed_actions=t['format_error_proposed_actions'],
        format_error_actions_executed=t['format_error_actions_executed'], final_action=t['final_action'],
        exit_status=t['exit_status'], request_receipts=f['receipts']['request_receipts'],
        outcome_receipts=f['receipts']['outcome_receipts'], submission_bytes=s['bytes'], submission_files=s['files'],
        submission_new_files=s['new_files'], submission_source_files=s['source_files'], fail_to_pass=g['fail_to_pass'],
        pass_to_pass=g['pass_to_pass'], strict_outcome=g['strict_outcome'], upstream_resolved=g['upstream_resolved'],
        image_equal_to_pin=f['image']['equal_to_pin'], stall_guard_fired=f['stall_guard']['fired'])


def reconcile(root=ROOT, run=S.sh):
    """(record, problems): the record is None whenever there is a problem."""
    try:
        inputs, f = facts(root, run)
    except (Mismatch, OSError, ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
        return None, ['%s: %s' % (type(e).__name__, str(e)[:300])]
    obs = observed(f)
    problems = ['%s: observed %r, expected %r' % (k, obs[k], v) for k, v in EXPECTED.items() if obs[k] != v]
    if not f['submission']['equals_grade_submission_sha256'] or not f['submission']['written_by_the_call1_command']:
        problems.append('the submission is not the call-1 reproducer graded by the evaluator')
    if problems:
        return None, problems
    g = f['grade']
    statement = ('REQ-012 probe %s: %d model calls; %d executed tool command (it wrote %s); %d FormatError turn with %d '
                 'proposed actions, none executed; then %r ended the episode as %s. The %d-byte submission adds only '
                 '%s (a new file, no source file). The unchanged evaluator applied it: FAIL_TO_PASS %d/%d (%s '
                 'failing), PASS_TO_PASS %d/%d, strict %s. The image equalled the pin before and after grading.' % (
                     f['run_id'], obs['model_calls'], obs['executed_tool_commands'],
                     ', '.join(f['transcript']['calls'][0]['wrote_files']), obs['format_error_turns'],
                     obs['format_error_proposed_actions'], obs['final_action'], obs['exit_status'],
                     obs['submission_bytes'], ', '.join(obs['submission_files']), g['fail_to_pass'][0],
                     g['fail_to_pass'][1], ', '.join(g['failing_fail_to_pass_tests']), g['pass_to_pass'][0],
                     g['pass_to_pass'][1], obs['strict_outcome']))
    return OrderedDict(
        request=REQUEST, kind='DTR-REQ-013 step 1a: reconciliation of the published REQ-012 probe (no model, no server, '
                              'no container; every value computed from committed files)',
        lead_decision='docs/theory_feedback_20260924_req012_decision.md', source=PROBE, manifest=MANIFEST12,
        inputs=inputs, expected=EXPECTED, observed=obs, facts=f, verified=True, statement=statement,
        interpretation='A submitted reproducer with FAIL_TO_PASS still failing is unresolved, not a repair. The '
                       'proposed fix_fits_card function in the FormatError response was never executed and would not '
                       'have edited the astropy source.'), []


def main(argv=None, root=ROOT, run=S.sh):
    out = Path(root) / OUT
    if out.exists():
        print('%s already exists (write-once)' % OUT, file=sys.stderr)
        return 3
    record, problems = reconcile(root, run)
    if problems:
        print('DTR-REQ-013 reconciliation FAILED (nothing written):\n  ' + '\n  '.join(problems), file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    S.write_json_x(out, record)
    if S.username_hits(out.parent):
        print('username found under %s: do not publish until redacted' % out.parent, file=sys.stderr)
        return 2
    print(json.dumps(OrderedDict(verified=True, record=OUT, statement=record['statement'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
