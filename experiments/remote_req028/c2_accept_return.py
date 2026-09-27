"""One-shot C2 return-leg acceptance, exact allowlist, no dispatch callback."""
import json,resource,time
from pathlib import Path
import sys
ROOT=Path.cwd()
sys.path.insert(0,str(ROOT/'experiments/remote_req028'))
from c2_git import GitTransport
from c2_relay import FileStore,Relay,sha,validate_request,validate_response
REQUEST_COMMIT='2cebde34d1b498ea90ba9442c171c07604cdd43b'
RESPONSE_COMMIT='ac1cb928c807df768454df3e190d7f6ff25eb67f'
REQUEST_PATH='results/remote_req028/c2_setup_verified_20260927/request.json'
RESPONSE_PATH='results/remote_req028/c2_lead_exchange_20260927/response.json'
REQUEST_SHA='2c546d276ad0c9d50b66e6066472991d3c0fb63bcbd078da6c1dde1c73750f83'
RESPONSE_SHA='8b230faa3813dc65928ae31dcecf75c0c7ea3aa6af88474fb2954f61cb0e1117'
OUT=ROOT/'results/remote_req028/c2_return_acceptance_20260927'
assert not OUT.exists(),'immutable return-leg already exists'
resource.setrlimit(resource.RLIMIT_CPU,(300,300))
start=time.time();events=[]
transport=GitTransport(ROOT,record=events.append)
fetched_main=transport.fetch_main()
request=transport.read_object(REQUEST_COMMIT,REQUEST_PATH)
response=transport.read_object(RESPONSE_COMMIT,RESPONSE_PATH)
read_finished=time.time()
assert sha(request)==REQUEST_SHA and sha(response)==RESPONSE_SHA
req=validate_request(request,time.time())
assert req['run_id']=='req028-c2-20260927' and req['request_id']=='req028-c2-20260927-1' and req['sequence']==1
assert req['body']=='DTR_C2_NONCE_20260927' and req['config_sha256']==sha(b'fixture-only-v1')
assert req['expires_at']=='2026-09-27T08:30:00Z'
resp=validate_response(response,req,REQUEST_COMMIT,time.time())
assert resp['status']=='ok' and resp['response']=='DTR_C2_ACK:DTR_C2_NONCE_20260927'
OUT.mkdir(parents=True,exist_ok=False)
store=FileStore(OUT/'journal');relay=Relay(store.read,store.write_exclusive,time.time)
accept_started=time.time()
accepted=relay.accept_response(response,request,REQUEST_COMMIT)
accepted_finished=time.time()
assert accepted==response
journal_name='req028-c2-20260927/1.accepted.json'
before=(OUT/'journal'/journal_name).stat()
duplicate=relay.accept_response(response,request,REQUEST_COMMIT)
after=(OUT/'journal'/journal_name).stat()
assert duplicate==response and before.st_mtime_ns==after.st_mtime_ns and before.st_ino==after.st_ino
assert store.write_exclusive('req028-c2-20260927/1.acceptance.seal',RESPONSE_SHA.encode())
with (OUT/'request.object.json').open('xb') as f:f.write(request)
with (OUT/'response.object.json').open('xb') as f:f.write(response)
receipt={'status':'ACCEPTED','synthetic_only':True,'request_commit':REQUEST_COMMIT,'request_path':REQUEST_PATH,'request_sha256':sha(request),'response_commit':RESPONSE_COMMIT,'response_path':RESPONSE_PATH,'response_sha256':sha(response),'fetched_main':fetched_main,'expires_at':req['expires_at'],'started':start,'reads_finished':read_finished,'accept_started':accept_started,'accept_finished':accepted_finished,'local_queue_seconds':accept_started-read_finished,'response_age_at_accept_seconds':accept_started-resp['receipt_time'],'response_age_interpretation':'wall age includes lead publication/coordination/network delay, not pure network latency','acceptance_seconds':accepted_finished-accept_started,'fetch_and_object_events':events,'persistent_acceptance_records':1,'duplicate_local_read_idempotent':True,'dispatch_callbacks':0,'model_loads':0,'commands_executed':0,'worker_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'publication_phase':'not yet started; separate later receipt','source_hashes':{n:sha((ROOT/'experiments/remote_req028'/n).read_bytes()) for n in ('c2_relay.py','c2_git.py')}}
with (OUT/'acceptance.json').open('x') as f:json.dump(receipt,f,indent=2)
with (OUT/'sha256.json').open('x') as f:json.dump({str(p.relative_to(OUT)):sha(p.read_bytes()) for p in OUT.rglob('*') if p.is_file() and p.name!='sha256.json'},f,indent=2)
print(json.dumps(receipt,indent=2))
