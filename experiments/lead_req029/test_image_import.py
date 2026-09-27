import gzip,hashlib,json,tempfile,tarfile,unittest
from pathlib import Path
from image_import import pack
class Tests(unittest.TestCase):
    def test_exact_archive_and_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);data=b'fixed inert bytes';compressed=gzip.compress(data);sha=lambda b:'sha256:'+hashlib.sha256(b).hexdigest()
            r=dict(compressed_sha256=sha(compressed),compressed_bytes=len(compressed),uncompressed_bytes=len(data),diff_id=sha(data))
            f=p/(r['compressed_sha256'][7:]+'.gz');f.write_bytes(compressed)
            config=b'{"inert":true}';pack(p/'a.tar',config,[r],p,'inert:fixture')
            with tarfile.open(p/'a.tar') as t:
                m=json.load(t.extractfile('manifest.json'))[0]
                self.assertEqual(t.extractfile(m['Config']).read(),config)
                self.assertEqual(t.extractfile(m['Layers'][0]).read(),data)
                self.assertEqual(m['RepoTags'],['inert:fixture'])
            f.write_bytes(b'bad')
            with self.assertRaises(AssertionError):pack(p/'bad.tar',config,[r],p,'inert:fixture')
if __name__=='__main__':unittest.main()
