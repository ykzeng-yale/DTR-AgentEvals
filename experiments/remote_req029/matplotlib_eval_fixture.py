"""Inert subprocess injection only; no production CLI accepts fixtures."""
import json,os,subprocess,sys,time
from pathlib import Path
from matplotlib_eval_contract import *
from matplotlib_eval_backend import Backend
from matplotlib_eval_guardian import Guardian
class Fake(Backend):
    def __init__(self,root,contract,fake_root):
        super().__init__(root,contract);self.fake_root=Path(fake_root)
        self.prefix=[sys.executable,str(HERE/'matplotlib_eval_fake_docker.py'),str(fake_root)]
        self.archive=self.fake_root/'archive'
    def verify(self,deadline):
        require(self.archive.read_bytes()==b'inert archive','fixture archive')
        require(not self.call(['ps','-q'],deadline)['output'].strip(),'peer')
        image=json.loads(self.call(['image','inspect','fixed'],deadline)['output'])[0]
        require(image['Id']==self.contract['image'],'fixture image')
def launch(spec,path,mode=''):
    root=path.parent/'fake';root.mkdir()
    (root/'archive').write_bytes(b'inert archive');(root/'mode').write_text(mode)
    spec['fake_root']=str(root);path.write_text(json.dumps(spec))
    with (path.parent/'guardian.stderr').open('xb') as err:
        return subprocess.Popen([sys.executable,__file__,'guardian',str(path)],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=err,start_new_session=True)
if __name__=='__main__':
    if sys.argv[1]=='guardian':
        s=json.loads(Path(sys.argv[2]).read_bytes())
        g=Guardian(s,Fake(Path(s['root'])/'docker',s['release']['sandbox'],s['fake_root']))
        if (Path(s['fake_root'])/'mode').read_text()=='journal-fail':
            original=g.save
            def save(name,value):
                if name=='helper.prepare.raw.json':raise OSError('injected journal failure')
                return original(name,value)
            g.save=save
        g.run()
    elif sys.argv[1]=='driver':
        from matplotlib_eval_evaluate import run
        r=json.loads(Path(sys.argv[2]).read_bytes())
        def start(s,path):
            p=launch(s,path,'hang')
            (Path(sys.argv[3]).parent/'guardian.pid').write_text(str(p.pid))
            return p
        run(r,'fixture-pin',{},Path(sys.argv[3]),start)
