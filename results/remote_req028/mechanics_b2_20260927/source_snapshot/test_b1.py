import hashlib,io,tempfile,unittest
from pathlib import Path
from b1_acquire import acquire,capacity
class B1Tests(unittest.TestCase):
    def test_size_and_hash_reject(self):
        for size,digest in ((4,hashlib.sha256(b'abc').hexdigest()),(3,'bad')):
            with tempfile.TemporaryDirectory() as d:
                p=Path(d);clock=[0]
                with self.assertRaises(AssertionError):acquire(p/'final',p/'partial',lambda:io.BytesIO(b'abc'),10,now=lambda:0,sleep=lambda _:None,size=size,sha=digest)
                self.assertTrue((p/'partial').exists());self.assertFalse((p/'final').exists())
    def test_existing_valid_reused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'final').write_bytes(b'abc')
            def opener():raise AssertionError('must not download')
            r=acquire(p/'final',p/'partial',opener,10,now=lambda:0,size=3,sha=hashlib.sha256(b'abc').hexdigest())
            self.assertTrue(r['reused']);self.assertFalse((p/'partial').exists())
    def test_deadline_and_disk_admission(self):
        s={'pressure_level':1,'free_percent':70,'foreign_inference':[],'disk_free_bytes':17*1024**3}
        capacity(s,5*1024**3,10,0)
        with self.assertRaisesRegex(AssertionError,'deadline'):capacity(s,0,10,10)
        with self.assertRaisesRegex(AssertionError,'disk'):capacity(s,6*1024**3,10,0)
    def test_interruption_retains_partial_no_duplicate(self):
        class Interrupted(io.BytesIO):
            def read(self,n):raise OSError('interrupted')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);calls=[]
            def opener():calls.append(1);return Interrupted()
            with self.assertRaises(OSError):acquire(p/'final',p/'partial',opener,10,now=lambda:0,sleep=lambda _:None,size=3)
            self.assertTrue((p/'partial').exists())
            with self.assertRaisesRegex(AssertionError,'partial exists'):acquire(p/'final',p/'partial',opener,10,now=lambda:0)
            self.assertEqual(len(calls),1)
    def test_success_renames_without_duplicate(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);r=acquire(p/'final',p/'partial',lambda:io.BytesIO(b'abc'),10,now=lambda:0,sleep=lambda _:None,size=3,sha=hashlib.sha256(b'abc').hexdigest())
            self.assertFalse((p/'partial').exists());self.assertEqual((p/'final').read_bytes(),b'abc');self.assertEqual(r['network_bytes'],3)
if __name__=='__main__':unittest.main()
