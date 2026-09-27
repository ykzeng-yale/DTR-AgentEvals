"""Fixed authored source/import probe; no generated command or task tests."""
import json,os,subprocess,sys
from pathlib import Path
os.chdir('/testbed')
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
base='a0d2e399729d36499a1924e5ca5bc067c8396810';head=git('rev-parse','HEAD')
assert head==base or git('rev-parse','HEAD^')==base,'unexpected task setup ancestry'
assert not git('status','--porcelain','--untracked-files=no'),'dirty tracked source'
import matplotlib
import matplotlib._path
import matplotlib.ft2font
assert str(Path(matplotlib.__file__).resolve()).startswith('/testbed/')
assert all(str(Path(m.__file__).resolve()).startswith('/testbed/') for m in (matplotlib._path,matplotlib.ft2font))
assert sys.executable=='/opt/miniconda3/envs/testbed/bin/python'
mounts={x.split()[1]:x.split()[3].split(',') for x in Path('/proc/mounts').read_text().splitlines()}
assert 'ro' in mounts['/'] and all(x in mounts['/testbed'] for x in ('rw','nosuid','nodev')) and 'noexec' not in mounts['/testbed']
p=Path('/testbed/.dtr_writable_probe');p.write_text('DTR_WRITABLE_SENTINEL\n')
assert '.dtr_writable_probe' in git('status','--porcelain','--untracked-files=all')
readonly=False
try:Path('/dtr_forbidden_root').write_text('must fail')
except OSError as e:readonly=e.errno==30
assert readonly and os.listdir('/sys/class/net')==['lo']
v=os.statvfs('/testbed');assert v.f_blocks*v.f_frsize==512*1024**2
print(json.dumps({'status':'PASS','base':base,'head':head,'setup_diff_stat':git('diff','--stat',base,'HEAD'),'setup_diff':git('diff',base,'HEAD'),'environment':dict(zip(('system','release','version','machine'),__import__('platform').uname()[:1]+__import__('platform').uname()[2:5])),'python':sys.executable,'matplotlib_file':matplotlib.__file__,'workspace_total_bytes':v.f_blocks*v.f_frsize,'workspace_free_bytes':v.f_bavail*v.f_frsize,'root_readonly':readonly,'interfaces':os.listdir('/sys/class/net')}))
