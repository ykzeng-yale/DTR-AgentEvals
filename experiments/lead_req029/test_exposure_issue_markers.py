import io,json,time,unittest
from exposure_issue_markers import markers
from exposure_delta import scan
class Tests(unittest.TestCase):
    def test_escaped_unicode_and_chunk_boundary(self):
        p='x'*140+'quote " newline\n unicode é'+'y'*140
        m=markers(p);data=json.dumps({'messages':[p]},ensure_ascii=True).encode()
        found=scan(io.BytesIO(data),list(set(m.values())),[0],time.monotonic()+2,7)
        self.assertIn(m['full/json_ascii'].decode(),found)
        self.assertNotIn(m['full/raw'].decode(),found)
    def test_no_task_id_needed_and_no_outcome_parse(self):
        p='issue '*60;m=markers(p)
        self.assertIn(p,scan(io.BytesIO(b'not JSON: '+p.encode()),list(set(m.values())),[0],time.monotonic()+2))
    def test_utf8_split_rejected_not_repaired(self):
        with self.assertRaises(UnicodeDecodeError):markers('x'*127+'é'+'z'*200)
if __name__=='__main__':unittest.main()
