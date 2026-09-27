"""Pinned evaluator-only bindings and strict control replay. No execution release."""
import ast,hashlib,json,re
from enum import Enum
from pathlib import Path
BUNDLE=Path(__file__).resolve().parents[2]/'docs/source_snapshots/req029w_matplotlib_eval'
MANIFEST='3add0498a93b3f171e453f5802fdc3fa03fe84bcd9eeb82795ef36afe1662733'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def bindings():
    raw=(BUNDLE/'manifest.json').read_bytes();assert sha(raw)==MANIFEST
    for name,pin in json.loads(raw).items():assert sha((BUNDLE/name).read_bytes())==pin
    data=json.loads((BUNDLE/'evaluation_inputs.json').read_bytes())
    assert data['instance_id']=='matplotlib__matplotlib-20826' and len(data['FAIL_TO_PASS'])==1 and len(data['PASS_TO_PASS'])==673
    ns={'Enum':Enum,'re':re,'TestSpec':object,'SWEbenchInstance':dict,'PASSED':'PASSED','Any':object}
    tree=ast.parse((BUNDLE/'constants.py.txt').read_text());nodes=[]
    for n in tree.body:
        if isinstance(n,ast.ClassDef) and n.name in ('TestStatus','EvalType','ResolvedStatus'):nodes.append(n)
        if isinstance(n,ast.Assign):
            try:v=ast.literal_eval(n.value)
            except (ValueError,TypeError):continue
            for t in n.targets:
                if isinstance(t,ast.Name):ns[t.id]=v
    def execute(nodes,label):exec(compile(ast.Module(body=nodes,type_ignores=[]),label,'exec'),ns)
    execute(nodes,'pinned-constants')
    execute([n for n in ast.parse((BUNDLE/'python_parser.py.txt').read_text()).body if not isinstance(n,(ast.Import,ast.ImportFrom))],'pinned-python-parser')
    for suffix in ('C','GO','JAVA','JS','PHP','RUBY','RUST'):ns['MAP_REPO_TO_PARSER_'+suffix]={}
    execute([n for n in ast.parse((BUNDLE/'log_parsers.py.txt').read_text()).body if isinstance(n,ast.Assign)],'pinned-registry')
    assert ns['MAP_REPO_TO_PARSER']['matplotlib/matplotlib'] is ns['parse_log_matplotlib']
    execute([n for n in ast.parse((BUNDLE/'strict_rule.py.txt').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='declared_outcome'],'strict-rule')
    return data,ns

def replay(raw,returncode,mode,*,cleanup_confirmed=False,provenance_verified=False,infrastructure_error=None):
    assert mode in ('baseline','reference') and type(raw) is bytes and len(raw)<=4*1024**2
    data,ns=bindings();text=raw.decode('utf-8',errors='replace');start=ns['START_TEST_OUTPUT'];end=ns['END_TEST_OUTPUT']
    markers=text.count(start)==text.count(end)==1 and text.find(start)<text.find(end)
    bad=[ns[k] for k in ('APPLY_PATCH_FAIL','RESET_FAILED','TESTS_ERROR','TESTS_TIMEOUT') if ns[k] in text]
    statuses=ns['parse_log_matplotlib'](text.split(start,1)[1].split(end,1)[0],None) if markers else {}
    valid=markers and not bad and type(returncode) is int and returncode in (0,1) and cleanup_confirmed is True and provenance_verified is True and infrastructure_error is None
    declared={t:statuses.get(t,'MISSING') for t in data['FAIL_TO_PASS']+data['PASS_TO_PASS']}
    target=all(statuses.get(t)=='FAILED' for t in data['FAIL_TO_PASS'])
    regressions=all(statuses.get(t)=='PASSED' for t in data['PASS_TO_PASS'])
    accepted=bool(valid and ((mode=='baseline' and returncode==1 and target and regressions) or (mode=='reference' and returncode==0 and all(x=='PASSED' for x in declared.values()))))
    return dict(task=data['instance_id'],task_count=1,mode=mode,control_accepted=accepted,
        declared_statuses=declared,extra_statuses={k:v for k,v in statuses.items() if k not in declared},
        strict_outcome=ns['declared_outcome'](data['FAIL_TO_PASS'],data['PASS_TO_PASS'],statuses,valid),
        markers_valid=markers,bad_markers=bad,raw_sha256=sha(raw),returncode=returncode,
        execution_authorized=False,provenance_verified=provenance_verified,cleanup_confirmed=cleanup_confirmed)
