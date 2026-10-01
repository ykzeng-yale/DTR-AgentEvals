"""Authored deterministic fixtures: no benchmark task code or model runs."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import pytest

spec = importlib.util.spec_from_file_location("history_audit", Path(__file__).with_name("source_history_audit.py"))
audit = importlib.util.module_from_spec(spec); spec.loader.exec_module(audit)

def git(tree, *args):
    return subprocess.check_output(["/usr/bin/git", "-c", "core.hooksPath=/dev/null", "-c", "user.name=Authored Fixture", "-c", "user.email=fixture@example.invalid", "-C", str(tree), *args], env={"PATH":"/usr/bin:/bin", "HOME":str(tree.parent), "GIT_CONFIG_NOSYSTEM":"1", "GIT_CONFIG_GLOBAL":"/dev/null"}, stderr=subprocess.PIPE)

def save(path, value): path.write_bytes(audit.canonical(value))

def archive(tree, path):
    with tarfile.open(path, "w") as stream: stream.add(tree, arcname="testbed")

@pytest.fixture
def authored(tmp_path):
    original=tmp_path/"original"; original.mkdir(); git(original,"init","--quiet")
    (original/"module.py").write_text("AUTHORED INERT BYTES: never import this file\n")
    (original/".gitignore").write_text("native.bin\n")
    git(original,"add","."); git(original,"commit","-qm","Authored inert base")
    base=git(original,"rev-parse","HEAD").decode().strip(); tree=git(original,"rev-parse","HEAD^{tree}").decode().strip()
    (original/"native.bin").write_bytes(b"AUTHORED INERT NATIVE BYTES")
    normalized=tmp_path/"normalized"; shutil.copytree(original,normalized)
    # Produce a fresh detached public-base fixture with one exact object closure.
    git(normalized,"checkout","--detach","--quiet",base)
    git(normalized,"update-ref","-d","refs/heads/master")
    for ref in git(normalized,"for-each-ref","--format=%(refname)").decode().splitlines(): git(normalized,"update-ref","-d",ref)
    shutil.rmtree(normalized/".git/hooks"); shutil.rmtree(normalized/".git/logs")
    (normalized/".git/config").write_text("[core]\nrepositoryformatversion = 0\nfilemode = true\nbare = false\nlogAllRefUpdates = false\n")
    original_tar=tmp_path/"original.tar"; norm_tar=tmp_path/"normalized.tar"; archive(original,original_tar); archive(normalized,norm_tar)
    norm={"task_id":audit.TASK_IDS[0],"base_commit":base,"head":base,"tree":tree,"base_tree":tree,"accepted":True,"original_head":base,
        "original_source_sha256":audit.digest(original_tar),"source_tar_sha256":audit.digest(norm_tar),"original_delta_paths":[],"original_delta_sha256":hashlib.sha256(b"").hexdigest()}
    normalization=tmp_path/"normalization.json"; acceptance=tmp_path/"acceptance.json"; save(normalization,norm); save(acceptance,norm)
    return {"task_id":audit.TASK_IDS[0],"base_commit":base,"normalized_archive":norm_tar,"original_archive":original_tar,"normalization_receipt":normalization,"acceptance_receipt":acceptance,"expected_original_sha256":audit.digest(original_tar)},normalized

def rewrite(args, normalized):
    args["normalized_archive"].unlink(); archive(normalized,args["normalized_archive"])
    for key in ("normalization_receipt","acceptance_receipt"):
        value=audit.load(args[key]); value["source_tar_sha256"]=audit.digest(args["normalized_archive"]); save(args[key],value)

def test_complete_authored_source_and_native_proof(authored):
    args,_=authored; result=audit.audit_task(**args)
    assert result["accepted"],result
    assert result["checks"]["retained_ignored_native"]["file_count"]==1
    assert result["checks"]["history"]["object_closure_equal"]

@pytest.mark.parametrize("mutation",["ref","remote","hook","reflog","alternate","graft","tracked","native","untracked","future_object","index"])
def test_boundary_mutations_are_rejected_even_with_rehashed_archive(authored,mutation):
    args,norm=authored
    if mutation=="ref": git(norm,"update-ref","refs/heads/future",args["base_commit"])
    elif mutation=="remote": (norm/".git/config").write_text((norm/".git/config").read_text()+"[remote \"private\"]\nurl = /never-read\n")
    elif mutation=="hook": (norm/".git/hooks").mkdir(); (norm/".git/hooks/post-checkout").write_text("NEVER EXECUTE")
    elif mutation=="reflog": (norm/".git/logs").mkdir()
    elif mutation=="alternate": (norm/".git/objects/info/alternates").write_text("/never-read\n")
    elif mutation=="graft": (norm/".git/info/grafts").write_text(args["base_commit"]+"\n")
    elif mutation=="tracked": (norm/"module.py").write_text("CHANGED INERT BYTES")
    elif mutation=="native": (norm/"native.bin").write_bytes(b"CHANGED NATIVE BYTES")
    elif mutation=="untracked": (norm/"exposed_reference.txt").write_text("AUTHORED INERT UNKNOWN")
    elif mutation=="future_object": subprocess.run(["/usr/bin/git","-C",str(norm),"hash-object","-w","--stdin"],input=b"AUTHORED UNREACHABLE BYTES",check=True,stdout=subprocess.PIPE)
    elif mutation=="index": git(norm,"update-index","--force-remove","module.py")
    rewrite(args,norm); result=audit.audit_task(**args)
    assert not result["accepted"],(mutation,result)

@pytest.mark.parametrize("kind",["traversal","symlink","hardlink","duplicate","special"])
def test_tar_boundary_refused(tmp_path,kind):
    path=tmp_path/"bad.tar"
    with tarfile.open(path,"w") as stream:
        member=tarfile.TarInfo("testbed/../../escaped" if kind=="traversal" else "testbed/item")
        if kind=="symlink": member.type=tarfile.SYMTYPE; member.linkname="/never-read"
        if kind=="hardlink": member.type=tarfile.LNKTYPE; member.linkname="testbed/item"
        if kind=="special": member.type=tarfile.FIFOTYPE
        stream.addfile(member)
        if kind=="duplicate": stream.addfile(member)
    with pytest.raises(ValueError): audit.safe_extract(path,tmp_path/"extract")

@pytest.mark.parametrize("kind", ["safe", "absolute", "escape", "wrong_target", "hardlink", "metadata", "link_child"])
def test_bounded_link_extraction(tmp_path, kind):
    import io
    archive_path = tmp_path / "links.tar"
    name = next(iter(audit.SAFE_LINKS)); link = audit.SAFE_LINKS[name]
    import posixpath
    target = posixpath.normpath(posixpath.join(posixpath.dirname(name), link))
    with tarfile.open(archive_path, "w") as out:
        m=tarfile.TarInfo("testbed/.git"); m.type=tarfile.DIRTYPE; out.addfile(m)
        m=tarfile.TarInfo("testbed/"+target); m.size=1; out.addfile(m,io.BytesIO(b"x"))
        m=tarfile.TarInfo("testbed/"+name); m.type=tarfile.SYMTYPE; m.linkname=link
        if kind=="absolute": m.linkname="/tmp/escape"
        if kind=="escape": m.linkname="../../../../../../../../escape"
        if kind=="wrong_target": m.linkname="other.py"
        if kind=="hardlink": m.type=tarfile.LNKTYPE
        if kind=="metadata": m.name="testbed/.git/config"
        out.addfile(m)
        if kind=="link_child":
            m=tarfile.TarInfo("testbed/"+name+"/child"); m.size=1; out.addfile(m,io.BytesIO(b"x"))
    if kind=="safe":
        receipt=audit.safe_extract(archive_path,tmp_path/"unpacked")
        assert receipt["reviewed_in_tree_symlinks"]==1
    else:
        with pytest.raises((ValueError,OSError)): audit.safe_extract(archive_path,tmp_path/"unpacked")

@pytest.mark.parametrize('case', ['known', 'other_error', 'unreachable', 'wrong_base', 'rerun_failure'])
def test_legacy_metadata_exception_is_narrow(authored, tmp_path, monkeypatch, case):
    args, tree = authored
    wrapper = audit.Git(tree, tmp_path / 'review_git')
    original = wrapper.run
    base = args['base_commit']
    monkeypatch.setattr(audit, 'REQUESTS_BASE', base if case != 'wrong_base' else '0' * 40)
    def run(*parts, **kwargs):
        if parts[0] == 'fsck':
            wrapper.last_code = 4
            wrapper.last_error = audit.REQUESTS_FSCK if case != 'other_error' else b'corrupt object'
            return b'dangling object\n' if case == 'unreachable' else b''
        if parts[:2] == ('-c', 'fsck.badTimezone=ignore') and case == 'rerun_failure':
            raise ValueError('remaining corruption')
        return original(*parts, **kwargs)
    wrapper.run = run
    if case == 'known':
        result = audit.check_history(tree, wrapper, base)
        assert result['reviewed_legacy_metadata_diagnostic'] == audit.REQUESTS_FSCK.decode()
    else:
        with pytest.raises(ValueError): audit.check_history(tree, wrapper, base)

@pytest.mark.parametrize('mutation', ['blob', 'link', 'platform_setting'])
def test_symlink_blob_and_platform_metadata_fail_closed(tmp_path, authored, mutation):
    args, tree = authored
    if mutation == 'platform_setting':
        config=tree/'.git/config'
        config.write_text(config.read_text()+'ignorecase = false\n')
        wrapper=audit.Git(tree,tmp_path/'metadata_wrapper')
        with pytest.raises(ValueError):audit.check_history(tree,wrapper,args['base_commit'])
        return
    name=next(iter(audit.SAFE_LINKS));path=tree/name;path.parent.mkdir(parents=True)
    link=audit.SAFE_LINKS[name]
    path.symlink_to(link if mutation=='blob' else '/tmp/untrusted')
    class Wrapper:
        def __init__(self):self.tree=tree
        def run(self,*parts,**kwargs):return b'1'*40+b'\n'
    with pytest.raises(ValueError):audit.check_worktree(Wrapper(),{name:('120000','0'*40)})

def test_independent_blob_framing_matches_trusted_git(tmp_path):
    data=b'authored bytes\x00\xff\n'
    path=tmp_path/'blob';path.write_bytes(data)
    expected=subprocess.check_output(['/usr/bin/git','hash-object','--stdin'],input=data).decode().strip()
    assert audit.blob_digest(path=path)==expected
    assert audit.blob_digest(data=data)==expected
