"""Exclusive atomic local IPC publication, not partially visible JSON files."""
import os,uuid
from pathlib import Path
from c6_protocol import put

def publish(root,name,value):
    root=Path(root);path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.parent/('.pending-'+uuid.uuid4().hex)
    put(temp.parent,temp.name,value)
    try:os.link(temp,path)
    finally:temp.unlink()
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
