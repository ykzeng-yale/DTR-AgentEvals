"""ID-only incremental project-record audit. Does not decode task/model outcomes.

A mention is not automatically exposure; absence is scoped to scanned records.
No task selection, model/evaluator invocation, or confirmation analysis.
"""
import hashlib,io,json,subprocess,tarfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE='0fe370b61c707d2325d4d05dfcdc62c75afe696f'
PINS={'results/v2_adapter/req019_executor_inventory_20260926/inventory.json':'91b8aea9af4126f915cbe83ff1eadb045ef62d89b5eeea0a7f828d212d0ba2d4','results/v2_adapter/req009_component_queue.json':'16d634965ee399a88f8b605778ed80dcaf2dc7b0bab4722d3fc0001a9bdfad07'}
def sha(b):return hashlib.sha256(b).hexdigest()
def scan(stream,needles,account,deadline,chunk=65536):
    overlap=max(map(len,needles),default=1)-1;tail=b'';found=set()
    while True:
        if time.monotonic()>deadline:raise TimeoutError('60-second audit cap')
        b=stream.read(chunk)
        if not b:break
        account[0]+=len(b)
        if account[0]>2*1024**3:raise ValueError('2GiB total read cap')
        v=tail+b;found.update(n.decode() for n in needles if n in v);tail=v[-overlap:] if overlap else b''
    return sorted(found)
def run():
    inputs={}
    for p,h in PINS.items():
        raw=(ROOT/p).read_bytes();assert sha(raw)==h,p;inputs[p]=json.loads(raw)
    inv=inputs[next(iter(PINS))]['exposure'];q=inputs[list(PINS)[1]]['queue'];excluded=set(inv['exclude_including_lead_rules'])
    candidates=[x for x in q if x not in excluded];assert len(candidates)==23
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    paths=subprocess.check_output(['git','diff','--name-only',BASE,head],cwd=ROOT,text=True).splitlines()
    needles=[x.encode() for x in candidates];hits={};scanned={};skipped={};count=[0];deadline=time.monotonic()+60
    for name in paths:
        p=ROOT/name
        if not p.is_file():skipped[name]='absent';continue
        if 'confirm' in name.lower() or name.startswith('results/code_routing/'):
            skipped[name]='explicit held confirmation/old routing archive exclusion';continue
        if p.suffix not in ('.json','.jsonl','.md','.py','.txt','.toml','.yaml','.yml') and not name.endswith('.tar.gz'):
            skipped[name]='unsupported binary format';continue
        scanned[name]=sha(p.read_bytes())
        if name.endswith('.tar.gz'):
            with tarfile.open(p,'r|gz') as t:
                for m in t:
                    if not m.isfile():continue
                    label=name+'::'+m.name
                    if 'confirm' in m.name.lower():skipped[label]='held confirmation member';continue
                    found=scan(t.extractfile(m),needles,count,deadline)
                    if found:hits[label]=found
        else:
            with p.open('rb') as f:found=scan(f,needles,count,deadline)
            if found:hits[name]=found
    return dict(base=BASE,head=head,script_sha256=sha(Path(__file__).read_bytes()),input_pins=PINS,
        previous_exclusions=len(excluded),remaining_queue=candidates,changed_records=len(paths),
        scanned_files=scanned,skipped=skipped,id_mentions=hits,bytes_read=count[0],
        selected_tasks=[],scope='tracked changed selected text and tar regular-member bytes; IDs only; no outcome JSON parsed',
        limitations=['Not a comprehensive claim of unexposed tasks. Untracked work/other hosts and unsupported binary/nested encodings not audited.','No claim about pretraining contamination. ID mentions require classification, not automatic exposure.','Task/image acquisition and model/evaluator execution remain held.'])
if __name__=='__main__':
    import sys
    out=Path(sys.argv[1]);result=run()
    with out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({k:result[k] for k in ('head','previous_exclusions','changed_records','bytes_read','id_mentions')}))
