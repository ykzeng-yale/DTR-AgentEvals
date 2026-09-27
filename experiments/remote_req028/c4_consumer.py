"""Data-only consumer with independently pinned pre-generation binding approval."""
import json
from c2_relay import encode,decode,sha,digest,commit_id,path_component,require,number
from c3_adapter import CONFIG_SHA,CONTRACT,validate_release,validate_request
from c3r_envelope import consume as consume_response
APPROVAL_KEYS={'protocol','release_sha256','request_commit','request_path','request_sha256','config_sha256','binding_sha256','asset_attestation_sha256','expires_at'}
PROVENANCE_KEYS={'commit','path','sha256'}
def approve_binding(release_raw,release_pin,request_raw,entry,binding,asset_attestation_sha,now):
    release=validate_release(release_raw,release_pin,now);q=validate_request(request_raw,release,entry,now)
    require(entry in release['requests'],'request not approved')
    require(binding['template_sha256']==CONTRACT['template_sha256'] and binding['native_exact'] is True,'native binding')
    require(type(binding['token_ids']) is list and all(type(i) is int for i in binding['token_ids']) and 0<len(binding['token_ids'])<=32768-1536,'token budget')
    return encode({'protocol':3,'release_sha256':release_pin,'request_commit':entry['commit'],'request_path':entry['path'],'request_sha256':sha(request_raw),'config_sha256':CONFIG_SHA,'binding_sha256':sha(encode(binding)),'asset_attestation_sha256':digest(asset_attestation_sha),'expires_at':q['expires_at']})
def consume(raw,provenance,provenance_raw,provenance_pin,request_raw,release_raw,release_pin,entry,approval_raw,approval_pin,asset_attestation_pin,now,ledger=None):
    # Pins are caller inputs, not copied out of the response. Provenance must be
    # supplied by the immutable-object fetch and independently approved receipt.
    require(sha(provenance_raw)==digest(provenance_pin),'response provenance pin')
    approved_provenance=decode(provenance_raw,PROVENANCE_KEYS)
    require(provenance==approved_provenance,'response object identity')
    commit_id(provenance['commit']);path_component(provenance['path'])
    require(provenance['path'].startswith('results/remote_req028/c3_'),'unowned response path')
    require(sha(raw)==digest(provenance['sha256']),'response object SHA')
    require(sha(approval_raw)==digest(approval_pin),'native approval pin')
    a=decode(approval_raw,APPROVAL_KEYS);require(type(a['protocol']) is int and a['protocol']==3,'approval protocol')
    release=validate_release(release_raw,release_pin,now);require(entry in release['requests'],'unapproved request entry')
    q=validate_request(request_raw,release,entry,now)
    expected={'release_sha256':release_pin,'request_commit':entry['commit'],'request_path':entry['path'],'request_sha256':sha(request_raw),'config_sha256':CONFIG_SHA,'asset_attestation_sha256':digest(asset_attestation_pin),'expires_at':q['expires_at']}
    for key,value in expected.items():require(a[key]==value,'native approval '+key)
    number(a['expires_at']);require(now<a['expires_at'],'expired native approval')
    result=consume_response(raw,q,entry,CONFIG_SHA,digest(a['binding_sha256']))
    if ledger is not None:
        require(ledger.write_exclusive(q['run_id']+'/consumed_'+str(q['sequence'])+'.json',encode(provenance)),'response already consumed')
    return result # DATA ONLY, no command/tool execution path
