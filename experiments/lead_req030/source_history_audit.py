#!/usr/bin/env python3
"""Independent prospective AL source audit. No task code is imported or executed.

All Git reads use a fresh, trusted metadata wrapper containing only copied
objects/HEAD/shallow/index; archived repository configuration is never loaded.
This module deliberately imports no production experiment implementation.
"""
from __future__ import annotations
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile

SCHEMA = "dtr.req030al.independent_source_history.v2"
MAX_ARCHIVE = 8 << 30
MAX_MEMBER = 512 << 20
MAX_MEMBERS = 1_000_000
SPHINX = "sphinx-doc__sphinx-8593"
SPHINX_DELTA = "71dbabe891e7add5c0a2dad354e65b233ac74aef3fd5888532515acee48872d9"
SAFE_LINKS = {'tests/functional/s/symlink/_binding/__init__.py': '../symlink_module/__init__.py', 'tests/functional/s/symlink/_binding/symlink_module.py': '../symlink_module/symlink_module.py', 'docs/_theme/djangodocs-epub/static/docicons-behindscenes.png': '../../djangodocs/static/docicons-behindscenes.png', 'docs/_theme/djangodocs-epub/static/docicons-note.png': '../../djangodocs/static/docicons-note.png', 'docs/_theme/djangodocs-epub/static/docicons-philosophy.png': '../../djangodocs/static/docicons-philosophy.png', 'docs/_theme/djangodocs-epub/static/docicons-warning.png': '../../djangodocs/static/docicons-warning.png', 'build/freetype-2.6.1/objs/.libs/libfreetype.la': '../libfreetype.la', 'lib/matplotlib/mpl-data/images/back-symbolic.svg': 'back.svg', 'lib/matplotlib/mpl-data/images/filesave-symbolic.svg': 'filesave.svg', 'lib/matplotlib/mpl-data/images/forward-symbolic.svg': 'forward.svg', 'lib/matplotlib/mpl-data/images/help-symbolic.svg': 'help.svg', 'lib/matplotlib/mpl-data/images/home-symbolic.svg': 'home.svg', 'lib/matplotlib/mpl-data/images/move-symbolic.svg': 'move.svg', 'lib/matplotlib/mpl-data/images/subplots-symbolic.svg': 'subplots.svg', 'lib/matplotlib/mpl-data/images/zoom_to_rect-symbolic.svg': 'zoom_to_rect.svg'}
REQUESTS_BASE = "0192aac24123735b3eaf9b08df46429bb770c283"
REQUESTS_FSCK = b"error in commit 5e6ecdad9f69b1ff789a17733b8edc6fd7091bd8: badTimezone: invalid author/committer line - bad time zone"
TASK_IDS = ("django__django-12039", "matplotlib__matplotlib-26208", "psf__requests-6028",
    "pydata__xarray-6461", "pylint-dev__pylint-6386", "pytest-dev__pytest-10081",
    "scikit-learn__scikit-learn-25102", SPHINX)

def digest(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file(): raise ValueError("bounded ordinary file required")
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""): value.update(block)
    return value.hexdigest()

def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()

