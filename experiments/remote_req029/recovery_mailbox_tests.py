import tempfile,unittest
from pathlib import Path
from recovery_mailbox import exchange
class Tests(unittest.TestCase):
    def test_immutable_role_and_path(self):
        with tempfile.TemporaryDirectory() as d:
            q=dict(operation='publish',kind='request',sequence=1,payload={'fixed':'nonce'})
            a=exchange(d,'controller',q)
            self.assertEqual(a,exchange(d,'controller',q))
            self.assertEqual(a,exchange(d,'worker',dict(q,operation='read',payload=None)))
            for bad,role in [(dict(q,payload={'changed':True}),'controller'),(q,'worker'),(dict(q,sequence=25),'controller'),(dict(q,kind='../escape'),'controller')]:
                with self.assertRaises(ValueError):exchange(d,role,bad)
            self.assertEqual(list(Path(d).glob('.pending-*')),[])
    def test_absent_size_and_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            q=dict(operation='read',kind='response',sequence=1,payload=None)
            self.assertFalse(exchange(d,'controller',q)['present'])
            with self.assertRaises(ValueError):exchange(d,'worker',dict(q,operation='publish',payload='x'*1048576))
            (Path(d)/'response-01.json').symlink_to('/dev/null')
            with self.assertRaises(ValueError):exchange(d,'worker',q)
if __name__=='__main__':unittest.main()
