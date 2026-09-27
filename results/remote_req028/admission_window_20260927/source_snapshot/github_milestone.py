"""Use existing Git credential helper in memory; never log or persist credentials."""
import base64,json,subprocess,sys,urllib.request
from pathlib import Path
result=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',text=True,capture_output=True)
if result.returncode:
    print(json.dumps({'status':'existing_credentials_unavailable'}));sys.exit(1)
credential=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
token=base64.b64encode((credential.get('username','')+':'+credential.get('password','')).encode()).decode()
headers={'Authorization':'Basic '+token,'Accept':'application/vnd.github+json','User-Agent':'DTR-REQ-028-worker'}
def call(path,data=None):
    req=urllib.request.Request('https://api.github.com/repos/ykzeng-yale/DTR-AgentEvals'+path,data=None if data is None else json.dumps(data).encode(),headers=headers)
    with urllib.request.urlopen(req,timeout=20) as response:return json.load(response)
permissions=call('').get('permissions',{})
if len(sys.argv)==1:print(json.dumps({'permissions':permissions}))
else:
    assert permissions.get('push')
    response=call('/issues/4/comments',{'body':Path(sys.argv[1]).read_text()})
    print(json.dumps({'posted':response['html_url'],'id':response['id']}))
