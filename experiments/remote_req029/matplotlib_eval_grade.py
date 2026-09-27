"""Pinned Matplotlib registry, stock command generation and strict declared endpoint."""
import ast,re
from enum import Enum
from types import SimpleNamespace
from matplotlib_eval_contract import *

def execute_nodes(path,select,ns):
    tree=ast.parse(path.read_text())
    nodes=[n for n in tree.body if select(n)]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
    return ns

def bindings():
    data,_,pins=inputs()
    ns={'Enum':Enum,'re':re,'TestSpec':object,'SWEbenchInstance':dict,'PASSED':'PASSED','Any':object}
    execute_nodes(BUNDLE/'constants.py.txt',lambda n:isinstance(n,ast.ClassDef) and n.name in ('TestStatus','EvalType','ResolvedStatus'),ns)
    for n in ast.parse((BUNDLE/'constants.py.txt').read_text()).body:
        if isinstance(n,ast.Assign):
            try:v=ast.literal_eval(n.value)
            except (ValueError,TypeError):continue
            for t in n.targets:
                if isinstance(t,ast.Name):ns[t.id]=v
    execute_nodes(BUNDLE/'python_parser.py.txt',lambda n:not isinstance(n,(ast.Import,ast.ImportFrom)),ns)
    for suffix in ('C','GO','JAVA','JS','PHP','RUBY','RUST'):ns['MAP_REPO_TO_PARSER_'+suffix]={}
    execute_nodes(BUNDLE/'log_parsers.py.txt',lambda n:isinstance(n,ast.Assign),ns)
    require(ns['MAP_REPO_TO_PARSER']['matplotlib/matplotlib'] is ns['parse_log_matplotlib'],'actual Matplotlib registry selection')
    execute_nodes(BUNDLE/'strict_rule.py.txt',lambda n:isinstance(n,ast.FunctionDef) and n.name=='declared_outcome',ns)
    execute_nodes(BUNDLE/'grading.py.txt',lambda n:isinstance(n,ast.FunctionDef),ns)
    # This file is pinned Python data; it contains no imports, network or processes.
    execute_nodes(BUNDLE/'constants_python.py.txt',lambda n:True,ns)
    ns['MAP_REPO_VERSION_TO_SPECS']=ns['MAP_REPO_VERSION_TO_SPECS_PY']
    ns['get_modified_files']=lambda patch:re.findall(r'^--- a/(.+)$',patch,re.M)
    ns['get_new_files']=lambda patch:[] # exact pinned patch has no new files
    execute_nodes(BUNDLE/'test_spec_python.py.txt',lambda n:isinstance(n,ast.FunctionDef) and n.name in
        ('get_test_directives','make_eval_script_list_py'),ns)
    specs=ns['MAP_REPO_VERSION_TO_SPECS']['matplotlib/matplotlib']['3.4']
    commands=ns['make_eval_script_list_py'](data,specs,'testbed','/testbed',BASE,data['test_patch'])
    stock='#!/bin/bash\nset -uxo pipefail\n'+'\n'.join(commands)+'\n'
    require(stock==data['stock_eval_script'],'actual stock command-generation binding')
    require(specs['install']==OMITTED and COMMAND in commands,'stock selected command and omission')
    return ns,stock

def grade(raw,returncode,mode,run_id,infra_error=None,cleanup_confirmed=True):
    require(mode in MODES,'fixed control mode');data,_,pins=inputs();ns,_=bindings()
    text=raw.decode('utf-8',errors='replace');start=ns['START_TEST_OUTPUT'];end=ns['END_TEST_OUTPUT']
    valid=text.count(start)==1 and text.count(end)==1 and text.find(start)<text.find(end)
    bad=[ns[k] for k in ('APPLY_PATCH_FAIL','RESET_FAILED','TESTS_ERROR','TESTS_TIMEOUT') if ns[k] in text]
    status={};parse_error=None
    if valid:
        try:status=ns['MAP_REPO_TO_PARSER']['matplotlib/matplotlib'](text.split(start,1)[1].split(end,1)[0],None)
        except BaseException as e:parse_error=repr(e)
    log_ok=valid and not bad and parse_error is None and type(returncode) is int and returncode in (0,1) and infra_error is None and cleanup_confirmed
    outcome=ns['declared_outcome'](data['FAIL_TO_PASS'],data['PASS_TO_PASS'],status,log_ok)
    declared={t:status.get(t,'MISSING') for t in data['FAIL_TO_PASS']+data['PASS_TO_PASS']}
    baseline=all(status.get(t)=='FAILED' for t in data['FAIL_TO_PASS']) and all(status.get(t)=='PASSED' for t in data['PASS_TO_PASS'])
    reference=all(v=='PASSED' for v in declared.values())
    # Extra selected tests are retained, never silently folded into the declared endpoint.
    accepted=log_ok and bool(status) and (baseline if mode=='baseline' else reference)
    if (mode=='baseline' and returncode!=1) or (mode=='reference' and returncode!=0):accepted=False
    extra={t:v for t,v in status.items() if t not in declared}
    return dict(protocol=PROTOCOL,task=TASK,run_id=run_id,mode=mode,
        dataset_sha256=DATASET_SHA,upstream_source_path=UPSTREAM_SOURCE,manifest_sha256=MANIFEST_SHA,
        inputs_sha256=INPUT_SHA,reference_patch_sha256=PATCH_SHA,source_pins=pins,
        raw_output_sha256=sha(raw),raw_output_bytes=len(raw),returncode=returncode,
        markers_valid=valid,bad_markers=bad,parser_error=parse_error,infrastructure_error=infra_error,
        cleanup_confirmed=cleanup_confirmed,outcome=outcome,control_accepted=bool(accepted),
        declared_statuses=declared,declared_unique_count=674,declared_observed_count=sum(v!='MISSING' for v in declared.values()),
        parsed_statuses=status,parser_map_size=len(status),extra_statuses=extra,

        raw_runner_totals=[int(n) for n in re.findall(r'^Ran (\d+) tests? in ',text,re.M)],
        upstream_report=ns['get_eval_tests_report'](status,data),
        untouched_stock_harness=False,omitted_install=OMITTED,command=COMMAND)
