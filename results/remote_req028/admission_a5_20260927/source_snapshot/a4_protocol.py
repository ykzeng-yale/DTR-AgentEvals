"""A4 prompt binding and bounded recovery. No model generation here."""
import hashlib,json
import guard
from admission_window import reason as admission_reason
SYSTEM="Follow the user's formatting instructions exactly."
SHORT=["Reply with exactly the text DTR_READY and nothing else.","Return exactly one fenced code block labelled mswea_bash_command containing the command printf DTR_READY. Do not add any other text."]
LITERAL="Neutral calibration text. "
SUFFIX="\nReply with exactly DTR_READY and nothing else."
def request(token,user):
    return {'model':token,'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':user}],'temperature':0,'seed':20260927028,'max_tokens':128,'stream':False,'cache_prompt':False,'timings_per_token':True}
def call_indices(cycle):return (0,1) if cycle==0 else (2,3,4,5)
def minimum_repetitions(target,count):
    lo=0;hi=1
    while count(hi)<target:
        lo=hi;hi*=2
        assert hi<=32768,'cannot bracket token target'
    while lo+1<hi:
        mid=(lo+hi)//2
        if count(mid)>=target:hi=mid
        else:lo=mid
    assert count(hi-1)<target<=count(hi)<=target+64
    assert count(hi)+128<=32768
    return hi
def freeze_prompts(token,http,out):
    calls=[request(token,SHORT[i%2]) for i in range(4)]
    def render(body):
        rendered=http('/apply-template',body)['prompt']
        ids=http('/tokenize',{'content':rendered,'add_special':True,'parse_special':True,'with_pieces':False})['tokens']
        assert isinstance(rendered,str) and all(isinstance(x,int) for x in ids)
        return rendered,ids
    searches=[]
    for target in (8192,24576):
        memo={}
        def count(n):
            if n not in memo:
                rendered,ids=render(request(token,LITERAL*n+SUFFIX))
                memo[n]=len(ids)
            return memo[n]
        n=minimum_repetitions(target,count)
        # Monotonic search for this fixed repeated literal; retain every exact
        # query and verify ordering and adjacent boundary, not character counts.
        pairs=sorted(memo.items())
        assert all(b[1]>=a[1] for a,b in zip(pairs,pairs[1:]))
        searches.append({'target':target,'repetitions':n,'predecessor_tokens':memo[n-1],'queries':pairs,'method':'exact-token monotonic binary search with adjacent boundary verification'})
        calls.append(request(token,LITERAL*n+SUFFIX))
    bindings=[]
    for index,body in enumerate(calls):
        rendered,ids=render(body)
        if index>=4:
            target=(8192,24576)[index-4]
            assert target<=len(ids)<=target+64 and len(ids)+128<=32768
        artifact={'call':index+1,'request':body,'rendered':rendered,'token_ids':ids}
        with (out/('prompt_'+str(index+1)+'.json')).open('x') as f:json.dump(artifact,f,indent=2)
        bindings.append({'call':index+1,'rendered_tokens':len(ids),'rendered_sha256':hashlib.sha256(rendered.encode()).hexdigest(),'user_sha256':hashlib.sha256(body['messages'][1]['content'].encode()).hexdigest(),'token_ids_sha256':hashlib.sha256(json.dumps(ids).encode()).hexdigest(),'search':searches[index-4] if index>=4 else None})
    return calls,bindings
def recover(sample,now,sleep,observe,deadline,swap_baseline):
    previous=None
    while now()<deadline:
        s=sample()
        fatal=guard.violation(s,swap_baseline,float('inf'))
        failure=admission_reason(s)
        observe(s,fatal or failure,'scheduled')
        if fatal:raise RuntimeError('recovery resource violation: '+fatal)
        instant=now()
        if failure:previous=None
        elif previous is None:previous=instant
        elif instant-previous>=15:
            final=sample();fatal=guard.violation(final,swap_baseline,float('inf'));failure=admission_reason(final)
            observe(final,fatal or failure,'final_recheck')
            if fatal:raise RuntimeError('recovery resource violation: '+fatal)
            if not failure and now()<deadline:return
            previous=None
        remaining=deadline-now()
        if remaining<=0:break
        sleep(min(15,remaining))
    raise TimeoutError('restart recovery deadline')
