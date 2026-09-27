import json,unittest
from b2r_binding import native_template
from mechanics_b2r import ROOT,build_command
from mechanics_b2 import build_command as prior
class B2RTests(unittest.TestCase):
    def setUp(self):
        p=ROOT/'results/remote_req028/mechanics_b2_20260927'
        self.raw=(p/'chat_template.jinja').read_text()
        self.served=json.loads((p/'server_0.props.json').read_text())['chat_template']
    def test_exact_known_pair_passes(self):
        r=native_template(self.served,self.raw)
        self.assertTrue(r['both_exact_hashes_verified'])
    def test_raw_mutations_rejected(self):
        variants=[self.raw.replace('tools','tools ',1),self.raw+'\n',self.raw+' ',self.raw+'\t',self.raw.replace('\n','\r\n'),self.raw[:-1],self.raw.replace(' ','\t',1)]
        for raw in variants:
            with self.subTest(raw=repr(raw[-20:])):
                with self.assertRaises(AssertionError):native_template(self.served,raw)
    def test_served_mutations_rejected(self):
        variants=[self.served+'\n',self.served+' ',self.served+'\t',self.served.replace('\n','\r\n'),self.served.replace('tools','tools ',1)]
        for served in variants:
            with self.subTest(served=repr(served[-20:])):
                with self.assertRaises(AssertionError):native_template(served,self.raw)
    def test_joint_internal_mutation_rejected_even_with_lf_relation(self):
        served=self.served.replace('tools','tools ',1)
        with self.assertRaises(AssertionError):native_template(served,served+'\n')
    def test_configuration_unchanged(self):
        self.assertEqual(build_command('alias',123,'B2R'),prior('alias',123,'B2'))
if __name__=='__main__':unittest.main()
