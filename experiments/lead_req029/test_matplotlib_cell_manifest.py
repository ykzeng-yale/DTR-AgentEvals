import copy,json,unittest
from pathlib import Path
from matplotlib_cell_manifest import draft,verify_frozen_cell,ROOT
from recovery_contract import validate
class Tests(unittest.TestCase):
    def setUp(self):self.public=(ROOT/'docs/source_snapshots/req029s_public/public_task.json').read_bytes()
    def test_both_drafts_stay_disabled(self):
        for arm in ('qwen','klear'):
            r=draft(arm,self.public);self.assertTrue(verify_frozen_cell(r,self.public))
            self.assertFalse(r['execution_authorized']);self.assertFalse(r['sandbox']['qualified'])
            self.assertIsNone(r['worker_commit']);self.assertIsNone(r['transport_config_sha256'])
            with self.assertRaises(Exception):validate(r)
    def test_shared_messages_and_declared_model_differences(self):
        q,k=[draft(a,self.public) for a in ('qwen','klear')]
        self.assertEqual(q['initial_messages_utf8'],k['initial_messages_utf8'])
        self.assertEqual(q['task'],k['task']);self.assertEqual(q['sandbox'],k['sandbox'])
        self.assertNotEqual(q['model'],k['model'])
        self.assertEqual(q['model']['config']['cache_k'],'q8_0')
        self.assertEqual(k['model']['config']['cache_k'],'q4_0')
    def test_mixed_task_prompt_sandbox_budget_rejected(self):
        original=draft('qwen',self.public)
        changes=[('task','task_id','django__django-16560'),('task','base_commit','0'*40),
                 ('sandbox','image','sha256:'+'0'*64),('sandbox','archive_ownership','restore'),
                 ('sandbox','import_module','django'),('caps','max_calls',25),
                 ('model','config',{})]
        for group,key,value in changes:
            r=copy.deepcopy(original);r[group][key]=value
            with self.assertRaises(ValueError):verify_frozen_cell(r,self.public)
        r=copy.deepcopy(original);r['initial_messages_utf8']='[]'
        with self.assertRaises(ValueError):verify_frozen_cell(r,self.public)
    def test_hidden_input_or_other_arm_rejected(self):
        t=json.loads(self.public);t['patch']='LEAK'
        with self.assertRaises(ValueError):draft('qwen',json.dumps(t).encode())
        with self.assertRaises(Exception):draft('newmodel',self.public)
    def test_drafts_do_not_share_mutable_contracts(self):
        first=draft('qwen',self.public);first['sandbox']['limits']['Memory']=1
        self.assertNotEqual(draft('qwen',self.public)['sandbox']['limits']['Memory'],1)
if __name__=='__main__':unittest.main()
