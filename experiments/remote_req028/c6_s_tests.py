"""Deterministic interval regressions. No actual Git, model, Docker or sleep."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from c2_relay import Rejected
from c6_git import Transport


class Clock:
    def __init__(self, now):
        self.now=now
        self.sleeps=[]

    def time(self):
        return self.now

    def sleep(self, seconds):
        if seconds<=0:
            raise ValueError('non-positive sleep')
        self.sleeps.append(seconds)
        self.now+=seconds


class Tests(unittest.TestCase):
    def fixture(self, now=4.99, deadline=100, check=lambda:None):
        clock=Clock(now)
        x=Transport.__new__(Transport)
        x.failed=False; x.fetches=0; x.last_fetch=0; x.interval=5
        x.deadline=deadline; x.runner=SimpleNamespace(check=check)
        x.origin='fixture-only'; x.seen={}; x.events=[]
        commands=[]
        def git(*args):
            commands.append((clock.now,args))
            return {'output':'a'*40+'\n'}
        x.git=git
        self.addCleanup(patch.stopall)
        patch('c6_git.time.time',clock.time).start()
        patch('c6_git.time.sleep',clock.sleep).start()
        return x,clock,commands

    def test_cross_boundary_during_cancellation_check(self):
        x,c,commands=self.fixture()
        x.runner.check=lambda:setattr(c,'now',5.01)
        self.assertEqual(x.fetch(),'a'*40)
        self.assertEqual(c.sleeps,[])
        self.assertEqual(commands[0][0],5.01)
        self.assertEqual(x.fetches,1)

    def test_exact_boundary_no_sleep(self):
        x,c,commands=self.fixture(now=5)
        x.fetch()
        self.assertEqual(c.sleeps,[])
        self.assertEqual(commands[0][0],5)

    def test_positive_wait_and_minimum_spacing(self):
        x,c,commands=self.fixture(now=4.9)
        x.fetch(); first=x.last_fetch
        x.fetch()
        self.assertGreaterEqual(x.last_fetch-first,5)
        self.assertTrue(all(0<s<=.05 for s in c.sleeps))
        self.assertEqual(x.fetches,2)
        self.assertEqual(len(commands),4)

    def test_deadline_crossed_in_check_no_dispatch(self):
        x,c,commands=self.fixture(deadline=5)
        x.runner.check=lambda:setattr(c,'now',5.01)
        with self.assertRaisesRegex(Rejected,'queue deadline'):x.fetch()
        self.assertEqual(commands,[])
        self.assertEqual(c.sleeps,[])
        self.assertEqual(x.fetches,0)

    def test_deadline_reached_after_wait_no_dispatch(self):
        x,c,commands=self.fixture(deadline=5)
        with self.assertRaisesRegex(Rejected,'queue deadline'):x.fetch()
        self.assertTrue(c.sleeps)
        self.assertEqual(commands,[])
        self.assertEqual(x.fetches,0)

    def test_cancel_at_boundary_no_dispatch(self):
        x,c,commands=self.fixture(now=5)
        def cancel():raise Rejected('cancelled fixture')
        x.runner.check=cancel
        with self.assertRaisesRegex(Rejected,'cancelled fixture'):x.fetch()
        self.assertEqual(commands,[])
        self.assertEqual(c.sleeps,[])
        self.assertEqual(x.fetches,0)

    def test_cancel_after_wait_no_dispatch(self):
        x,c,commands=self.fixture()
        def cancel():
            if c.sleeps:raise Rejected('cancelled fixture')
        x.runner.check=cancel
        with self.assertRaisesRegex(Rejected,'cancelled fixture'):x.fetch()
        self.assertTrue(c.sleeps)
        self.assertEqual(commands,[])
        self.assertEqual(x.fetches,0)

    def test_cap_and_poison_prevent_dispatch(self):
        x,c,commands=self.fixture(now=5)
        x.fetches=359
        x.fetch()
        with self.assertRaisesRegex(Rejected,'fetch cap'):x.fetch()
        self.assertEqual(x.fetches,360)
        self.assertEqual(len(commands),2)
        x.fetches=0; x.failed=True
        with self.assertRaisesRegex(Rejected,'fetch cap'):x.fetch()
        self.assertEqual(len(commands),2)


if __name__=='__main__':unittest.main()
