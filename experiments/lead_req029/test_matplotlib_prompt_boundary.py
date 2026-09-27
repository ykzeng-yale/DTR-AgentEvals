"""Public-input boundary checks, no model or evaluator invocation."""
import json,unittest
from pathlib import Path
from unittest.mock import patch
from jinja2 import Template,StrictUndefined
from matplotlib_prompt_boundary import build,BUNDLE,ENVIRONMENT,TASK_SHA
ROOT=BUNDLE.parents[2]
PUBLIC=ROOT/'docs/source_snapshots/req029s_public/public_task.json'
class Tests(unittest.TestCase):
    def setUp(self):self.raw=PUBLIC.read_bytes();self.env=dict(ENVIRONMENT)
    def test_native_model_independent_identical_initial_messages(self):
        a=build(self.raw,self.env);self.assertEqual(a,build(self.raw,self.env))
        m=json.loads(a);self.assertEqual([x['role'] for x in m],['system','user'])
        templates=json.loads((BUNDLE/'templates.json').read_bytes())
        task=json.loads(self.raw)
        self.assertEqual(m[0]['content'],Template(templates['system_template'],undefined=StrictUndefined).render(**self.env))
        archived=json.loads((ROOT/'docs/req028_c0_prompt_20260927.json').read_bytes())
        self.assertEqual(m[0],archived['messages'][0])
        self.assertEqual(m[1]['content'],Template(templates['instance_template'],undefined=StrictUndefined).render(task=task['problem_statement'],**self.env))
        self.assertEqual(set(m[0]),{'role','content'});self.assertEqual(set(m[1]),{'role','content'})
    def test_hidden_columns_and_wrong_task_fail_before_template_io(self):
        for field in ('patch','test_patch','hints_text','FAIL_TO_PASS','PASS_TO_PASS','reference','future_observation'):
            task=json.loads(self.raw);task[field]='LEAK_SENTINEL'
            with patch.object(Path,'read_bytes',side_effect=AssertionError('unexpected file read')):
                with self.assertRaises(ValueError):build(json.dumps(task).encode(),self.env)
        with self.assertRaises(ValueError):build(b'{}',self.env)
    def test_exact_environment_not_secondary_input_channel(self):
        for field in self.env:
            for replacement in ('LEAK_SENTINEL',self.env[field]+' ',self.env[field]+'\n'):
                env=dict(self.env);env[field]=replacement
                with self.assertRaises(ValueError):build(self.raw,env)
        with self.assertRaises(ValueError):build(self.raw,dict(self.env,test_patch='LEAK'))
    def test_builder_reads_only_pinned_public_template(self):
        real=Path.read_bytes;seen=[]
        def read(path):
            seen.append(path);self.assertEqual(path,BUNDLE/'templates.json');return real(path)
        with patch.object(Path,'read_bytes',read):build(self.raw,self.env)
        self.assertEqual(seen,[BUNDLE/'templates.json'])
    def test_template_substitution_rejected(self):
        with patch.object(Path,'read_bytes',return_value=b'{"system_template":"LEAK"}'):
            with self.assertRaises(ValueError):build(self.raw,self.env)
if __name__=='__main__':unittest.main()
