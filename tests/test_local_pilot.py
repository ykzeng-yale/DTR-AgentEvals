import unittest
from dtr_agent_evals.local_pilot import parse_answer,task_from_seed,action_probability

class TestLocalPilot(unittest.TestCase):
    def test_strict_parser_never_executes(self):
        self.assertEqual(parse_answer('{"answer": 7}'),7)
        for invalid in ['{"answer":true}','{"answer":"7"}','{"answer":7,"code":"print(1)"}', '__import__("os").system("anything")']:
            self.assertIsNone(parse_answer(invalid))
    def test_task_validator(self):
        for seed in range(20):
            for family in ['modular','small_products']:
                t=task_from_seed(seed,family);answer=t['a']*t['b']+t['c']*t['d']-t['e']
                if family=='modular':answer%=t['m']
                self.assertEqual(answer,t['answer'])
    def test_adaptive_logging_and_target_differ(self):
        self.assertEqual(action_probability('logging',0,None),.5)
        self.assertEqual(action_probability('logging',1,False),.75)
        self.assertEqual(action_probability('logging',1,True),.25)
        self.assertEqual(action_probability('failure_escalation',0,None),0)
        self.assertEqual(action_probability('failure_escalation',1,False),1)
        self.assertEqual(action_probability('failure_escalation',1,True),0)

    def test_feedback_is_sequential_and_true_answer_not_in_initial_prompt(self):
        import json
        from unittest.mock import patch
        from dtr_agent_evals.local_pilot import run_trajectory
        task={'seed':99,'a':15,'b':8,'c':14,'d':8,'e':13,'expression':'(15 * 8) + (14 * 8) - 13','answer':219}
        cfg={'seed':1,'models':['small','large'],'horizon':3,'temperature':0,'num_predict':192,'resource_cost':[.01,.03],'ollama_url':'http://127.0.0.1:11434','task_family':'small_products','allow_reasoning':True}
        replies=iter([0,219,219]);requests=[]
        def fake_api(base,path,payload):
            requests.append(json.loads(json.dumps(payload)))
            return {'message':{'content':json.dumps({'reasoning':'arithmetic','answer':next(replies)})},'eval_count':12}
        with patch('dtr_agent_evals.local_pilot.api',fake_api):
            events,summary=run_trajectory(cfg,task,'failure_escalation',0,{'small':'s','large':'l'})
        self.assertEqual(summary['actions'],[0,1,0])
        self.assertEqual(summary['correctness'],[False,True,True])
        self.assertAlmostEqual(summary['utility'],.95)
        first=requests[0]['messages'][1]['content']
        self.assertNotIn('219',first)
        self.assertNotIn('mod',first)
        self.assertIn('15 * 8 = 120',requests[1]['messages'][-1]['content'])
        self.assertIn('incorrect',requests[1]['messages'][-1]['content'])
        self.assertIn('is correct',requests[2]['messages'][-1]['content'])
