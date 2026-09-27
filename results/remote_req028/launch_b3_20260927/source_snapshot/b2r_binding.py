"""Accept only the released exact raw/served native-template byte pair."""
import hashlib,json,tarfile
RAW_SHA='f858b0b34b6c89118490c6c087cbbc5df911f56994cc8cb61ee7a619903abcd8'
SERVED_SHA='f2850fd92c68d5375344b9e09b551e3bbc3124b56f8ca58e468b2c91179bdb51'
TRACE={
'common/jinja/lexer.cpp':('3d6774bc2dac477e10ddbee69eff403df36f5925c8512ccf8a249bde5c26dbd7',[(53,58),(338,338)]),
'common/chat.h':('12b3f8a287698b1b5f3f4e020e52162f5026b06596b55946fa865a4a0b3c4abc',[(58,71)]),
'common/chat.cpp':('a226aa0cbf844490cd480bb805c458df16af8771b1ecb53a8fe608e3b2e60d3c',[(744,754),(765,770),(839,840),(1215,1221),(1424,1428)]),
'tools/server/server-context.cpp':('2f5d65ce6ef0504b5c8cf55a74c68d3959c49784ba380ef836566b7a7d5fa12b',[(4609,4629),(4930,4943),(5060,5069)]),
'tools/server/server-common.cpp':('de3a89422f67b97eb385041fae17e553dc677aac6b67f2e98e9f0beff672b4e0',[(1359,1363)])}
def native_template(served,raw):
    a=raw.encode('utf-8');b=served.encode('utf-8')
    assert b'\r' not in a,'CR not permitted'
    assert len(a)==3990 and hashlib.sha256(a).hexdigest()==RAW_SHA,'raw pinned template mismatch'
    assert len(b)==3989 and hashlib.sha256(b).hexdigest()==SERVED_SHA,'served pinned template mismatch'
    assert a==b+b'\n','exact single LF relation required'
    return {'raw_sha256':RAW_SHA,'served_sha256':SERVED_SHA,'raw_bytes':len(a),'served_bytes':len(b),'transformation':'pinned lexer removes exactly one final LF; no CR','both_exact_hashes_verified':True}
def archive_trace(source,archive,out):
    dest=out/'runner_template_trace';dest.mkdir()
    receipts={}
    with tarfile.open(archive) as tar:
        for name,(digest,ranges) in TRACE.items():
            data=(source/name).read_bytes()
            assert hashlib.sha256(data).hexdigest()==digest,('trace source mismatch',name)
            member=next(x for x in tar.getmembers() if x.name.endswith('/'+name))
            assert tar.extractfile(member).read()==data,('trace archive mismatch',name)
            target=dest/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            lines=data.decode().splitlines()
            receipts[name]={'sha256':digest,'line_ranges':ranges,'snippets':['\n'.join(lines[a-1:b]) for a,b in ranges]}
    with (out/'template_source_trace.json').open('x') as f:json.dump(receipts,f,indent=2)
