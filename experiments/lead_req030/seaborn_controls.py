"""Frozen offline baseline/reference controls. Never imported by prompt/model code."""
import hashlib,json,os,subprocess,sys,tarfile,time
from pathlib import Path
D=json.loads(Path('evaluation_inputs.json').read_text());BASE='22cdfb0c93f8ec78492d87edb810f10cb7f57a31'
assert D['instance_id']=='mwaskom__seaborn-3187' and D['base_commit']==BASE
assert len(D['FAIL_TO_PASS'])==2 and len(D['PASS_TO_PASS'])==248
IMAGE='/home/yz2324/project_pi_gt353/yz2324/DTR-AgentEvals/req030-seaborn-image-20260928-a/task.sif'
ARCHIVE='/home/yz2324/project_pi_gt353/yz2324/DTR-AgentEvals/req030-seaborn-export-20260928-a/testbed.tar'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(IMAGE)=='9da1f51cb8c01a6ad9e0db4d1969742fbec995021e78150a9623d4f4719a8a47'
assert sha(ARCHIVE)=='317705a1463c5ac9fca593d7349f7ed0099a5d574d23117cebcafdd5014e60e0'
for mode in ('baseline','reference'):
 work=Path(mode);work.mkdir(mode=0o700)
 seed=work/'seed';seed.mkdir()
 with tarfile.open(ARCHIVE) as t:
  ms=t.getmembers()
  assert len(ms)==400 and all(m.isfile() or m.isdir() for m in ms)
  assert all(m.name=='testbed' or m.name.startswith('testbed/') for m in ms)
  t.extractall(seed)
 image=work/'workspace.img'
 with open(image,'wb') as f:f.truncate(512*1024*1024)
 with open(work/'mkfs.log','wb') as f:subprocess.run(['mkfs.ext3','-F','-m','0','-d',str(seed/'testbed'),str(image)],stdout=f,stderr=subprocess.STDOUT,timeout=60,check=True)
 for field,value in [('uid',os.getuid()),('gid',os.getgid())]:subprocess.run(['debugfs','-w','-R',f'set_inode_field / {field} {value}',str(image)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=15,check=True)
 script=['#!/bin/bash','set -euo pipefail','cd /testbed','git diff --quiet '+BASE+' HEAD || exit 90','export MPLCONFIGDIR=/tmp/mpl','mkdir -p "$MPLCONFIGDIR"']
 if mode=='reference':script+=['git apply --check /dev/stdin'] # replaced below with bound fixed files
 # Patch application uses an exact evaluator-only file exposed at /tmp through stdin script heredoc.
 if mode=='reference':
  ref=Path('reference.diff').read_text();script+=['git apply <<\'DTR_REFERENCE\'\n'+ref+'\nDTR_REFERENCE']
 patch=D['test_patch'];script+=['git checkout '+BASE+' tests/_core/test_plot.py tests/test_relational.py','git apply <<\'DTR_TEST_PATCH\'\n'+patch+'\nDTR_TEST_PATCH','git diff --stat','echo ">>>>> Start Test Output"','pytest --no-header -rA tests/_core/test_plot.py tests/test_relational.py','status=$?','echo ">>>>> End Test Output"','exit "$status"']
 # Preserve pytest exit1 while still emitting end marker.
 script=[x if x!='set -euo pipefail' else 'set -uo pipefail' for x in script]
 script=[x for x in script if x!='git apply --check /dev/stdin']
 (work/'eval.sh').write_text('\n'.join(script)+'\n')
 cmd=['apptainer','exec','--containall','--cleanenv','--no-home','--no-mount','hostfs,bind-paths','--net','--network','none','--pwd','/','--bind',str(image.resolve())+':/testbed:image-src=/',IMAGE,'/bin/bash','-s']
 out=work/'raw.log';r,w=os.pipe()
 cmd=[sys.executable,'bounded_supervisor.py','--owner-fd',str(r),'--out',str(out),'--receipt',str(work/'supervisor.json'),'--seconds','600','--cap',str(4*1024*1024),'--']+cmd
 with open(work/'eval.sh','rb') as inp:
  p=subprocess.Popen(cmd,stdin=inp,pass_fds=(r,))
  os.close(r)
  try:p.wait(timeout=630)
  finally:
   os.close(w)
   if p.poll() is None:p.kill();p.wait()
 sup=json.loads((work/'supervisor.json').read_text())
 data=out.read_bytes()
 (work/'receipt.json').write_text(json.dumps(dict(mode=mode,supervisor=sup,raw_sha256=sha(out),raw_bytes=len(data),workspace_sha256=sha(image)),indent=2)+'\n')
 # An infrastructure error prevents the second arm from running.
 if not (data.count(b'>>>>> Start Test Output')==data.count(b'>>>>> End Test Output')==1 and sup['reason']=='exited' and sup['returncode'] in (0,1)):raise RuntimeError('invalid evaluator output')
