"""Fixed source passed to container Python -c. NEVER execute this module on host."""
# The host reads CODE as source data. Generated commands arrive only on container stdin.
CODE = r'''
import json,os,subprocess,sys
from pathlib import Path
s=json.loads(sys.stdin.buffer.read(65537))
op=s['operation'];os.chdir('/testbed')
if op=='execute':
    command=s['command'];assert isinstance(command,str) and len(command.encode())<=65536
    env=dict(os.environ,PAGER='cat',MANPAGER='cat',LESS='-R',PIP_PROGRESS_BAR='off',TQDM_DISABLE='1')
    p=subprocess.run(['bash','-lc',command],stdin=subprocess.DEVNULL,env=env)
    sys.exit(p.returncode)
elif op=='diff':
    env=dict(os.environ,GIT_CONFIG_GLOBAL='/dev/null',GIT_CONFIG_SYSTEM='/dev/null',GIT_CONFIG_NOSYSTEM='1')
    git=['/usr/bin/git','--no-pager','-c','core.hooksPath=/dev/null','-c','diff.external=']
    subprocess.run(git+['add','--intent-to-add','--all'],env=env,check=True,stdout=subprocess.DEVNULL)
    sys.exit(subprocess.run(git+['diff','--no-ext-diff','--no-textconv','--binary','HEAD'],env=env).returncode)
elif op=='preflight':
    assert subprocess.check_output(['/usr/bin/git','rev-parse','HEAD'],text=True).strip()=='a4ae7a3808de3c53b0788875b6c97b20d5a12ee0'
    import astropy
    assert str(Path(astropy.__file__).resolve()).startswith('/testbed/')
    assert sys.executable=='/opt/miniconda3/envs/testbed/bin/python'
    mounts={line.split()[1]:line.split()[3].split(',') for line in Path('/proc/mounts').read_text().splitlines()}
    assert all(k in mounts['/testbed'] for k in ('rw','nosuid','nodev')) and 'noexec' not in mounts['/testbed']
    assert 'ro' in mounts['/']
    for name,size in (('/testbed',512*1024**2),('/tmp',64*1024**2)):
        v=os.statvfs(name);assert v.f_blocks*v.f_frsize==size
    p=Path('/testbed/.c6-preflight');p.write_text('fixed writable probe');p.unlink()
    assert os.listdir('/sys/class/net')==['lo']
    print(json.dumps({'head':'a4ae7a3808de3c53b0788875b6c97b20d5a12ee0','python':sys.executable,
        'import_path':astropy.__file__,'writable':True,'limits_verified':True}))
else:raise ValueError('fixed helper operation')
'''
