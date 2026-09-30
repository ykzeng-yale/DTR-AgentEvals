"""Official-parser candidate replay fixtures, never execution or model outcomes."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from experiments.lead_req030 import req030ai_candidate_grade as grade


def frame(lines):
    return ('DTR_TEST_START\n>>>>> Start Test Output\n'+'\n'.join(lines)+
            '\n>>>>> End Test Output\nDTR_TEST_END\n').encode()


def line(repo, node, status):
    if repo=='django/django':
        return node+' ... '+{'PASSED':'ok','FAILED':'FAIL','ERROR':'ERROR','SKIPPED':"skipped 'fixture'"}[status]
    if repo=='matplotlib/matplotlib':
        node=node.replace('[1]','[MouseButton.LEFT]').replace('[3]','[MouseButton.RIGHT]')
    if repo in {'scikit-learn/scikit-learn','sphinx-doc/sphinx'}:
        return node+' '+status  # Official pytest-v2 suffix format.
    return status+' '+node


def args_for(repo, lines=None, *, evaluation=None):
    tid=next(t for t,r in grade.TASK_REPOS.items() if r==repo)
    if evaluation is None:
        required=(['test_target (tests.FixtureCase)','test_preserved (tests.FixtureCase)']
                  if repo=='django/django' else
                  ['tests/test_inert.py::test_target[1]','tests/test_inert.py::test_preserved[3]'])
        evaluation={'instance_id':tid,'base_commit':'a'*40,'fail_to_pass':required[:1],
                    'pass_to_pass':required[1:],'reference_patch':'DO_NOT_RETURN_REFERENCE_SENTINEL',
                    'stock_eval_script':'DO_NOT_RETURN_SCRIPT_SENTINEL','test_patch':'DO_NOT_RETURN_TEST_SENTINEL'}
    required=evaluation['fail_to_pass']+evaluation['pass_to_pass']
    if lines is None:lines=[line(repo,node,'PASSED') for node in required]
    ev_bytes=grade.canonical(evaluation)
    raw=frame(lines)
    receipt={'reason':'exited','pid':123,'returncode':0,'retained_bytes':len(raw),'elapsed':.1,'error':None}
    patch=b'authored inert candidate bytes; not applied'
    task={'instance_id':tid,'repo':repo,'base_commit':evaluation['base_commit'],
          'evaluator_bundle_sha256':grade.sha(ev_bytes)}
    binding={'task_id':tid,'repo':repo,'base_commit':task['base_commit'],'policy_id':'SL',
             'invocation_id':tid+':SL:assigned-a','release_sha256':'b'*64,
             'evaluator_bundle_sha256':grade.sha(ev_bytes),'patch_sha256':grade.sha(patch),
             'raw_sha256':grade.sha(raw),'supervisor_sha256':grade.sha(grade.canonical(receipt)),
             'parser_sha256':grade.PARSER_SHA256}
    return dict(task=task,evaluator_bundle=ev_bytes,raw=raw,supervisor=receipt,patch=patch,
                expected_patch_sha256=grade.sha(patch),expected_binding=binding,observed_binding=copy.deepcopy(binding))


def rebind_artifacts(args):
    # Independent replay expectations, after retrieval. Prospective task/policy/
    # invocation identity is unchanged, even for diagnostic corrupted artifacts.
    changes={'raw_sha256':grade.sha(args['raw']),
             'supervisor_sha256':grade.sha(grade.canonical(args['supervisor']))}
    args['expected_binding'].update(changes);args['observed_binding'].update(changes)


def assert_unknown(result):
    assert result['graded'] is False and result['resolved'] is False
    assert result['operational_resolution']==0 and result['algorithmic_correctness']=='unknown'
    assert result['assigned_slot_retained'] is True


@pytest.mark.parametrize('repo',grade.TASK_REPOS.values())
def test_all_eight_official_repo_parsers_resolve_exact_declared_passes(repo):
    args=args_for(repo)
    result=grade.replay_candidate(**args)
    assert result['graded'] and result['resolved'], result
    assert result['operational_resolution']==1 and result['task_count']==1
    assert result['declared_check_count']==2
    assert result['parser_sha256']==grade.controls.PARSER_SHA
    assert result['raw_sha256']==grade.sha(args['raw'])
    assert 'DO_NOT_RETURN' not in json.dumps(result)


@pytest.mark.parametrize('repo',grade.TASK_REPOS.values())
@pytest.mark.parametrize('status',['FAILED','SKIPPED'])
def test_observed_required_nonpass_is_strict_unresolved(repo,status):
    args=args_for(repo);ev=json.loads(args['evaluator_bundle'])
    required=ev['fail_to_pass']+ev['pass_to_pass']
    args['raw']=frame([line(repo,required[0],status),line(repo,required[1],'PASSED')])
    args['supervisor']['retained_bytes']=len(args['raw']);rebind_artifacts(args)
    result=grade.replay_candidate(**args)
    assert result['graded'] and result['resolved'] is False
    assert result['algorithmic_correctness']==('unresolved' if status=='FAILED' else 'unknown')
    assert result['operational_resolution']==0


def test_required_xfail_is_observed_unresolved():
    args=args_for('psf/requests');ev=json.loads(args['evaluator_bundle'])
    args['raw']=frame([line('psf/requests',ev['fail_to_pass'][0],'XFAIL'),
                       line('psf/requests',ev['pass_to_pass'][0],'PASSED')])
    args['supervisor']['retained_bytes']=len(args['raw']);rebind_artifacts(args)
    result=grade.replay_candidate(**args)
    assert result['graded'] and not result['resolved']
    assert result['algorithmic_correctness']=='unknown'


@pytest.mark.parametrize('repo',grade.TASK_REPOS.values())
def test_each_required_identity_omission_and_error_fails_closed(repo):
    original=args_for(repo);evaluation=json.loads(original['evaluator_bundle'])
    required=evaluation['fail_to_pass']+evaluation['pass_to_pass']
    for absent in required:
        args=args_for(repo,[line(repo,node,'PASSED') for node in required if node!=absent])
        result=grade.replay_candidate(**args)
        assert_unknown(result);assert result['declared_statuses'][absent]=='MISSING'
        args=args_for(repo,[line(repo,node,'ERROR' if node==absent else 'PASSED') for node in required])
        assert_unknown(grade.replay_candidate(**args))


def test_undeclared_statuses_do_not_redefine_declared_endpoint():
    args=args_for('psf/requests');evaluation=json.loads(args['evaluator_bundle'])
    lines=[line('psf/requests',n,'PASSED') for n in evaluation['fail_to_pass']+evaluation['pass_to_pass']]
    args=args_for('psf/requests',lines+['FAILED extra_failure','ERROR extra_error'])
    result=grade.replay_candidate(**args)
    assert result['resolved'] and result['graded']
    assert result['undeclared_statuses']=={'extra_failure':'FAILED','extra_error':'ERROR'}
    assert result['undeclared_error_count']==1 and result['undeclared_review_required']


@pytest.mark.parametrize('mutation',[{'reason':'deadline'},{'error':'fixture'}, {'pid':True},{'returncode':2},
    {'returncode':True},{'retained_bytes':0},{'elapsed':-1},{'extra':'unexpected'}])
def test_malformed_supervisor_rejected_even_if_log_says_pass(mutation):
    args=args_for('django/django');args['supervisor'].update(mutation);rebind_artifacts(args)
    assert_unknown(grade.replay_candidate(**args))


def test_every_required_supervisor_field_is_mandatory():
    for field in args_for('django/django')['supervisor']:
        args=args_for('django/django');del args['supervisor'][field];rebind_artifacts(args)
        assert_unknown(grade.replay_candidate(**args))


@pytest.mark.parametrize('elapsed',[float('nan'),float('inf')])
def test_nonfinite_supervisor_measurements_fail_closed(elapsed):
    args=args_for('django/django');args['supervisor']['elapsed']=elapsed
    assert_unknown(grade.replay_candidate(**args))


@pytest.mark.parametrize('mutation',[
    lambda raw:raw+b'DTR_TEST_START\n',
    lambda raw:raw.replace(b'DTR_TEST_END',b''),
    lambda raw:b'DTR_TEST_END\n'+raw.replace(b'DTR_TEST_END\n',b''),
    lambda raw:raw+b'DTR_SETUP_FAILURE\n',
    lambda raw:raw+b'DTR_ISOLATION_FAILURE\n',
    lambda raw:raw+b'DTR_EVAL_ERROR\n',
])
def test_framing_and_setup_errors_are_unknown(mutation):
    args=args_for('matplotlib/matplotlib');args['raw']=mutation(args['raw'])
    args['supervisor']['retained_bytes']=len(args['raw']);rebind_artifacts(args)
    assert_unknown(grade.replay_candidate(**args))


@pytest.mark.parametrize('field',sorted(grade.BINDING_FIELDS))
def test_binding_mutation_or_omission_cannot_move_result_to_another_assignment(field):
    args=args_for('pytest-dev/pytest');args['observed_binding'][field]='tampered'
    assert_unknown(grade.replay_candidate(**args))
    args=args_for('pytest-dev/pytest');del args['observed_binding'][field]
    assert_unknown(grade.replay_candidate(**args))


def test_patch_and_evaluator_identities_fail_closed():
    for change in ({'patch':b''},{'patch':b'changed'},{'expected_patch_sha256':'bad'},
                   {'evaluator_bundle':b'{}'}):
        args=args_for('pydata/xarray');args.update(change)
        assert_unknown(grade.replay_candidate(**args))


def test_candidate_replay_has_no_execution_or_file_write_path(monkeypatch):
    import subprocess
    def forbidden(*args,**kwargs):raise AssertionError('execution/write forbidden')
    monkeypatch.setattr(subprocess,'Popen',forbidden)
    monkeypatch.setattr(subprocess,'run',forbidden)
    monkeypatch.setattr(Path,'write_bytes',forbidden)
    monkeypatch.setattr(Path,'write_text',forbidden)
    assert grade.replay_candidate(**args_for('sphinx-doc/sphinx'))['resolved']


def test_complete_private_frozen_identity_lists_and_every_single_omission():
    bundle=grade.controls.ROOT/'work/req030ah_controls_20260930_a/evaluator'
    if not bundle.is_dir():pytest.skip('private frozen AH evaluator bundle unavailable')
    mutation_count=0
    for task_id,repo in grade.TASK_REPOS.items():
        evaluation=json.loads((bundle/(task_id+'.json')).read_bytes())
        required=evaluation['fail_to_pass']+evaluation['pass_to_pass']
        lines=[line(repo,node,'PASSED') for node in required]
        args=args_for(repo,lines,evaluation=evaluation)
        result=grade.replay_candidate(**args)
        assert result['resolved'] and result['declared_check_count']==len(required), result
        for missing in range(len(required)):
            args=args_for(repo,lines[:missing]+lines[missing+1:],evaluation=evaluation)
            result=grade.replay_candidate(**args)
            assert_unknown(result)
            assert result['declared_statuses'][required[missing]]=='MISSING'
            mutation_count+=1
    assert mutation_count==1398
