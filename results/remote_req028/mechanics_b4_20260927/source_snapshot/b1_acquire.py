"""REQ028B1 one streamed pinned acquisition; one CPU process, no inference."""
import hashlib,json,os,resource,signal,struct,sys,time,urllib.error,urllib.request
from pathlib import Path
import gguf_meta,guard
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/remote_req028/b1_artifact_20260927'
ASSETS=ROOT.parent/'assets'
NAME='Klear-AgentForge-8B.Q4_K_M.gguf'
SIZE=5027783808
SHA='9c0909b89b518283ded8ca415694743bd922e8844356db4f26957e37047142ae'
REV='0626423882f502d6fe113bd0ddc61970b19d942b'
CANON='fa3d41e92e9ce7a5b4a52a3e7439aa00521f40c9'
URL='https://huggingface.co/mradermacher/Klear-AgentForge-8B-GGUF/resolve/'+REV+'/'+NAME
def write(name,data):
    with (OUT/name).open('x') as f:json.dump(data,f,indent=2,ensure_ascii=False)
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    return h.hexdigest()
def verify(path,size=SIZE,sha=SHA):
    assert path.stat().st_size==size,'size mismatch'
    assert digest(path)==sha,'hash mismatch'
def capacity(sample,remaining,deadline,now):
    assert now<deadline,'deadline'
    assert sample['pressure_level']==1 and sample['free_percent']>=20 and not sample['foreign_inference'],'resource admission'
    assert sample['disk_free_bytes']-remaining>=12*1024**3,'disk admission'
def acquire(final,partial,opener,deadline,now=time.time,sleep=time.sleep,size=SIZE,sha=SHA,progress=lambda *x:None):
    if final.exists():verify(final,size,sha);return {'reused':True,'network_bytes':0}
    assert not partial.exists(),'partial exists: no duplicate attempt or renewal'
    assert now()<deadline,'deadline'
    received=0;h=hashlib.sha256();began=now()
    with partial.open('xb') as f:
        with opener() as response:
            while True:
                assert now()<deadline,'deadline'
                delay=(received+256*1024)/(20*1024**2)-(now()-began)
                if delay>0:sleep(delay)
                b=response.read(min(256*1024,size-received+1))
                if not b:break
                received+=len(b);assert received<=size,'size overflow'
                f.write(b);h.update(b);progress(received,now())
    assert received==size,'size mismatch'
    assert h.hexdigest()==sha,'hash mismatch'
    partial.rename(final)
    return {'reused':False,'network_bytes':received,'sha256':h.hexdigest(),'bytes':received,'seconds':now()-began}
