"""Data-only exact C5 consumer with external provenance/attestation pins."""
import json
from c2_relay import encode,sha,require,digest,commit_id
from c3r_envelope import consume
from c5_contract import *
def consume_published(raw,object_identity,receipt_raw,receipt_pin,attestation_raw,attestation_pin,native_approval_raw,native_approval_pin,now,ledger=None):
    require(now<EXPIRY,'C5 response expired before any future action')
    require(sha(receipt_raw)==digest(receipt_pin),'publication provenance pin');receipt=json.loads(receipt_raw)
    require(set(receipt)=={'commit','path','sha256'} and receipt==object_identity,'publication object identity');commit_id(receipt['commit'])
    require(receipt['path']==RESPONSE_PATH and sha(raw)==receipt['sha256'],'exact response path/SHA')
    require(sha(attestation_raw)==digest(attestation_pin),'asset attestation pin');att=json.loads(attestation_raw)
    require(att['contract']==CONTRACT and att['contract_sha256']==CONFIG_SHA and att['source_verified_by_archive'] is True,'asset attestation contract')
    require(sha(native_approval_raw)==digest(native_approval_pin),'native approval pin');native=json.loads(native_approval_raw)
    expected=dict(verify_native(native_expected()),asset_attestation_sha256=attestation_pin,request_sha256=REQUEST_SHA,release_sha256=RELEASE_SHA,expires_at=EXPIRY)
    require(native==expected,'independent native/asset approval')
    q=request((ROOT/REQUEST_PATH).read_bytes(),(ROOT/RELEASE_PATH).read_bytes(),now)
    result=consume(raw,q,ENTRY,CONFIG_SHA,sha(encode(native_expected())))
    if ledger:require(ledger.write_exclusive('req028-c5-20260927/consumed.json',encode(receipt)),'already consumed')
    return result # no command/tool execution
