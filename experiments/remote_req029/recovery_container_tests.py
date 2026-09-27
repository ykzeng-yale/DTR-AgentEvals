import importlib,sys,unittest
from unittest.mock import patch
from recovery_container import CAPTURE,CODE
class Tests(unittest.TestCase):
 def test_preserve_diagnostics_and_reject_overflow(self):
  ns={'importlib':importlib};exec(CAPTURE,ns);sentinel=object()
  def noisy(name):print('out');print('warning',file=sys.stderr);return sentinel
  with patch.object(importlib,'import_module',noisy):
   m,d=ns['captured_import']('inert');self.assertIs(m,sentinel);self.assertEqual(d,{'stdout':'out\n','stderr':'warning\n'})
  def overflow(name):print('x'*65537);return sentinel
  with patch.object(importlib,'import_module',overflow):
   with self.assertRaises(ValueError):ns['captured_import']('inert')
  compile(CODE,'fixed-container-helper','exec')
if __name__=='__main__':unittest.main()
