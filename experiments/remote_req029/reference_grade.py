"""Data-only grading using exact AST-extracted pinned upstream parser and strict rule."""
import ast,re
from enum import Enum
from reference_contract import BUNDLE,PINS,INPUT_SHA,PATCH_SHA,inputs,MODE,PROTOCOL
from c6_protocol import sha,require

def extract(path,names,namespace):
    tree=ast.parse(path.read_text())
    nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
    require({n.name for n in nodes}==set(names),'pinned function missing')
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),namespace)
    return namespace

def bindings():
    inputs() # all snapshots hash verified before execution, not log-supplied code
    ns={'Enum':Enum,'re':re,'TestSpec':object,'PASSED':'PASSED'}
    extract(BUNDLE/'constants.py.txt',['TestStatus'],ns)
    tree=ast.parse((BUNDLE/'python_parser.py.txt').read_text())
    aliases={t.id:n.value.id for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.value,ast.Name) for t in n.targets if isinstance(t,ast.Name)}
    require(aliases.get('parse_log_astropy')=='parse_log_pytest_v2','Astropy alias changed')
    mapping=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MAP_REPO_TO_PARSER_PY' for t in n.targets))
    require(any(isinstance(k,ast.Constant) and k.value=='astropy/astropy' and isinstance(v,ast.Name) and v.id=='parse_log_astropy' for k,v in zip(mapping.keys,mapping.values)),'Astropy registry changed')
    extract(BUNDLE/'python_parser.py.txt',['parse_log_pytest_v2'],ns)
    extract(BUNDLE/'strict_rule.py.txt',['declared_outcome'],ns)
    constants={t.id:ast.literal_eval(n.value) for n in ast.parse((BUNDLE/'constants.py.txt').read_text()).body if isinstance(n,ast.Assign) and isinstance(n.value,ast.Constant) for t in n.targets if isinstance(t,ast.Name)}
    return ns,constants

def grade(raw,returncode,mode,run_id,infra_error=None,cleanup_confirmed=True):
    require(mode==MODE,'reference-only mode');data,_=inputs();ns,c=bindings()
    text=raw.decode('utf-8',errors='replace');start=c['START_TEST_OUTPUT'];end=c['END_TEST_OUTPUT']
    valid=text.count(start)==1 and text.count(end)==1 and text.find(start)<text.find(end)
    bad=[c[k] for k in ('APPLY_PATCH_FAIL','RESET_FAILED','TESTS_ERROR','TESTS_TIMEOUT') if c[k] in text]
    collection=bool(re.search(r'ERROR collecting|ImportError while importing|INTERNALERROR',text))
    status={}
    if valid:status=ns['parse_log_pytest_v2'](text.split(start,1)[1].split(end,1)[0],None)
    log_ok=valid and not bad and returncode in (0,1) and not collection and infra_error is None and cleanup_confirmed
    result=ns['declared_outcome'](data['FAIL_TO_PASS'],data['PASS_TO_PASS'],status,log_ok)
    # Exit1 with an all-PASSED map is inconsistent: never promote it to resolved.
    if result=='resolved' and returncode!=0:result='unknown_evaluator_failure'
    return dict(protocol=PROTOCOL,run_id=run_id,mode=mode,reference_patch_sha256=PATCH_SHA,
        applied_patch_sha256=None,
        inputs_sha256=INPUT_SHA,source_pins=PINS,raw_output_sha256=sha(raw),returncode=returncode,
        markers_valid=valid,bad_markers=bad,collection_or_import_error=collection,
        infrastructure_error=infra_error,cleanup_confirmed=cleanup_confirmed,outcome=result,
        declared_statuses={t:status.get(t,'MISSING') for t in data['FAIL_TO_PASS']+data['PASS_TO_PASS']},
        parsed_statuses=status,all_declared_passed=all(status.get(t)=='PASSED' for t in data['FAIL_TO_PASS']+data['PASS_TO_PASS']),
        untouched_stock_harness=False,execution_environment='offline existing W2R editable imports; stock pip install omitted')
