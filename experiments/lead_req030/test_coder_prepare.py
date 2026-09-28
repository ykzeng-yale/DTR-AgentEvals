import hashlib
import io
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from coder_prepare import download

class DownloadTests(unittest.TestCase):
    def call(self, body=b'abc', size=3, digest=None, deadline=None):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'asset'
            entry={'url':'https://example.invalid/asset','size':size,'sha256':digest or hashlib.sha256(b'abc').hexdigest()}
            with patch('urllib.request.urlopen',return_value=io.BytesIO(body)):
                result=download(entry,p,time.monotonic()+10 if deadline is None else deadline)
            self.assertEqual(p.read_bytes(),body)
            return result
    def test_exact(self): self.assertEqual(self.call()['bytes'],3)
    def test_oversize(self):
        with self.assertRaises(ValueError):self.call(body=b'abcd')
    def test_short(self):
        with self.assertRaises(ValueError):self.call(body=b'ab')
    def test_hash(self):
        with self.assertRaises(ValueError):self.call(body=b'xyz')
    def test_deadline(self):
        with self.assertRaises(TimeoutError):self.call(deadline=0)

if __name__=='__main__':unittest.main()