def load(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 << 20:
        raise ValueError("bounded ordinary JSON required")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError("duplicate receipt key")
            result[key] = value
        return result
    value = json.loads(path.read_bytes(), object_pairs_hook=unique)
    if not isinstance(value, dict): raise ValueError("receipt object required")
    return value

def safe_extract(archive, target):
    archive, target = Path(archive), Path(target)
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_size > MAX_ARCHIVE:
        raise ValueError("source archive exceeds ordinary 8 GiB cap")
    target.mkdir(mode=0o700, parents=True, exist_ok=False)
    seen = set(); total = 0; count = 0; links = []
    with tarfile.open(archive, "r:") as stream:
        for member in stream:
            count += 1
            if count > MAX_MEMBERS: raise ValueError("source member-count cap")
            name = member.name.rstrip("/")
            pieces = name.split("/")
            if (not name or name.startswith("/") or any(p in ("", ".", "..") for p in pieces)
                    or pieces[0] != "testbed" or "\x00" in name):
                raise ValueError("source traversal or root mismatch")
            relative = PurePosixPath(*pieces[1:])
            if relative in seen: raise ValueError("duplicate source archive member")
            seen.add(relative)
            destination = target.joinpath(*relative.parts)
            if member.isdir(): destination.mkdir(mode=0o700, parents=True, exist_ok=True)
            elif member.isfile():
                if member.size < 0 or member.size > MAX_MEMBER: raise ValueError("512 MiB member cap")
                total += member.size
                if total > MAX_ARCHIVE: raise ValueError("8 GiB unpacked cap")
                destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                source = stream.extractfile(member)
                if source is None: raise ValueError("missing archive payload")
                fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
                with os.fdopen(fd, "wb") as output: shutil.copyfileobj(source, output, 1 << 20)
                destination.chmod(member.mode & 0o777)
                if destination.stat().st_size != member.size: raise ValueError("archive size mismatch")
            elif member.issym():
                if SAFE_LINKS.get(str(relative)) != member.linkname:
                    raise ValueError("unreviewed symlink refused")
                links.append((relative, member.linkname))
            else: raise ValueError("hardlink or special member refused")
    for relative, linkname in links:
        destination = target.joinpath(*relative.parts)
        if any(parent.is_symlink() for parent in destination.parents if parent.is_relative_to(target)):
            raise ValueError("symlink parent refused")
        resolved = (destination.parent / linkname).resolve()
        if not resolved.is_relative_to(target.resolve()) or not resolved.is_file() or resolved.is_symlink():
            raise ValueError("symlink target must be existing in-tree ordinary file")
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination.symlink_to(linkname)
    if not count or not (target / ".git").is_dir(): raise ValueError("task Git metadata absent")
    return {"member_count": count, "unpacked_bytes": total, "reviewed_in_tree_symlinks": len(links), "hardlinks_and_special_members": 0}

class Git:
    def __init__(self, tree, scratch, binary="/usr/bin/git"):
        tree, scratch = Path(tree), Path(scratch)
        binary = Path(binary)
        if not binary.is_absolute() or not binary.is_file(): raise ValueError("trusted absolute Git binary required")
        self.binary = str(binary); self.tree = tree; self.meta = scratch / "git"
        self.meta.mkdir(mode=0o700, parents=True)
        archived = tree / ".git"
        if archived.is_symlink() or not archived.is_dir(): raise ValueError("ordinary Git directory required")
        if any((archived / name).exists() for name in ("objects/info/alternates", "objects/info/http-alternates")) or list((archived / "objects").rglob("*.promisor")):
            raise ValueError("external/promisor object lookup refused even in original source")
        shutil.copytree(archived / "objects", self.meta / "objects")
        for name in ("HEAD", "shallow", "index"):
            if (archived / name).exists(): shutil.copyfile(archived / name, self.meta / name)
        (self.meta / "refs").mkdir()
        (self.meta / "config").write_text("[core]\nrepositoryformatversion = 0\nbare = false\nlogAllRefUpdates = false\n")
        (scratch / "home").mkdir()
        self.env = {"PATH": "/usr/bin:/bin", "HOME": str(scratch / "home"), "LANG": "C", "LC_ALL": "C",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat"}
        # Original HEAD may point to a branch. Copy its *data* only, never its config.
        if (archived / "refs").exists():
            shutil.rmtree(self.meta / "refs"); shutil.copytree(archived / "refs", self.meta / "refs")
        if (archived / "packed-refs").exists(): shutil.copyfile(archived / "packed-refs", self.meta / "packed-refs")
    def run(self, *arguments, data=None, allowed=(0,)):
        command = [self.binary, "--no-pager", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
            "-c", "core.untrackedCache=false", "-c", "protocol.allow=never", "--git-dir=" + str(self.meta),
            "--work-tree=" + str(self.tree), *arguments]
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            result = subprocess.run(command, input=data, stdin=subprocess.DEVNULL if data is None else None,
                stdout=out, stderr=err, env=self.env, cwd=self.meta.parent, timeout=180, check=False)
            if out.tell() > 128 << 20 or err.tell() > 1 << 20: raise ValueError("Git output cap")
            out.seek(0); err.seek(0); output, error = out.read(), err.read()
        self.last_code, self.last_error = result.returncode, error
        if result.returncode not in allowed: raise ValueError("read-only Git command failed: " + arguments[0] + ": " + error[:2048].decode("utf-8", "replace"))
        return output

def tree_entries(git, commit):
    entries = {}
    for record in git.run("ls-tree", "-rz", "--full-tree", commit).split(b"\0"):
        if not record: continue
        header, path = record.split(b"\t", 1); mode, kind, oid = header.decode().split()
        if kind != "blob" or mode not in ("100644", "100755", "120000"): raise ValueError("unsupported linked/submodule tree entry")
        relative = path.decode("utf-8", "strict")
        if Path(relative).is_absolute() or ".." in Path(relative).parts: raise ValueError("unsafe tracked path")
        entries[relative] = (mode, oid)
    return entries

def blob_digest(path=None, data=None):
    # Frozen repositories use Git SHA-1 objects. Recompute framing and bytes
    # independently, without thousands of per-file Git subprocesses.
    size = len(data) if data is not None else path.stat().st_size
    h = hashlib.sha1(("blob " + str(size) + "\0").encode())
    if data is not None: h.update(data)
    else:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1 << 20), b""): h.update(block)
    return h.hexdigest()

