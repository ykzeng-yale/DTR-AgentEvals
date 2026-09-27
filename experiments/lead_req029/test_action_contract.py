import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from action_contract import parse_complete,CONTRACT
ROOT=Path(__file__).resolve().parents[2]
class Tests(unittest.TestCase):
 def test_both_archived_contents_as_data(self):
  data=json.loads((ROOT/'results/remote_req028/c1_boundary_20260927/arm_comparison.json').read_bytes())
  for arm,row in data.items():
   with self.subTest(arm=arm):
    got=parse_complete(row['content'],row['finish_reason'])
    self.assertEqual(got['command'],row['endpoints_unchanged']['extracted_actions'][0]);self.assertEqual(got['raw_content'],row['content'])
  self.assertFalse(data['klear']['endpoints_unchanged']['interface_gate'])
 def test_reasoning_prose_does_not_transform_content(self):
  fence='```mswea_bash_command\necho data\n```'
  for text in [fence,'<think>'+fence,'<think>'+fence+'</think>','<think><think>'+fence,'</think>'+fence,'quoted prose\n'+fence]:
   self.assertEqual(parse_complete(text,'stop')['raw_content'],text)
 def test_multiple_anywhere_rejected(self):
  f='```mswea_bash_command\necho data\n```'
  for text in [f+f,'<think>'+f+'</think>'+f]:
   with self.assertRaises(ValueError):parse_complete(text,'stop')
 def test_empty_unclosed_wrong_label_and_missing_rejected(self):
  for text in ['', '```mswea_bash_command\n\n```','```mswea_bash_command\necho data','```bash\necho data\n```']:
   with self.assertRaises(ValueError):parse_complete(text,'stop')
 def test_nonterminal_and_nontext_rejected(self):
  for finish in ['length','error',None]:
   with self.assertRaises(ValueError):parse_complete('```mswea_bash_command\necho data\n```',finish)
  with self.assertRaises(ValueError):parse_complete(None,'stop')
if __name__=='__main__':unittest.main()
