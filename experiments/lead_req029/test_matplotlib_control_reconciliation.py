import copy,json,unittest,tarfile
from pathlib import Path
from matplotlib_control_reconciliation import reconcile,sha
ROOT=Path('results/local_req029/matplotlib_eval_runtime/mpe029w-matplotlib20826-a')
class Tests(unittest.TestCase):
    def setUp(self):
        with tarfile.open('results/local_req029/matplotlib_controls_review_20260927/runtime.tar.gz') as t:
            self.raw=[t.extractfile(m+'/test.output').read() for m in ('baseline','reference')]
            self.r=[json.load(t.extractfile(m+'/terminal.json')) for m in ('baseline','reference')]
    def test_observed_diagnostic_preserves_original_failure(self):
        out=reconcile(*self.raw,*self.r)
        self.assertEqual(out['original_gate_preserved'],[True,False]);self.assertFalse(out['execution_authorized'])
    def test_all_declared_status_corruptions_rejected(self):
        target=b'PASSED lib/matplotlib/tests/test_axes.py::test_shared_axes_clear[png]'
        for status in (b'FAILED',b'ERROR',b'SKIPPED',b'XFAIL',b'UNKNOWN'):
            raw=self.raw[1].replace(target,status+target[6:]);r=copy.deepcopy(self.r);r[1]['raw_output_sha256']=sha(raw)
            with self.assertRaises(ValueError):reconcile(self.raw[0],raw,*r)
        raw=self.raw[1].replace(target,b'');r=copy.deepcopy(self.r);r[1]['raw_output_sha256']=sha(raw)
        with self.assertRaises(ValueError):reconcile(self.raw[0],raw,*r)
    def test_extra_failure_change_rejected(self):
        raw=self.raw[1].replace(b'PASSED lib/matplotlib/tests/test_axes.py::test_shared_axes_retick',b'FAILED lib/matplotlib/tests/test_axes.py::test_shared_axes_retick')
        r=copy.deepcopy(self.r);r[1]['raw_output_sha256']=sha(raw)
        with self.assertRaises(ValueError):reconcile(self.raw[0],raw,*r)
    def test_incomplete_or_unknown_or_wrong_identity_rejected(self):
        for k,v in [('raw_output_complete',False),('returncode',-9),('infrastructure_error','timeout'),('source_commit','0'*40)]:
            r=copy.deepcopy(self.r);r[1][k]=v
            with self.assertRaises(ValueError):reconcile(*self.raw,*r)
        raw=self.raw[1].replace(b'>>>>> End Test Output',b'');r=copy.deepcopy(self.r);r[1]['raw_output_sha256']=sha(raw)
        with self.assertRaises(ValueError):reconcile(self.raw[0],raw,*r)
    def test_raw_hash_and_cleanup_rejected(self):
        with self.assertRaises(ValueError):reconcile(self.raw[0],self.raw[1]+b'x',*self.r)
        r=copy.deepcopy(self.r);r[1]['cleanup']['owned_absent']=False
        with self.assertRaises(ValueError):reconcile(*self.raw,*r)
if __name__=='__main__':unittest.main()
