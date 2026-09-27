"""Single physical request, durable seal, bounded cleanup independent of audit IO."""
import json,time
from pathlib import Path
from c2_relay import encode,sha,require
from c3_adapter import PENDING,CONFIG_SHA
from c3r_envelope import build,consume
from c4_http import HTTP,body
from c4_git_handles import Handles
from c5_contract import *
class Execution:
    def __init__(self,root,life,transport,request_raw,manifest,attestation_sha):
        self.root=Path(root);self.life=life;self.transport=transport;self.request_raw=request_raw;self.manifest=manifest;self.attestation_sha=attestation_sha;self.http=HTTP(self.root/'http',life);self.git=Handles(self.root/'git-operations',transport);self.errors=[];self.physical=0;self.timings=[]
    def put(self,name,data):
        with (self.root/name).open('xb') as f:f.write(data if type(data) is bytes else encode(data));f.flush();import os;os.fsync(f.fileno())
    def best(self,name,data):
        try:self.put(name,data)
        except BaseException as e:self.errors.append({'path':name,'error':repr(e),'durable':False})
    def left(self,cap):
        left=min(cap,EXPIRY-time.time(),self.life.spec['phase_deadline']-time.time());require(left>0,'C5 deadline');return left
    def wait(self,h,label,cap):
        start=time.time();end=start+self.left(cap)
        try:
            while True:
                self.life.check();require(time.time()<end,label+' deadline');value=h.poll()
                if value is not PENDING:return value
                time.sleep(.01)
        except BaseException:
            try:h.cancel()
            except BaseException as e:self.errors.append({'cancellation':repr(e)})
            raise
        finally:self.timings.append({'phase':label,'started':start,'finished':time.time()})
    def run(self):
        q=request(self.request_raw,self.manifest,time.time());sealed=False;primary=None;cleanup=None;started=time.time()
        try:
            self.put('request.claim.json',{'request_sha256':REQUEST_SHA,'physical_call_cap':1,'no_retry':True})
            start=time.time();self.life.launch()
            while not self.life.health():time.sleep(.05)
            self.timings.append({'phase':'load_health','started':start,'finished':time.time()})
            # Read exact immutable request again inside the model-phase budget.
            e=self.transport.authorized['entry'];got=self.wait(self.git.begin_read(e['commit'],e['path'],self.left(30)),'network_read',30);require(got['raw']==self.request_raw,'request changed')
            binding=self.wait(self.http.begin_bind(q['messages'],self.left(180)),'native_binding',180)
            native=self.transport.approve_exact_native(binding,self.attestation_sha);self.put('native_approval.json',dict(native,asset_attestation_sha256=self.attestation_sha,request_sha256=REQUEST_SHA,release_sha256=RELEASE_SHA,expires_at=EXPIRY));self.put('native_binding.json',binding)
            self.put('physical_attempt.json',{'number':1,'started':time.time(),'no_retry':True});self.physical=1;request_start=time.time()
            raw=self.wait(self.http.begin_generate(body(q['messages']),self.left(180)),'request',180);request_end=time.time();self.put('raw_response.json',raw)
            parsed=json.loads(raw);require(parsed['usage']['prompt_tokens']==1530,'native usage mismatch');require(type(parsed['usage']['completion_tokens']) is int and 0<=parsed['usage']['completion_tokens']<=1536,'completion cap')
            self.put('terminal.json',{'usage':parsed['usage'],'finish_reason':parsed['choices'][0]['finish_reason'],'content':parsed['choices'][0]['message'].get('content'),'server_timings':parsed.get('timings',{})})
            from c0_protocol import analyze
            self.put('descriptive_interface_gate.json',analyze(parsed['choices'][0]['message'].get('content') or '',parsed['choices'][0]['finish_reason']))
            envelope=build(q,e,CONFIG_SHA,binding,raw,{'request_wall_seconds':request_end-request_start,'prefill_ms':parsed.get('timings',{}).get('prompt_ms'),'generation_ms':parsed.get('timings',{}).get('predicted_ms')})
            consume(envelope,q,e,CONFIG_SHA,sha(encode(native_expected())))
            self.put('response.json',envelope);self.put('response.seal',sha(envelope).encode());sealed=True
            publication=self.wait(self.git.begin_publish(1,envelope,self.left(30)),'network_publication',30);self.put('publication.json',publication)
            return envelope
        except BaseException as e:primary=repr(e);self.best('failure.json',{'primary':primary,'physical_attempts':self.physical,'sealed':sealed});raise
        finally:
            # Stop first, even when any receipt/audit write failed. Preserve primary.
            try:cleanup=self.life.stop()
            except BaseException as e:self.errors.append({'cleanup':repr(e)})
            for hook in (self.http,self.git):
                try:hook.close()
                except BaseException as e:self.errors.append({'hook_cleanup':repr(e)})
            self.best('execution_receipt.json',{'primary':primary,'physical_attempts':self.physical,'sealed':sealed,'cleanup':cleanup,'errors':self.errors,'timings':self.timings,'total_wall_seconds':time.time()-started,'nested_server_timings_not_additive':True})
            if primary is None:require(cleanup is not None and cleanup['cleanup']['owned_absent'] and not self.errors,'cleanup/audit failure')
