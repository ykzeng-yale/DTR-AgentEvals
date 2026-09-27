import copy,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from recovery_backend import Docker
from recovery_fixtures import release
from recovery_contract import validate
class Tests(unittest.TestCase):
 def test_policy_bound_before_population(self):
  r,_=release();validate(r)
  with tempfile.TemporaryDirectory() as tmp:
   d=Docker(Path(tmp),r['sandbox'])
   with patch.object(d,'call') as call:
    d.populate('c'*64,123)
    self.assertEqual(call.call_args.args,(['exec','-i','c'*64,'tar','--no-same-owner','-xf','-','-C','/testbed'],123))
    self.assertEqual(call.call_args.kwargs,{'stdin':d.archive})
   for mode in (None,'preserve','root'):
    bad=copy.deepcopy(r)
    if mode is None:bad['sandbox'].pop('archive_ownership')
    else:bad['sandbox']['archive_ownership']=mode
    with self.assertRaises(Exception):validate(bad)
    d.contract=bad['sandbox']
    with patch.object(d,'call') as call:
     with self.assertRaises(Exception):d.populate('c'*64,123)
     call.assert_not_called()
if __name__=='__main__':unittest.main()
