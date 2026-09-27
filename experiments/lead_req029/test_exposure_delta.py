import io,time,unittest
from exposure_delta import scan
class ScanTests(unittest.TestCase):
    def test_boundary_and_no_outcome_parsing(self):
        self.assertEqual(scan(io.BytesIO(b'not-json: xx django__django-16560 yy outcome:private'),[b'django__django-16560'],[0],time.monotonic()+2,3),['django__django-16560'])
    def test_nonmatching(self):
        self.assertEqual(scan(io.BytesIO(b'astropy__astropy-14598'),[b'django__django-16560'],[0],time.monotonic()+2),[])
    def test_deadline(self):
        with self.assertRaises(TimeoutError):scan(io.BytesIO(b'x'),[b'x'],[0],time.monotonic()-1)
if __name__=='__main__':unittest.main()
