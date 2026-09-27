import io,json,tempfile,time,unittest,urllib.request
from pathlib import Path
from unittest.mock import patch
import image_acquire as a
class Tests(unittest.TestCase):
    def test_pins(self):
        raw=(a.META/(a.TASK+'.amd64.json')).read_bytes();self.assertEqual(len(a.manifest(raw)['layers']),10)
        with self.assertRaises(AssertionError):a.manifest(raw+b' ')
    def test_redirect_drops_auth(self):
        q=urllib.request.Request('https://registry-1.docker.io/x',headers={'Authorization':'Bearer inert'})
        r=a.NoAuthRedirect().redirect_request(q,None,302,'ok',{},'https://example.invalid/x');self.assertFalse(r.has_header('Authorization'))
        with self.assertRaises(ValueError):a.NoAuthRedirect().redirect_request(q,None,302,'ok',{},'http://example.invalid/x')
    def test_expiry_and_network_cap(self):
        b=a.Budget(Path('.'),seconds=-1)
        with self.assertRaisesRegex(AssertionError,'deadline'):b.check()
        b=a.Budget(Path('.'));b.bytes=a.LIMIT
        with self.assertRaisesRegex(AssertionError,'response-body cap'):b.check(1)
    def test_auth_failure_retains_terminal_no_retry(self):
        calls=[]
        def fake(*args,**kw):calls.append(1);raise TimeoutError('inert')
        with tempfile.TemporaryDirectory() as t,patch.object(a.Budget,'check'):
            r=a.run(Path(t)/'once',fake);self.assertEqual(len(calls),1);self.assertTrue(r['error']);self.assertTrue((Path(t)/'once/terminal.json').exists())
            with self.assertRaises(FileExistsError):a.run(Path(t)/'once',fake)
    def test_stream_success_and_digest_failure(self):
        import hashlib
        payload=b'fixed inert OCI body'
        pin='sha256:'+hashlib.sha256(payload).hexdigest()
        for corrupt in (False,True):
            with self.subTest(corrupt=corrupt),tempfile.TemporaryDirectory() as t,patch.object(a.Budget,'check'),patch.object(a.Budget,'throttle'),patch.object(a,'manifest',return_value={'layers':[{'size':len(payload),'digest':pin}]}):
                calls=[]
                def fake(req,**kwargs):
                    calls.append(req)
                    return io.BytesIO(b'{"token":"inert"}' if len(calls)==1 else (b'X'+payload[1:] if corrupt else payload))
                root=Path(t)/'once';r=a.run(root,fake)
                self.assertEqual(len(calls),2)
                self.assertEqual(bool(r['error']),corrupt)
                self.assertEqual(len(r['completed_layers']),0 if corrupt else 1)
                self.assertTrue((root/(pin[7:]+('.partial' if corrupt else '.gz'))).is_file())
                self.assertNotIn('inert',json.dumps(r))
    def test_throttle_rechecks_until_rate_bound(self):
        clock=[0.0]
        with patch.object(a.time,'monotonic',side_effect=lambda:clock[0]),patch.object(a.time,'sleep',side_effect=lambda d:clock.__setitem__(0,clock[0]+d)),patch.object(a.Budget,'check'):
            a.Budget(Path('.')).throttle(0,a.RATE)
        self.assertGreaterEqual(clock[0],1)
if __name__=='__main__':unittest.main()
