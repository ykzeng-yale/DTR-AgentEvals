"""No-model integration tests: deadline, parent death, independent cleanup."""
import json,subprocess,sys,time
from pathlib import Path
import guard
ROOT=Path(__file__).resolve().parents[2]
out=ROOT/'results/remote_req028'/('watchdog_fake_tests_'+(sys.argv[1] if len(sys.argv)>1 else 'v2')+'_20260927')
out.mkdir(parents=True,exist_ok=False)
results=[]
decoy=subprocess.Popen(['/bin/sleep','30'],start_new_session=True)
try:
    for case,seconds in [('deadline',2),('parent_death',20),('python_launcher',2)]:
        folder=out/case
        command=[sys.executable,'-c','import time; time.sleep(25)'] if case=='python_launcher' else ['/bin/sleep','25']
        supervisor=subprocess.Popen([sys.executable,str(Path(guard.__file__)),'run',str(folder),str(seconds),*command],stdout=subprocess.PIPE,text=True)
        info=json.loads(supervisor.stdout.readline())
        record=json.loads((folder/'ownership.json').read_text())
        if case=='parent_death':
            supervisor.kill();supervisor.wait()
        else:supervisor.wait(timeout=12)
        limit=time.time()+10
        while time.time()<limit and not (folder/'ownership.abort.json').exists():time.sleep(.1)
        abort=json.loads((folder/'ownership.abort.json').read_text())
        assert abort['reason']==('owner_parent_exited' if case=='parent_death' else 'deadline'),abort
        assert abort['owned_stop'] and not guard.same(record)
        assert decoy.poll() is None
        results.append({'case':case,'passed':True,'abort':abort,'decoy_untouched':True})
finally:
    decoy.terminate();decoy.wait()
(out/'receipt.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
