"""Exact C5 authorization atop C4's isolated-index, non-force transport."""
import time
from c4_git import Transport
from c5_contract import *
class ExactTransport(Transport):
    def authorize_exact(self,manifest,expected_main,timeout=30,fixture_commit=None):
        try:
            self.start(timeout);r=release(manifest,time.time());entry=dict(ENTRY)
            if fixture_commit is not None:
                require(self.fixture_root is not None,'test commit only in isolated local fixture');commit_id(fixture_commit);entry['commit']=fixture_commit
            require(self.authorized is None,'C5 one authorization only');require(self.fetch()==expected_main,'concurrent main advancement');self.git('merge-base','--is-ancestor',entry['commit'],expected_main)
            raw=self.object(entry['commit'],entry['path']);q=request(raw,manifest,time.time())
            self.authorized={'release':r,'pin':RELEASE_SHA,'entry':entry,'request':q,'raw':raw,'expected_main':expected_main,'response_path':RESPONSE_PATH}
            return raw
        except BaseException:self.failed=True;raise
    def approve_exact_native(self,binding,attestation_sha):
        receipts=verify_native(binding);digest(attestation_sha);require(self.authorized is not None,'authorize request first')
        self.authorized['binding_sha256']=receipts['binding_sha256'];self.authorized['asset_attestation_sha256']=attestation_sha;return receipts
