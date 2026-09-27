import json,unittest
from unittest.mock import patch
from prompt_boundary import build,BUNDLE
class Tests(unittest.TestCase):
    def setUp(self):
        self.raw=(BUNDLE/'public_task.json').read_bytes()
        self.env={'system':'Linux','release':'fixture-release','version':'fixture-version','machine':'x86_64'}
    def test_identical_model_inputs_and_upstream_system(self):
        a=build(self.raw,self.env);b=build(self.raw,self.env);self.assertEqual(a,b)
        m=json.loads(a);self.assertEqual([x['role'] for x in m],['system','user'])
        source=json.loads((BUNDLE.parents[1]/'req028_c0_prompt_20260927.json').read_text())
        self.assertEqual(m[0],source['messages'][0]);self.assertTrue(m[1]['content'].startswith('Please solve this issue: '+json.loads(self.raw)['problem_statement']))
    def test_hidden_fields_or_other_task_rejected(self):
        for key in ('test_patch','patch','hints_text','FAIL_TO_PASS','reference','future_observation'):
            x=json.loads(self.raw);x[key]='LEAK_SENTINEL'
            with self.assertRaises(ValueError):build(json.dumps(x).encode(),self.env)
        x=json.loads(self.raw);x['instance_id']='astropy__astropy-14598'
        with self.assertRaises(ValueError):build(json.dumps(x).encode(),self.env)
    def test_environment_not_a_second_task_channel(self):
        for x in (dict(self.env,test_patch='LEAK'),dict(self.env,machine='arm64'),dict(self.env,version='first\nLEAK'),dict(self.env,system='Darwin')):
            with self.assertRaises(ValueError):build(self.raw,x)
    def test_template_mutation_rejected(self):
        from pathlib import Path
        with patch.object(Path,'read_bytes',return_value=b'{"system_template":"LEAK"}'):
            with self.assertRaises(ValueError):build(self.raw,self.env)
if __name__=='__main__':unittest.main()