def check_worktree(git, entries):
    for name, (mode, oid) in entries.items():
        path = git.tree / name
        if mode == "120000":
            if not path.is_symlink() or SAFE_LINKS.get(name) != os.readlink(path):
                raise ValueError("unreviewed or altered tracked symlink")
            actual = blob_digest(data=os.readlink(path).encode())
            if actual != oid: raise ValueError("tracked symlink blob differs")
            continue
        if path.is_symlink() or not path.is_file(): raise ValueError("missing/linked tracked base file")
        actual = blob_digest(path=path)
        if actual != oid or bool(path.stat().st_mode & 0o111) != (mode == "100755"):
            raise ValueError("tracked worktree differs from Git tree: " + name)
    return len(entries)

def native_manifest(git, entries):
    files = {}
    for path in git.tree.rglob("*"):
        relative = path.relative_to(git.tree)
        if relative.parts[0] == ".git" or not path.is_file() or str(relative) in entries: continue
        if path.is_symlink():
            link = os.readlink(path)
            if SAFE_LINKS.get(str(relative)) != link: raise ValueError("unreviewed native symlink")
            files[str(relative)] = {"bytes": len(link.encode()), "sha256": hashlib.sha256(link.encode()).hexdigest(), "symlink": link}
        else:
            files[str(relative)] = {"bytes": path.stat().st_size, "sha256": digest(path), "executable": bool(path.stat().st_mode & 0o111)}
    if files:
        expected = set(files)
        output = git.run("check-ignore", "--no-index", "-z", "--stdin", data=("\0".join(sorted(files)) + "\0").encode(), allowed=(0, 1))
        if {p.decode() for p in output.split(b"\0") if p} != expected:
            raise ValueError("untracked non-ignored source member retained")
    return files