def inventory(path):
    # Extend the existing metadata-only reader: never map or load tensor data.
    with path.open('rb') as f:
        def u(fmt):
            size=struct.calcsize('<'+fmt);data=f.read(size);assert len(data)==size
            return struct.unpack('<'+fmt,data)[0]
        def string():
            n=u('Q');assert n<=32*1024**2
            b=f.read(n);assert len(b)==n
            return b.decode('utf-8')
        formats={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
        def val(k):
            if k in formats:return u(formats[k])
            if k==8:return string()
            if k==9:
                subtype=u('I');n=u('Q');assert n<=2000000
                return [val(subtype) for _ in range(n)]
            raise ValueError('GGUF type')
        assert f.read(4)==b'GGUF';version=u('I');nt=u('Q');nm=u('Q')
        assert nt<100000 and nm<10000
        metadata={}
        for _ in range(nm):key=string();metadata[key]=val(u('I'))
        tensors=[]
        for _ in range(nt):
            name=string();nd=u('I');assert nd<=8
            dims=[u('Q') for _ in range(nd)]
            tensors.append({'name':name,'dimensions':dims,'ggml_type':u('I'),'offset':u('Q')})
        return metadata,tensors,f.tell()
def main():
    resource.setrlimit(resource.RLIMIT_CPU,(1200,1200))
    until=time.time()+5
    while not (OUT/'ownership.json').exists() and time.time()<until:time.sleep(.02)
    record=json.loads((OUT/'ownership.json').read_text());deadline=record['deadline']
    def timeout(*args):raise TimeoutError('B1 deadline')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(max(1,int(deadline-time.time())))
    status='FAILED';download={};network=0
    try:
        ready=OUT/'watchdog_ready.json'
        until=time.time()+5
        while not ready.exists() and time.time()<until:time.sleep(.05)
        assert ready.exists() and json.loads(ready.read_text())['owned_identity_verified'],'watchdog handshake'
        os.kill(json.loads(ready.read_text())['pid'],0)
        capacity(guard.sample(os.getpgrp()),5*1024**3,deadline,time.time())
        def progress(n,t):
            temp=OUT/'progress.next';temp.write_text(json.dumps({'stage':'DOWNLOADING','received_bytes':n,'time':t}));temp.replace(OUT/'progress.json')
        download=acquire(ASSETS/NAME,ASSETS/(NAME+'.partial'),lambda:urllib.request.urlopen(URL,timeout=30),deadline,progress=progress)
        network=download['network_bytes'];write('integrity.json',dict(download,expected_bytes=SIZE,expected_sha256=SHA,pinned_url=URL))
        metadata=gguf_meta.read(ASSETS/NAME);write('gguf_metadata_summary.json',metadata)
        full,tensors,header_bytes=inventory(ASSETS/NAME)
        write('gguf_metadata_full.json',full);write('tensor_inventory.json',{'header_bytes':header_bytes,'tensors':tensors})
        text=full.get('tokenizer.chat_template','');(OUT/'chat_template.jinja').write_text(text)
        canonical=OUT/'canonical';canonical.mkdir();receipts=[];metadata_bytes=0
        urls=[('community_README.md','https://huggingface.co/mradermacher/Klear-AgentForge-8B-GGUF/resolve/'+REV+'/README.md')]
        urls += [(n,'https://huggingface.co/Kwai-Klear/Klear-AgentForge-8B/resolve/'+CANON+'/'+n) for n in ('config.json','tokenizer_config.json','tokenizer.json','special_tokens_map.json','README.md','LICENSE')]
        for name,url in urls:
            assert time.time()<deadline,'deadline'
            try:
                with urllib.request.urlopen(url,timeout=30) as response:
                    with (canonical/name).open('xb') as dest:
                        h=hashlib.sha256();n=0;began=time.time()
                        while True:
                            delay=(n+256*1024)/(20*1024**2)-(time.time()-began)
                            if delay>0:time.sleep(delay)
                            b=response.read(256*1024)
                            if not b:break
                            n+=len(b);network+=len(b);metadata_bytes+=len(b)
                            assert metadata_bytes<=30*1024**2 and network<=6*1024**3,'network cap'
                            dest.write(b);h.update(b)
                receipts.append({'file':name,'url':url,'bytes':n,'sha256':h.hexdigest(),'status':'downloaded'})
            except urllib.error.HTTPError as e:
                if e.code!=404:raise
                receipts.append({'file':name,'url':url,'status':'missing_404'})
        write('metadata_sources.json',receipts)
        card_receipt=json.loads((ROOT/'docs/audits/req028_b1_source_receipt_20260927.json').read_text())
        assert digest(canonical/'community_README.md')==card_receipt['sha256'],'publisher card hash mismatch'
        config=json.loads((canonical/'config.json').read_text());tc=json.loads((canonical/'tokenizer_config.json').read_text());tj=json.loads((canonical/'tokenizer.json').read_text())
        arch=full['general.architecture'];layers=full[arch+'.block_count'];kv=full[arch+'.attention.head_count_kv'];heads=full[arch+'.attention.head_count'];dim=full[arch+'.embedding_length']//heads
        comparisons=[]
        for key,canonical_key in [('block_count','num_hidden_layers'),('embedding_length','hidden_size'),('attention.head_count','num_attention_heads'),('attention.head_count_kv','num_key_value_heads'),('context_length','max_position_embeddings')]:
            a=full.get(arch+'.'+key);b=config.get(canonical_key);comparisons.append({'field':key,'gguf':a,'canonical':b,'exact_match':a==b})
        vocab=full.get('tokenizer.ggml.tokens',[]);cv=tj.get('model',{}).get('vocab',{});vocab_matches=sum(1 for token,i in cv.items() if i<len(vocab) and vocab[i]==token)
        ct=tc.get('chat_template');template_match=isinstance(ct,str) and ct==text
        nominal=layers*2*32768*kv*dim*34/32
        write('comparison.json',{'architecture':arch,'canonical_model_type':config.get('model_type'),'fields':comparisons,'head_dim':dim,'gguf_vocab_length':len(vocab),'canonical_base_vocab_length':len(cv),'canonical_base_vocab_id_string_matches':vocab_matches,'gguf_tokenizer_metadata':{k:v for k,v in metadata.items() if k.startswith('tokenizer.')},'canonical_special_tokens':{k:v for k,v in tc.items() if 'token' in k and k not in ('added_tokens_decoder',)},'canonical_added_tokens':tj.get('added_tokens',[]),'chat_template_exact_match':template_match,'gguf_template_sha256':hashlib.sha256(text.encode()).hexdigest(),'canonical_template_sha256':hashlib.sha256(ct.encode()).hexdigest() if isinstance(ct,str) else None,'actual_weight_file_bytes':SIZE,'nominal_q8_32k_kv_bytes':nominal,'nominal_weight_plus_kv_bytes':SIZE+nominal,'compute_runtime_system_reserve':'unmeasured; not included in lower-bound sum','weight_converter_provenance':'unverified; no canonical score transfer'})
        status='COMPLETE'
    except BaseException as e:write('failure.json',{'type':type(e).__name__,'message':str(e),'time':time.time()})
    finally:
        signal.alarm(0)
        if (OUT/'progress.json').exists():network=max(network,json.loads((OUT/'progress.json').read_text())['received_bytes'])
        write('status.json',{'status':status,'finished':time.time(),'network_payload_bytes':network,'partial_retained':(ASSETS/(NAME+'.partial')).exists(),'no_inference':True})
        write('sha256.json',{str(p.relative_to(OUT)):digest(p) for p in OUT.rglob('*') if p.is_file() and p.name not in ('sha256.json','samples.jsonl','supervisor.log','worker.log','exit.json')})
    return 0 if status=='COMPLETE' else 1
if __name__=='__main__':sys.exit(main())
