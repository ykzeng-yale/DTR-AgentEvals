"""DTR-REQ-002 workspace-capture binding v2 (lead 93588ab): replaces the plain `git diff` capture, which omits staged,
new/untracked and committed edits.

Declared rule:
  * at episode start (before the agent's first action) record the IMMUTABLE starting tree
        base = tree of the whole /testbed working tree, written through a PRIVATE temporary git index
               (GIT_INDEX_FILE=<tmp>; `git read-tree HEAD; git add -A; git write-tree`), so the agent's own index,
               branch and history are never touched; .gitignore'd paths are excluded by `git add -A`
  * on an explicit Submitted exit ONLY, record the final tree the same way and submit
        patch = `git diff --binary --full-index <base> <final>`
    which captures modified, staged, added (new/untracked), deleted and committed changes alike; every permitted path
    under /testbed except ignored files is included, new files included (declared)
  * every git step's exit status is checked; any failure makes the capture a CAPTURE FAILURE, retained as its own
    operational outcome (never an empty-but-successful submission, never a salvage)
  * non-Submitted exits submit nothing
Episode outputs use unique immutable run IDs and a no-clobber preflight (see new_run_dir).
"""
from __future__ import annotations
import re
import secrets
import time
from pathlib import Path

WORKDIR = '/testbed'
TREE_CMD = ('cd {wd} && export GIT_INDEX_FILE="$(mktemp)" && rm -f "$GIT_INDEX_FILE" && git read-tree HEAD && '
            'git add -A && git write-tree; rc=$?; rm -f "$GIT_INDEX_FILE"; exit $rc')
SHA = re.compile(r'^[0-9a-f]{40}$')


class CaptureError(RuntimeError):
    pass


def tree(execute, wd=WORKDIR):
    """execute(command) -> (returncode, output). Returns the tree SHA of the whole working tree via a private index."""
    rc, out = execute(TREE_CMD.format(wd=wd))
    sha = (out or '').strip().splitlines()[-1].strip() if (out or '').strip() else ''
    if rc != 0 or not SHA.match(sha):
        raise CaptureError('tree capture failed (rc=%s): %r' % (rc, (out or '')[-300:]))
    return sha


def patch(execute, base, wd=WORKDIR):
    """Final tree + binary diff from the immutable base tree. Returns dict(final_tree, patch)."""
    if not SHA.match(base or ''):
        raise CaptureError('invalid base tree %r' % base)
    final = tree(execute, wd)
    rc, out = execute('cd %s && git diff --binary --full-index %s %s' % (wd, base, final))
    if rc != 0:
        raise CaptureError('diff failed (rc=%s): %r' % (rc, (out or '')[-300:]))
    return dict(final_tree=final, patch=out or '')


def new_run_dir(root, instance_id, backend, binding):
    """Unique immutable run ID and a no-clobber preflight: refuses if the directory exists."""
    run_id = '%s__%s__%s__%s-%s' % (instance_id, backend, binding, time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()), secrets.token_hex(3))
    d = Path(root) / run_id
    d.mkdir(parents=True, exist_ok=False)          # raises FileExistsError instead of overwriting
    return run_id, d


def write_once(path, text):
    """Write a new file; refuses to overwrite an existing one."""
    with open(path, 'x') as fh:
        fh.write(text)
