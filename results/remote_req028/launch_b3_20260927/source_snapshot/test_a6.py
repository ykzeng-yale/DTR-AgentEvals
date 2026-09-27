"""A6 executable control-flow regression with an owned inert subprocess."""
import subprocess,sys,unittest
import guard
from a6_control import owned_scope,execute_calls
from mechanics_a6 import build_command
from mechanics_a5 import build_command as a5_command
class A6Tests(unittest.TestCase):
    def test_cli_only_cache_types_change(self):
        old=a5_command('same-alias',12345,'A5');new=build_command('same-alias',12345,'A6')
        expected=old[:]
        for flag in ('--cache-type-k','--cache-type-v'):expected[expected.index(flag)+1]='q8_0'
        self.assertEqual(new,expected)
    def test_first_abort_prevents_second_and_releases_owned_process(self):
        command=[sys.executable,'-c','import time; time.sleep(30)']
        child=subprocess.Popen(command,start_new_session=True)
        record={'pid':child.pid,'identity':guard.ps(child.pid),'command':command}
        calls=[];cleanups=[]
        def cleanup():
            cleanups.append(True);guard.stop(record);child.wait(timeout=5)
        def dispatch(index):
            calls.append(index)
            raise RuntimeError('fake first-call resource abort')
        try:
            with self.assertRaisesRegex(RuntimeError,'fake first-call resource abort'):
                with owned_scope(cleanup):execute_calls(dispatch)
            self.assertEqual(calls,[0])
            self.assertEqual(cleanups,[True])
            self.assertIsNotNone(child.poll())
            self.assertFalse(guard.same(record))
        finally:
            if child.poll() is None:cleanup()
    def test_terminal_format_failure_does_not_retry(self):
        calls=[];cleanups=[]
        def dispatch(index):
            calls.append(index)
            return {'terminal':True,'format_compliant':False}
        with owned_scope(lambda:cleanups.append(True)):execute_calls(dispatch)
        self.assertEqual(calls,[0,1]);self.assertEqual(cleanups,[True])
    def test_setup_failure_still_cleans(self):
        cleanups=[]
        with self.assertRaisesRegex(ValueError,'binding mismatch'):
            with owned_scope(lambda:cleanups.append(True)):raise ValueError('binding mismatch')
        self.assertEqual(cleanups,[True])
if __name__=='__main__':unittest.main()
