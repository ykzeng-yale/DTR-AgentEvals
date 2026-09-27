"""Fake dispatch outcomes and exact runner command contract, no model invocation."""
import unittest
from dispatch_followup import permit_a3
from mechanics_followup import build_command,SERVER,MODEL
class FollowupTests(unittest.TestCase):
    def test_completion_skips(self):
        self.assertFalse(permit_a3({'status':'COMPLETE'},[],{}))
    def test_pressure_cleanup_permits(self):
        self.assertTrue(permit_a3({'status':'FAILED','lifecycles':[{'released':True}]},[{'reason':'adverse_pressure','owned_stop':True}],{'exception':"RemoteDisconnected('closed')"}))
    def test_other_failure_forbids(self):
        for exception in ("AssertionError('watchdog exited')","JSONDecodeError('invalid')"):
            self.assertFalse(permit_a3({'status':'FAILED','lifecycles':[{'released':True}]},[{'reason':'adverse_pressure','owned_stop':True}],{'exception':exception}))
        self.assertFalse(permit_a3({'status':'FAILED','lifecycles':[{'released':True}]},[{'reason':'deadline','owned_stop':True}],{'exception':"RemoteDisconnected('closed')"}))
    def test_unconfirmed_cleanup_forbids(self):
        self.assertFalse(permit_a3({'status':'FAILED','lifecycles':[{'released':False}]},[{'reason':'adverse_pressure','owned_stop':True}],{'exception':"RemoteDisconnected('closed')"}))
    def test_exact_cli(self):
        for variant,cache in [('A2','f16'),('A3','q8_0')]:
            expected=[str(SERVER),'-m',str(MODEL),'--alias','fake-token','--host','127.0.0.1','--port','12345','--ctx-size','32768','--parallel','1','--cache-type-k',cache,'--cache-type-v',cache,'--cache-ram','0','--no-cache-prompt','--no-cache-idle-slots','--no-context-shift','--jinja','--seed','20260927028','--temp','0','--n-predict','128','--threads','2','--threads-batch','2','--threads-http','2','--n-gpu-layers','99','--flash-attn','on','--no-warmup','--batch-size','128','--ubatch-size','32','--verbose']
            self.assertEqual(build_command('fake-token',12345,variant),expected)
        self.assertEqual(20260927028%2**32,3081057844)
if __name__=='__main__':unittest.main()
