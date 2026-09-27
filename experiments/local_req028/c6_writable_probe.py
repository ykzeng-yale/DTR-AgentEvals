"""Fixed authored W1 probe; never accepts or executes model output."""
import json, os, shutil, subprocess
from pathlib import Path
assert subprocess.check_output(['git','-C','/testbed','rev-parse','HEAD'],text=True).strip()=='a4ae7a3808de3c53b0788875b6c97b20d5a12ee0'
shutil.copytree('/testbed','/work/testbed',symlinks=True)
os.chdir('/work/testbed')
import sys
sys.path.insert(0,'/work/testbed')
import astropy
assert str(Path(astropy.__file__).resolve()).startswith('/work/testbed/'), astropy.__file__
p=Path('/work/testbed/.dtr_writable_probe');p.write_text('DTR_WRITABLE_SENTINEL\n')
status=subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],text=True)
assert '.dtr_writable_probe' in status
readonly=False
try:Path('/dtr_forbidden_root').write_text('must fail')
except OSError as e:readonly=e.errno==30
assert readonly
v=os.statvfs('/work');assert v.f_blocks*v.f_frsize<=512*1024**2
print(json.dumps({'git_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'astropy_file':astropy.__file__,'workspace_total_bytes':v.f_blocks*v.f_frsize,'workspace_free_bytes':v.f_bavail*v.f_frsize,'sentinel_visible':True,'root_readonly':readonly,'interfaces':os.listdir('/sys/class/net'),'status':'PASS'}))
