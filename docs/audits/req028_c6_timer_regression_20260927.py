"""Retrospective deterministic reproduction; no Git, model or container execution."""
import sys,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'experiments/remote_req028'))
from c6_git import Transport
from types import SimpleNamespace
x=Transport.__new__(Transport);x.failed=False;x.fetches=0;x.last_fetch=0;x.interval=5;x.deadline=100;x.runner=SimpleNamespace(check=lambda:None)
sleeps=[]
def sleep(n):
 sleeps.append(n)
 if n<0:raise ValueError('sleep length must be non-negative')
with patch('c6_git.time.time',side_effect=[4.99,4.99,5.01]),patch('c6_git.time.sleep',sleep):
 try:x.fetch()
 except ValueError as e:print(json.dumps({'reproduced':True,'error':str(e),'sleep_arguments':sleeps,'scope':'clock crosses interval between loop test and sleep computation'}))
 else:raise AssertionError('expected original race')
