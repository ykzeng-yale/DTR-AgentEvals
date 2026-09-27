"""Four fixed-root provenance supplement; never execute archived sources."""
import ast,json,re,sys,time
from pathlib import Path
from exposure_reconcile_scan import ROOT,BASE,Budget,read_small,sha
CASES={
'mechanics_a2_20260927':'mechanics_followup.py',
'mechanics_a6_20260927':'mechanics_a6.py',
'mechanics_b2_20260927':'mechanics_b2.py',
'mechanics_b2r_20260927':'mechanics_b2r.py'}
def fingerprint(messages):
    return sha(json.dumps(messages,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())
def synthetic(messages):
    if len(messages)!=2:return False
    if messages[0]!={'role':'system','content':"Follow the user's formatting instructions exactly."}:return False
    if messages[1].get('role')!='user':return False
    text=messages[1].get('content','')
    return text in ('Reply with exactly the text DTR_READY and nothing else.',
        'Return exactly one fenced code block labelled mswea_bash_command containing the command printf DTR_READY. Do not add any other text.') or bool(
        re.fullmatch(r'(?:Neutral calibration text\. )+\nReply with exactly DTR_READY and nothing else\.',text))
def order_facts(raw):
    tree=ast.parse(raw);facts={}
    for n in ast.walk(tree):
        if not isinstance(n,ast.Call):continue
        text=ast.get_source_segment(raw.decode(),n) or ''
        if isinstance(n.func,ast.Name) and n.func.id=='write':
            if '.request.json' in text:facts.setdefault('request_write_lines',[]).append(n.lineno)
            if '.start.json' in text:facts.setdefault('start_write_lines',[]).append(n.lineno)
        if isinstance(n.func,ast.Name) and n.func.id=='http' and any(isinstance(a,ast.Constant) and a.value=='/v1/chat/completions' for a in n.args):
            facts.setdefault('generation_http_lines',[]).append(n.lineno)
    facts['request_and_start_writes_precede_generation']=bool(facts.get('generation_http_lines') and facts.get('request_write_lines') and
        facts.get('start_write_lines') and max(facts['request_write_lines']+facts['start_write_lines'])<min(facts['generation_http_lines']))
    return facts
def run(parent):
    prior=[json.loads(p.read_bytes()) for p in sorted(parent.glob('scan_*/scan.json'))]
    used_seconds=sum(x['scan_elapsed_seconds'] for x in prior);used_bytes=sum(x['bytes_read'] for x in prior)
    b=Budget(seconds=60-used_seconds,read_cap=2*1024**3-used_bytes);rows={};gaps=[]
    scanned=prior[-1]['records']
    existing={}
    for name,r in scanned.items():
        h=r.get('canonical_json_messages_sha256')
        if h:existing.setdefault(h,[]).append(dict(path=name,sha256=r['sha256']))
    try:
        for root,source in CASES.items():
            directory=BASE/root
            raw=read_small(directory/'manifest.json',b);manifest=json.loads(raw);manifest_sha=sha(raw)
            statusraw=read_small(directory/'status.json',b);status=json.loads(statusraw)
            failure_raw=read_small(directory/'failure.json',b);failure=json.loads(failure_raw)
            sourcepath=directory/'source_snapshot'/source;source_raw=read_small(sourcepath,b)
            assert sha(source_raw)==manifest['source_hashes'][source]
            assert status['manifest_sha256']==manifest_sha
            flow=order_facts(source_raw)
            entries=[]
            for index,request in enumerate(manifest.get('requests',manifest.get('request_plan',[])),1):
                m=request['messages'];h=fingerprint(m)
                entries.append(dict(planned_index=index,messages_sha256=h,synthetic_recipe_exact=synthetic(m),
                    message_bytes=[len(x['content'].encode()) for x in m],matching_already_scanned_message_arrays=existing.get(h,[])))
            starts=sorted(p.name for p in directory.glob('call_*.start.json'))
            requests=sorted(p.name for p in directory.glob('call_*.request.json'))
            # Read only journal counters and infrastructure exception, no content,
            # usage, finish reasons, model-format scores, task outcomes or grading.
            rows[root]=dict(manifest_sha256=manifest_sha,status_sha256=sha(statusraw),failure_sha256=sha(failure_raw),
                source_path=str(sourcepath.relative_to(ROOT)),source_sha256=sha(source_raw),source_pin_matches=True,
                manifest_binding_matches=True,calls_recorded=status['calls_recorded'],call_journal_entries=len(status['calls']),
                call_start_files=starts,call_request_files=requests,pre_generation_failure=failure['exception'],
                source_order=flow,planned_inputs=entries,all_planned_inputs_exact_synthetic=all(x['synthetic_recipe_exact'] for x in entries),
                physical_generation_attempt_evidence='none recorded; pinned source writes request/start and appends call before generation HTTP',
                physical_generation_attempt_inference=False if status['calls_recorded']==0 and not status['calls'] and not starts and not requests and flow['request_and_start_writes_precede_generation'] else None,
                missing_history_not_reconstructed=True)
    except BaseException as e:gaps.append(repr(e))
    return dict(request='REQ-029K-four-root-supplement',rows=rows,gaps=gaps,seconds=b.clock()-b.start,
        bytes_read=b.bytes,peak_sampled_rss=b.peak_rss,cumulative_scan_seconds=used_seconds+b.clock()-b.start,
        cumulative_scan_bytes=used_bytes+b.bytes,scope='Only four named run manifests, launch counters/infrastructure failure and manifest-pinned driver source; no generation or outcome evaluation',
        interpretation='Separate retrospective no-attempt/source-plan evidence. Not fabricated input history, universal nonexposure or task-selection decision.')
if __name__=='__main__':
    path=Path(sys.argv[1]);value=run(path.parent)
    with path.open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({k:value[k] for k in ('seconds','bytes_read','cumulative_scan_seconds','cumulative_scan_bytes','gaps')}))
