import unittest
from pathlib import Path
from matplotlib_acquire import manifest,TASK
class Tests(unittest.TestCase):
    def test_frozen_manifest_and_mutation(self):
        p=Path(__file__).resolve().parents[2]/'results/local_req029/image_metadata_20260927'/ (TASK+'.amd64.json')
        raw=p.read_bytes();m=manifest(raw);self.assertEqual(sum(x['size'] for x in m['layers']),2258509781)
        with self.assertRaises(AssertionError):manifest(raw+b' ')
if __name__=='__main__':unittest.main()