def check_history(tree, git, base):
    meta = tree / ".git"
    for name in ("logs", "hooks", "objects/info/alternates", "objects/info/http-alternates", "refs/remotes", "refs/replace", "info/grafts", "commondir", "gitdir", "worktrees", "modules", "FETCH_HEAD", "MERGE_HEAD", "AUTO_MERGE"):
        if (meta / name).exists(): raise ValueError("forbidden external/history metadata: " + name)
    if git.run("for-each-ref").strip(): raise ValueError("retained refs")
    if (meta / "packed-refs").exists() and any(line and not line.startswith(("#", "^")) for line in (meta / "packed-refs").read_text().splitlines()):
        raise ValueError("retained packed refs")
    config = configparser.RawConfigParser(strict=True); config.read(meta / "config")
    if set(config.sections()) != {"core"} or set(config["core"]) - {"repositoryformatversion", "filemode", "bare", "logallrefupdates", "ignorecase", "precomposeunicode"}:
        raise ValueError("nonfresh Git config/remotes/includes/filters")
    if any(config["core"].get(key) not in (None, "true") for key in ("ignorecase", "precomposeunicode")):
        raise ValueError("unreviewed platform Git setting")
    if config["core"].get("repositoryformatversion") != "0" or config["core"].get("bare") != "false" or config["core"].get("logallrefupdates") != "false":
        raise ValueError("unexpected fresh Git core config")
    if (meta / "HEAD").read_text().strip() != base: raise ValueError("HEAD is not detached exact public base")
    if (meta / "ORIG_HEAD").exists() and (meta / "ORIG_HEAD").read_text().strip() != base: raise ValueError("old future ORIG_HEAD retained")
    if list((meta / "objects").rglob("*.promisor")): raise ValueError("promisor object metadata retained")
    reachable = set(git.run("rev-list", "--objects", "--no-object-names", base).decode().splitlines())
    actual = set(git.run("cat-file", "--batch-all-objects", "--batch-check=%(objectname)").decode().splitlines())
    if not reachable or actual != reachable: raise ValueError("stored Git objects differ from public base reachable closure")
    fsck = git.run("fsck", "--full", "--no-reflogs", "--unreachable", allowed=(0, 4))
    legacy = None
    if git.last_code:
        if base != REQUESTS_BASE or fsck or git.last_error.strip() != REQUESTS_FSCK:
            raise ValueError("unreviewed fsck failure")
        legacy = REQUESTS_FSCK.decode()
        fsck = git.run("-c", "fsck.badTimezone=ignore", "fsck", "--full", "--no-reflogs", "--unreachable")
    if fsck.strip(): raise ValueError("dangling/unreachable Git objects retained")
    if git.run("rev-list", "--all", "--not", base).strip(): raise ValueError("nonbase reachable history retained")
    commits = set(git.run("rev-list", base).decode().splitlines())
    if (meta / "shallow").exists() and not set((meta / "shallow").read_text().splitlines()) <= commits:
        raise ValueError("unrelated shallow boundary retained")
    return {"detached_exact_base": True, "stored_object_count": len(actual), "base_reachable_commit_count": len(commits),
        "object_closure_equal": True, "refs_remotes_hooks_reflogs_alternates_replaces_absent": True,
        "fsck_unreachable_empty": True, "reviewed_legacy_metadata_diagnostic": legacy, "archived_config_never_loaded": True}

