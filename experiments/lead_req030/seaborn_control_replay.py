"""Data-only exact parser replay for frozen diagnostic controls."""
import ast,hashlib,json,re
from enum import Enum
from pathlib import Path
B=Path(__file__).resolve().parents[2]/'docs/source_snapshots/req030q_seaborn_eval'
PIN='03c8d3a4837ebdd065693d09153555af305144f2857651c8e2aabc8707cf9c54'
def sha(b):return hashlib.sha256(b).hexdigest()
def bindings():
 assert sha((B/'manifest.json').read_bytes())==PIN
 for name,digest in json.loads((B/'manifest.json').read_text()).items():assert sha((B/name).read_bytes())==digest
 d=json.loads((B/'evaluation_inputs.json').read_text());assert d['instance_id']=='mwaskom__seaborn-3187'
 assert len(d['FAIL_TO_PASS'])==2 and len(d['PASS_TO_PASS'])==248
 ns={'TestStatus':Enum('TestStatus',{'FAILED':'FAILED','PASSED':'PASSED','SKIPPED':'SKIPPED','ERROR':'ERROR','XFAIL':'XFAIL'}),'TestSpec':object}
 tree=ast.parse((B/'python_parser.py.txt').read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='parse_log_seaborn')
 exec(compile(ast.Module(body=[node],type_ignores=[]),'pinned-seaborn-parser','exec'),ns)
 return d,ns['parse_log_seaborn']
def replay(raw,receipt,mode):
 d,parser=bindings();assert mode in ('baseline','reference') and type(raw) is bytes and len(raw)<=4*1024*1024
 assert sha(raw)==receipt['raw_sha256'] and len(raw)==receipt['raw_bytes']
 text=raw.decode('utf-8','replace');a='>>>>> Start Test Output';z='>>>>> End Test Output'
 markers=text.count(a)==text.count(z)==1 and text.find(a)<text.find(z)
 status=parser(text.split(a,1)[1].split(z,1)[0],None) if markers else {}
 ids=d['FAIL_TO_PASS']+d['PASS_TO_PASS'];declared={i:status.get(i,'MISSING') for i in ids}
 good=markers and receipt['supervisor']['reason']=='exited' and receipt['supervisor']['returncode'] in (0,1)
 accepted=good and ((mode=='baseline' and all(declared[i]=='FAILED' for i in d['FAIL_TO_PASS']) and all(declared[i]=='PASSED' for i in d['PASS_TO_PASS'])) or (mode=='reference' and all(v=='PASSED' for v in declared.values())))
 return dict(mode=mode,task_count=1,valid=good,accepted=accepted,declared=declared,extras={k:v for k,v in status.items() if k not in ids},returncode=receipt['supervisor']['returncode'],raw_sha256=sha(raw))
