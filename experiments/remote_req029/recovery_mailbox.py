"""Bounded immutable REQ029O mailbox helper. Data only; no command execution."""
import hashlib,json,os,re,sys,tempfile
from pathlib import Path
LIMIT=1048576
KINDS={'request':'controller','observation':'controller','response':'worker','preflight':'controller','ready':'worker','controller_terminal':'controller','worker_terminal':'worker'}
def encode(v):return (json.dumps(v,sort_keys=True,separators=(',',':'))+'\n').encode()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def exchange(root,role,q):
    root=Path(root)
    require(root.is_dir() and not root.is_symlink(),'owned root missing')
    require(role in ('controller','worker'),'role')
    require(set(q)=={'operation','kind','sequence','payload'},'request schema')
    kind=q['kind'];seq=q['sequence'];require(kind in KINDS,'kind')
    sequenced=kind in ('request','response','observation')
    require((sequenced and type(seq) is int and 1<=seq<=24) or (not sequenced and seq is None),'sequence')
    name=kind+('' if seq is None else '-%02d'%seq)+'.json'
    path=root/name
    require(not path.is_symlink(),'symlink rejected')
    if q['operation']=='publish':
        require(KINDS[kind]==role,'role ownership')
        raw=encode(q['payload']);require(len(raw)<=LIMIT,'payload cap')
        # Same-directory temp + atomic no-clobber link. A crash may leave a temp,
        # never a partial final object. Unknown outcome must be inspected, not retried.
        fd,tmp=tempfile.mkstemp(prefix='.pending-',dir=root)
        try:
            with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
            try:os.link(tmp,path)
            except FileExistsError:
                require(path.stat().st_size<=LIMIT and path.read_bytes()==raw,'immutable conflict')
            d=os.open(root,os.O_RDONLY)
            try:os.fsync(d)
            finally:os.close(d)
        finally:os.unlink(tmp)
    else:require(q['operation']=='read' and q['payload'] is None,'read schema')
    if not path.exists():return {'present':False}
    require(path.is_file() and path.stat().st_size<=LIMIT,'stored object cap')
    raw=path.read_bytes()
    return dict(present=True,payload=json.loads(raw),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),name=name)
def main():
    raw=sys.stdin.buffer.read(LIMIT+4097);require(len(raw)<=LIMIT+4096,'request cap')
    print(json.dumps(exchange(sys.argv[1],sys.argv[2],json.loads(raw)),sort_keys=True))
if __name__=='__main__':main()
