"""REQ-029K bounded byte-only input scan. Never execute record instructions."""
import gzip,hashlib,io,json,os,re,resource,stat,subprocess,tarfile,time
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'results/remote_req028'
PINS={
'results/v2_adapter/req019_executor_inventory_20260926/inventory.json':'91b8aea9af4126f915cbe83ff1eadb045ef62d89b5eeea0a7f828d212d0ba2d4',
'results/v2_adapter/req009_component_queue.json':'16d634965ee399a88f8b605778ed80dcaf2dc7b0bab4722d3fc0001a9bdfad07',
'docs/source_snapshots/req029j_prompt/public_task.json':'7affd4e265f74b40093ea0caa4c2a17f12c2516540fa66cf14c521aabf001320'}
MECHANICS=['mechanics'+x+'_20260927' for x in ('','_a2','_a2r','_a4','_a5','_a6','_a6r','_b2','_b2r','_b3','_b4','_c0')]
ROOTS=MECHANICS+['launch_c0_20260927','c5_request_20260927','c5_execution_20260927','c6_runs','c6_runtime']
ARCHIVES=['c6_terminal_20260927_a/runtime_evidence.tar.gz','c6_terminal_20260927_b/runtime_evidence.tar.gz',
    'c5_terminal_20260927/execution_evidence.tar.gz','c5_terminal_20260927/complete_execution.tar.gz']
SKIP_PARTS={'source_snapshot','source_snapshots','.git','fixtures','tests','test','__pycache__','runner_template_trace',
    'source','raw','response','responses','observation','observations','sandbox','admission_samples','git-operations',
    'attestation-process','supervision','admission','network'}
ID_PATTERN=re.compile(rb'(?<![A-Za-z0-9_.-])([A-Za-z0-9_.-]{1,60}__[A-Za-z0-9_.-]{1,60}-[0-9]{1,12})(?![A-Za-z0-9_.-])')
def sha(raw):return hashlib.sha256(raw).hexdigest()
class Cap(Exception):pass
class Budget:
    def __init__(self,seconds=60,read_cap=2*1024**3,clock=time.monotonic):
        self.clock=clock;self.start=clock();self.deadline=self.start+seconds
        self.read_cap=read_cap;self.bytes=0;self.peak_rss=0;self.categories={}
    def check(self):
        if self.clock()>=self.deadline:raise Cap('scan deadline')
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if os.uname().sysname!='Darwin':rss*=1024
        self.peak_rss=max(self.peak_rss,rss)
        if rss>2*1024**3:raise Cap('2GiB sampled self RSS')
    def read(self,f,n,category):
        self.check();remaining=self.read_cap-self.bytes
        if remaining<=0:raise Cap('2GiB aggregate streamed read cap')
        raw=f.read(min(n,remaining))
        self.bytes+=len(raw);self.categories[category]=self.categories.get(category,0)+len(raw)
        self.check();return raw
class Counted:
    def __init__(self,f,budget,category):
        self.f=f;self.budget=budget;self.category=category;self.hash=hashlib.sha256();self.bytes=0
    def read(self,n=-1):
        if n<0:n=65536
        raw=self.budget.read(self.f,n,self.category);self.hash.update(raw);self.bytes+=len(raw);return raw
def read_small(path,budget,cap=2*1024**2):
    if path.is_symlink() or not path.is_file():raise ValueError('nonregular input: '+str(path))
    if path.stat().st_size>cap:raise ValueError('metadata record cap')
    with path.open('rb') as f:
        data=bytearray()
        while True:
            b=budget.read(f,65536,'pinned_or_provenance')
            if not b:break
            data.extend(b)
    return bytes(data)