def audit_task(*, task_id, base_commit, normalized_archive, original_archive, normalization_receipt,
               acceptance_receipt, expected_original_sha256, expected_acceptance_sha256=None, git_binary="/usr/bin/git"):
    result = {"schema": SCHEMA, "task_id": task_id, "base_commit": base_commit, "accepted": False,
        "task_code_imported_or_executed": False, "original_archives_modified": False, "checks": {}, "error": None,
        "audit_source_sha256": digest(Path(__file__).absolute())}
    try:
        if task_id not in TASK_IDS or re.fullmatch("[0-9a-f]{40}", base_commit) is None: raise ValueError("frozen task/base identity required")
        norm, acceptance = load(normalization_receipt), load(acceptance_receipt)
        result.update(normalized_archive_sha256=digest(normalized_archive), original_archive_sha256=digest(original_archive),
            normalization_receipt_sha256=digest(normalization_receipt), acceptance_receipt_sha256=digest(acceptance_receipt))
        if expected_acceptance_sha256 is not None and result["acceptance_receipt_sha256"] != expected_acceptance_sha256: raise ValueError("source acceptance pin differs")
        if (result["original_archive_sha256"] != expected_original_sha256 or norm.get("original_source_sha256") != expected_original_sha256
                or norm.get("source_tar_sha256") != result["normalized_archive_sha256"] or acceptance.get("source_tar_sha256") != result["normalized_archive_sha256"]
                or norm.get("accepted") is not True or acceptance.get("accepted") is not True
                or norm.get("task_id") != task_id or acceptance.get("task_id") != task_id
                or any(r.get("head") != base_commit or r.get("tree") != r.get("base_tree") for r in (norm, acceptance))
                or norm.get("base_commit") != base_commit or norm.get("tree") != acceptance.get("tree")):
            raise ValueError("full archive/task/receipt/base-tree binding differs")
        if norm.get("source_tar_bytes") is not None and norm["source_tar_bytes"] != Path(normalized_archive).stat().st_size:
            raise ValueError("normalized archive receipt byte count differs")
        with tempfile.TemporaryDirectory(prefix="dtr-al-independent-source-") as scratch:
            scratch = Path(scratch); scratch.chmod(0o700)
            original = scratch / "original"; normalized = scratch / "normalized"
            result["checks"]["original_extraction"] = safe_extract(original_archive, original)
            result["checks"]["normalized_extraction"] = safe_extract(normalized_archive, normalized)
            old_git, new_git = Git(original, scratch / "old_git", git_binary), Git(normalized, scratch / "new_git", git_binary)
            old_head = old_git.run("rev-parse", "HEAD").decode().strip()
            old_tree = old_git.run("rev-parse", "HEAD^{tree}").decode().strip()
            if new_git.run("rev-parse", "HEAD").decode().strip() != base_commit: raise ValueError("normalized HEAD differs")
            tree = new_git.run("rev-parse", base_commit + "^{tree}").decode().strip()
            if tree != norm["tree"] or tree != acceptance["tree"]: raise ValueError("actual base tree differs from bound receipts")
            if old_git.run("rev-parse", base_commit + "^{tree}").decode().strip() != tree: raise ValueError("original public base tree differs")
            old_entries, entries = tree_entries(old_git, old_head), tree_entries(new_git, base_commit)
            check_worktree(old_git, old_entries); result["checks"]["tracked_base_files_verified"] = check_worktree(new_git, entries)
            index_entries = {}
            for record in new_git.run("ls-files", "--stage", "-z").split(b"\0"):
                if not record: continue
                header, name = record.split(b"\t", 1); mode, oid, stage = header.decode().split()
                if stage != "0": raise ValueError("nonbase unmerged index retained")
                index_entries[name.decode()] = (mode, oid)
            if index_entries != entries: raise ValueError("normalized index differs from public base tree")
            delta = old_git.run("diff", "--no-ext-diff", "--no-textconv", base_commit, old_head)
            paths = old_git.run("diff", "--no-ext-diff", "--no-textconv", "--name-only", base_commit, old_head).decode().splitlines()
            delta_sha = hashlib.sha256(delta).hexdigest()
            if paths and (task_id != SPHINX or sorted(paths) != ["setup.py", "tox.ini"] or delta_sha != SPHINX_DELTA):
                raise ValueError("original setup delta differs from pre-reviewed Sphinx-only correction")
            if (norm.get("original_head") != old_head or (norm.get("original_tree") is not None and norm["original_tree"] != old_tree)
                    or norm.get("original_delta_sha256") != delta_sha or norm.get("original_delta_paths") != paths):
                raise ValueError("source normalization original-head/delta evidence differs")
            original_native, normalized_native = native_manifest(old_git, old_entries), native_manifest(new_git, entries)
            if original_native != normalized_native: raise ValueError("ignored/native product exact bytes changed")
            result["checks"]["retained_ignored_native"] = {"file_count": len(original_native), "bytes": sum(v["bytes"] for v in original_native.values()),
                "manifest_sha256": hashlib.sha256(canonical(original_native)).hexdigest(), "exact_bytes_modes_equal": True}
            result["checks"]["history"] = check_history(normalized, new_git, base_commit)
            result.update(tree=tree, original_head=old_head, original_delta_paths=paths, original_delta_sha256=delta_sha,
                normalized_archive_bytes=Path(normalized_archive).stat().st_size, accepted=True)
    except (ValueError, OSError, KeyError, TypeError, configparser.Error, subprocess.SubprocessError, tarfile.TarError) as error:
        result["error"] = {"type": type(error).__name__, "detail": str(error)[:4096]}
    return result

def main():
    parser = argparse.ArgumentParser()
    for argument in ("task-id", "base-commit", "normalized-archive", "original-archive", "normalization-receipt", "acceptance-receipt", "expected-original-sha256", "output"):
        parser.add_argument("--" + argument, required=True)
    parser.add_argument("--expected-acceptance-sha256")
    args = vars(parser.parse_args()); output = Path(args.pop("output"))
    value = audit_task(**{key.replace("-", "_"): val for key, val in args.items()})
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream: stream.write(canonical(value))
    print(json.dumps({"accepted": value["accepted"], "output": str(output.absolute()), "sha256": digest(output)}))
    raise SystemExit(0 if value["accepted"] else 2)

if __name__ == "__main__": main()
