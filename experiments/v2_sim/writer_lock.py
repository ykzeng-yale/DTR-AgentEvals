"""Writer lock and git guard (lead f0b4fa2: fix the recurrent stash/write-loss defect before the next run).

Batch runners write ONLY under the git-ignored work/ tree (git stash -u and pull/rebase leave ignored files alone), hold
an exclusive lock file under work/locks/ while writing, and publish into results/ only by an atomic finalize after the
writers have closed. Before any git working-tree operation, run `python writer_lock.py guard`: it exits non-zero while
any lock is held.
"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCKS = ROOT / 'work' / 'locks'


class LockHeld(RuntimeError):
    pass


class WriterLock:
    def __init__(self, name):
        self.path = LOCKS / (name + '.lock')

    def __enter__(self):
        LOCKS.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise LockHeld('writer lock already held: %s' % self.path)
        with os.fdopen(fd, 'w') as fh:
            json.dump(dict(pid=os.getpid(), started=time.time()), fh)
        return self

    def __exit__(self, *exc):
        self.path.unlink(missing_ok=True)
        return False


def held():
    return sorted(p.name for p in LOCKS.glob('*.lock')) if LOCKS.exists() else []


def finalize(part_path, final_path, expected_ids, key):
    """Atomically publish a CLOSED part file: parse every line, require exactly the expected unique ids, then os.replace."""
    recs = [json.loads(x) for x in Path(part_path).read_text().splitlines()]
    ids = [key(r) for r in recs]
    dup = len(ids) - len(set(ids))
    missing, extra = set(expected_ids) - set(ids), set(ids) - set(expected_ids)
    if dup or extra:
        raise ValueError('refusing to finalize: %d duplicate and %d unexpected ids' % (dup, len(extra)))
    Path(final_path).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(final_path) + '.tmp')
    tmp.write_text(''.join(json.dumps(r) + '\n' for r in sorted(recs, key=key)))
    os.replace(tmp, final_path)
    return dict(records=len(recs), unique=len(set(ids)), missing=len(missing), expected=len(expected_ids))


if __name__ == '__main__' and sys.argv[1:] == ['guard']:
    h = held()
    if h:
        print('WRITER ACTIVE, do not stash/pull/rebase:', h)
        sys.exit(1)
    print('no writer lock held')