def markers(ids,problem):
    items={}
    def add(raw,label):
        if not raw:return
        items.setdefault(raw,[]).append(label)
    for t in ids:add(t.encode(),'task-id:'+t)
    p=problem.encode()
    middle=max(0,(len(p)-128)//2)
    for name,raw in [('full',p),('first128',p[:128]),('middle128',p[middle:middle+128]),('last128',p[-128:])]:
        add(raw,'django:'+name+':raw-utf8')
        # Exact byte substrings may bisect UTF8; no replacement/normalization.
        # Only valid UTF8 substrings have JSON-string encodings.
        try:text=raw.decode('utf-8')
        except UnicodeDecodeError:continue
        for ascii_flag in (True,False):
            add(json.dumps(text,ensure_ascii=ascii_flag)[1:-1].encode(),'django:'+name+':json-ascii-'+str(ascii_flag).lower())
    out=[]
    for raw,labels in items.items():
        out.append(dict(id='m%03d'%(len(out)+1),sha256=sha(raw),bytes=len(raw),labels=labels,needle=raw))
    return out
def scan(stream,ms,budget,chunk=65536,category='selected_input'):
    tail=b'';offset=0;hits={};ids=set();h=hashlib.sha256();sample=bytearray()
    overlap=max(160,max((len(m['needle']) for m in ms),default=1)-1)
    while True:
        b=budget.read(stream,chunk,category)
        if not b:break
        h.update(b)
        if sample is not None:
            if len(sample)+len(b)<=2*1024**2:sample.extend(b)
            else:sample=None
        v=tail+b
        for m in ms:
            i=v.find(m['needle'])
            if i>=0 and m['id'] not in hits:hits[m['id']]=offset-len(tail)+i
        # Do not record an identifier truncated at a chunk's temporary EOF.
        ids.update(m[1].decode() for m in ID_PATTERN.finditer(v) if m.end()<len(v))
        offset+=len(b);tail=v[-overlap:]
    ids.update(x.decode() for x in ID_PATTERN.findall(tail))
    metadata={};message_sha=None;has_messages=False
    if sample is not None:
        try:
            x=json.loads(sample)
            if isinstance(x,dict):
                for k in ('task','task_id','instance_id','run_id','request_id','request','source_commit','frozen_at','sequence','messages_sha256','operation','endpoint'):
                    if k in x and isinstance(x[k],(str,int,float,bool,type(None))):metadata[k]=x[k]
                body=x.get('body',x)
                if isinstance(body,dict) and isinstance(body.get('messages'),list):
                    has_messages=True
                    message_sha=sha(json.dumps(body['messages'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())
        except (ValueError,TypeError):pass
    return dict(sha256=h.hexdigest(),bytes=offset,marker_matches=[dict(marker_id=k,first_byte_offset=v) for k,v in sorted(hits.items())],
        canonical_id_mentions=sorted(ids),request_metadata=metadata,has_message_array=has_messages,
        canonical_json_messages_sha256=message_sha,json_projection_available=sample is not None)
def canonical(name):
    parts=PurePosixPath(name).parts
    if name.startswith('/') or '..' in parts:return None
    if parts[:2]==('results','remote_req028'):parts=parts[2:]
    return '/'.join(parts)
def selected(name):
    name=canonical(name)
    if not name:return False
    parts=PurePosixPath(name).parts
    if not parts or parts[0] not in ROOTS or any(p in SKIP_PARTS or 'confirm' in p.lower() for p in parts):return False
    f=parts[-1];top=parts[0]
    if top in MECHANICS:
        return bool(
            re.fullmatch(r'call_[0-9]+\.request\.json',f) or re.fullmatch(r'prompt_[0-9]+\.json',f) or
            f in ('manifest.json','prompt_manifest.json','frozen_prompt_source.json','frozen_message_binding.json','native_template_binding.json'))
    if top=='launch_c0_20260927':return f=='frozen_prompt.json'
    if top=='c5_request_20260927':return f=='request.json'
    if top=='c5_execution_20260927':
        return f in ('request.json','native_binding.json','native_approval.json') or ('http' in parts and f.endswith('.input.json'))
    if top=='c6_runs':return 'request' in parts and f.endswith('.json')
    if top=='c6_runtime':
        return ('http' in parts and f.endswith('.input.json')) or ('native' in parts and f.endswith('.json')) or ('request' in parts and f.endswith('.json'))
    return False
def provenance_path(top,name):
    if top not in ROOTS and not top.startswith(('launch_','c5_launch_','c5_terminal_','c6_launch_','c6_terminal_','admitted_execution_')):return False
    return name in ('launch.json','launch.claim.json','launch_receipt.json','program.json','program_window.json',
        'execution_window.json','terminal_receipt.json','receipt.json','evidence_manifest.json')
def walk(root,budget,gaps=None):
    for current,dirs,files in os.walk(root,followlinks=False):
        budget.check()
        if gaps is not None:
            for d in dirs:
                if (Path(current)/d).is_symlink():gaps.append(dict(path=str(Path(current)/d),reason='symlink directory not followed'))
        dirs[:]=sorted(d for d in dirs if d not in SKIP_PARTS and 'confirm' not in d.lower() and not (Path(current)/d).is_symlink())
        for name in sorted(files):yield Path(current)/name
def run(root=ROOT):
    root=Path(root);base=root/'results/remote_req028';b=Budget();records={};gaps=[];provenance={};excluded={};archives={};pins={}
    started=time.time();completed=False;pending=[]
    try:
        for name,pin in PINS.items():
            raw=read_small(root/name,b);assert sha(raw)==pin,'pinned input mismatch: '+name;pins[name]=json.loads(raw)
        inv=pins[next(iter(PINS))]['exposure'];q=pins[list(PINS)[1]]['queue']
        exclusions=inv['exclude_including_lead_rules'];remaining=[x for x in q if x not in set(exclusions)]
        assert len(exclusions)==len(set(exclusions))==89 and len(remaining)==23
        assert remaining==inv['req009_design_queue_remaining_unexposed']
        public=pins[list(PINS)[2]];ms=markers(remaining,public['problem_statement'])
        # If a byte window splits UTF8, retain its exact raw marker and explicitly
        # report the unavailable JSON form rather than silently normalizing it.
        public_bytes=public['problem_statement'].encode();middle=max(0,(len(public_bytes)-128)//2)
        for label,window in [('first128',public_bytes[:128]),('middle128',public_bytes[middle:middle+128]),('last128',public_bytes[-128:])]:
            try:window.decode('utf-8')
            except UnicodeDecodeError:gaps.append(dict(marker=label,reason='128-byte UTF8 window splits codepoint; JSON-string forms unavailable, raw marker retained'))
        # Git index path metadata only, never Git object content.
        tracked=set(subprocess.check_output(['git','ls-files','--','results/remote_req028'],cwd=root,text=True,timeout=3).splitlines())
        tops=sorted(p for p in base.iterdir() if p.is_dir() and not p.is_symlink())
        for top in tops:
            b.check()
            if top.name not in ROOTS:excluded[top.name]='not selected actual-input root; fixtures/setup/evaluator/source or receipt-only provenance'
            if top.name.startswith('mechanics') and top.name not in ROOTS:
                gaps.append(dict(root=top.name,reason='unresolved additional mechanics root; not in reviewed scope inventory'))
            for p in sorted(top.iterdir()):
                if p.is_file() and provenance_path(top.name,p.name):
                    raw=read_small(p,b);x=json.loads(raw)
                    keys=('run_id','source_commit','release_commit','release_sha256','stage','runtime_path','runtime_root',
                        'command','argv','identity','archive','archive_sha256','archive_bytes','included_files','excluded_reconstructible_git_object_cache')
                    provenance[str(p.relative_to(root))]=dict(sha256=sha(raw),bytes=len(raw),projection={k:x[k] for k in keys if k in x})
        for top in ROOTS:
            p=base/top
            if not p.is_dir() or p.is_symlink():gaps.append(dict(root=top,reason='expected run/input root absent or symlink'));continue
            candidates=[]
            for path in walk(p,b,gaps):
                name=str(path.relative_to(base))
                if selected(name):candidates.append(path)
            if not candidates:gaps.append(dict(root=top,reason='no eligible input records discovered'))
            pending.extend(candidates)
        while pending:
            p=pending[0];name=str(p.relative_to(root));b.check()
            if p.is_symlink() or not p.is_file():
                gaps.append(dict(path=name,reason='nonregular/symlink selected input'));pending.pop(0);continue
            before=p.stat()
            with p.open('rb') as f:result=scan(f,ms,b)
            after=p.stat();result.update(storage='loose',tracked=name in tracked,root=str(p.relative_to(base)).split('/')[0])
            if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
                gaps.append(dict(path=name,reason='input changed during read'))
            records[name]=result;pending.pop(0)
        for archive_name in ARCHIVES:
            path=base/archive_name;label=str(path.relative_to(root))
            if not path.is_file() or path.is_symlink() or path.parent.is_symlink():gaps.append(dict(path=label,reason='expected archive missing/nonregular'));continue
            info=dict(bytes=path.stat().st_size,complete=False,selected_members=0,skipped_members=0,skipped_reason_counts={})
            archives[label]=info
            before=path.stat()
            with path.open('rb') as f:
                compressed=Counted(f,b,'archive_compressed')
                with gzip.GzipFile(fileobj=compressed,mode='rb') as gz:
                    decoded=Counted(gz,b,'archive_decoded')
                    with tarfile.open(fileobj=decoded,mode='r|') as tf:
                        for m in tf:
                            b.check()
                            if not m.isfile() or not selected(m.name):
                                info['skipped_members']+=1
                                reason='nonregular' if not m.isfile() else 'outside explicit input/member allowlist'
                                info['skipped_reason_counts'][reason]=info['skipped_reason_counts'].get(reason,0)+1
                                continue
                            result=scan(tf.extractfile(m),ms,b,category='archive_selected_member')
                            result.update(storage='archive_member',archive=label,member_path=m.name,root=canonical(m.name).split('/')[0])
                            records[label+'::'+m.name]=result;info['selected_members']+=1
                    # Consume gzip/tar padding so compressed SHA covers the whole file.
                    while decoded.read(65536):pass
                while compressed.read(65536):pass
                info.update(sha256=compressed.hash.hexdigest(),compressed_bytes_read=compressed.bytes,decoded_bytes=decoded.bytes,complete=True)
            after=path.stat()
            if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):gaps.append(dict(path=label,reason='archive changed during read'))
        completed=True
    except (Cap,ValueError,OSError,AssertionError,tarfile.TarError,subprocess.SubprocessError) as e:
        gaps.append(dict(reason=repr(e),pending_loose_records=[str(p.relative_to(root)) for p in pending]))
    groups={}
    for name,r in records.items():groups.setdefault(r['sha256'],[]).append(name)
    for name,r in records.items():
        r['duplicate_of']=next((n for n in groups[r['sha256']] if n!=name),None)
    root_inventory={}
    for top in ROOTS:
        rr={n:r for n,r in records.items() if r['root']==top}
        root_inventory[top]=dict(records=len(rr),loose_records=sum(r['storage']=='loose' for r in rr.values()),
            untracked_loose_records=sum(r['storage']=='loose' and not r['tracked'] for r in rr.values()),
            unique_record_hashes=len({r['sha256'] for r in rr.values()}),
            canonical_id_mentions=sorted({t for r in rr.values() for t in r['canonical_id_mentions']}),
            message_array_records=sum(r['has_message_array'] for r in rr.values()))
        if not root_inventory[top]['message_array_records']:
            gaps.append(dict(root=top,reason='no direct message-array record; planned/binding-only records do not prove complete dispatched history'))
    return dict(request='REQ-029K',started=started,finished=time.time(),scan_elapsed_seconds=b.clock()-b.start,
        bytes_read=b.bytes,read_categories=b.categories,peak_sampled_rss=b.peak_rss,input_pins=PINS,
        previous_exclusions=locals().get('exclusions'),remaining_queue=locals().get('remaining'),
        marker_definitions=[{k:v for k,v in m.items() if k!='needle'} for m in locals().get('ms',[])],
        records=records,root_inventory=root_inventory,provenance=provenance,archives=archives,excluded_roots=excluded,gaps=gaps,
        scan_completed_within_scope=completed,universal_untouched_verdict=False,selected_tasks=[],
        limitations=['Byte exact raw UTF8 / JSON string escaped ensure_ascii true,false only; no Unicode normalization, whitespace rewriting, base64, UTF16, nested JSON escaping or compressed nested payload decoding.',
            'A missing canonical ID is not evidence of no exposure. Problem markers cover Django16560 only; other 22 issue texts were not supplied.',
            'Manifest/prompt/native binding records may be planned/tokenizer-only, not dispatched; marker hits require lead classification.',
            'No arbitrary home/assets/peer scan. Other-host v2_agent archives are not claimed as mini-origin runs; local lead reconciliation is separate.',
            'No evaluator/test/reference/outcome or held CONFIRM record parsing; excluded archive bodies are only streamed past for bounded archive traversal/hash, never matched or decoded as outcomes.',
            'Provenance projection reads only run/path/source/archive metadata. Archived/loose duplicates are byte hashes, not independent model calls.',
            'Unknown or missing historical roots and unavailable input histories remain gaps; absence never proves universal untouchedness.'])
if __name__=='__main__':
    import sys
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
    value=run()
    value['source_sha256']=sha(Path(__file__).read_bytes())
    encoded=json.dumps(value,indent=2,sort_keys=True)+'\n'
    if len(encoded.encode())>99*1024**2:
        encoded=json.dumps(dict(request='REQ-029K',gaps=['100MiB result cap; full scan result not retained'],
            universal_untouched_verdict=False,scan_completed_within_scope=False))+'\n'
    with (out/'scan.json').open('x') as f:f.write(encoded)
    assert sum(p.stat().st_size for p in out.rglob('*') if p.is_file())<100*1024**2
    print(json.dumps({k:value[k] for k in ('scan_elapsed_seconds','bytes_read','peak_sampled_rss','scan_completed_within_scope','gaps')}))
