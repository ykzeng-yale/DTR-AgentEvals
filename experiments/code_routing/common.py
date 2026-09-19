"""Paths, hashing, config and task loading for the code-routing experiment."""
from __future__ import annotations
import glob, hashlib, json, os, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
RESULTS = ROOT / 'results' / 'code_routing'
sys.path.insert(0, str(HERE.parent / 'common'))
sys.path.insert(0, str(HERE.parent / 'dtr'))


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def load_config() -> dict:
    cfg = json.loads((HERE / 'config.json').read_text())
    cfg['_config_sha256'] = sha256_bytes((HERE / 'config.json').read_bytes())
    return cfg


def resolve(path_glob: str) -> str:
    hits = sorted(glob.glob(os.path.expanduser(path_glob)))
    if not hits:
        raise FileNotFoundError(path_glob)
    return hits[0]


def load_tasks(cfg: dict) -> list:
    tp = cfg['tasks_path']
    raw = Path(resolve(tp if tp.startswith(('/', '~')) else str(ROOT / tp))).read_bytes()
    got = sha256_bytes(raw)
    tasks = json.loads(raw)
    for t in tasks:
        t['_tasks_sha256'] = got
    return tasks


def git_head() -> str:
    """Commit id read from .git files (no git subprocess)."""
    try:
        head = (ROOT / '.git' / 'HEAD').read_text().strip()
        if head.startswith('ref: '):
            ref = ROOT / '.git' / head[5:]
            return ref.read_text().strip() if ref.exists() else 'unborn'
        return head
    except OSError:
        return 'unknown'


def now_iso() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def code_sha256() -> str:
    files = sorted(HERE.glob('*.py')) + sorted((HERE.parent / 'common').glob('*.py'))
    return sha256_bytes(b''.join(f.read_bytes() for f in files))


def read_jsonl(path) -> tuple:
    """(records, n_torn). Only a FINAL unparsable line is tolerated (a torn append); the runner cuts such a fragment
    off into a sidecar before appending, so an unparsable line can never legitimately be non-final."""
    path = Path(path)
    if not path.exists():
        return [], 0
    lines = [l for l in path.read_text().splitlines() if l.strip()]
    out = []
    for i, l in enumerate(lines):
        try:
            out.append(json.loads(l))
        except ValueError:
            if i == len(lines) - 1:
                return out, 1
            raise SystemExit('%s: unparsable line %d that is not the last line - refusing to guess' % (path, i + 1))
    return out, 0


def cut_torn_tail(path, invocation: str) -> int:
    """If the file does not end in a complete JSON line, move the fragment to <name>.torn.<invocation> and truncate.
    Returns the number of bytes removed."""
    path = Path(path)
    if not path.exists():
        return 0
    raw = path.read_bytes()
    if not raw:
        return 0
    body = raw.rstrip(b'\r\n'); cut = body.rfind(b'\n') + 1; last = body[cut:]
    try:
        json.loads(last.decode('utf-8', errors='strict')); ok = True
    except ValueError:
        ok = False
    if ok:
        if not raw.endswith(b'\n'):
            with open(path, 'ab') as f:
                f.write(b'\n')
        return 0
    path.with_name(path.name + '.torn.' + invocation).write_bytes(raw[cut:])
    with open(path, 'r+b') as f:
        f.truncate(cut); f.flush(); os.fsync(f.fileno())
    return len(raw) - cut


def resolve_episodes(path, max_attempts: int) -> dict:
    """good: last record without an infrastructure error, per episode id. exhausted: ids whose max_attempts attempts all
    errored (scored intention-to-treat by analysis). pending: ids with only error records and attempts left - NOT done,
    NOT analysable. n_err: error attempts per id."""
    recs, torn = read_jsonl(path)
    good, last_bad, n_err = {}, {}, {}
    for r in recs:
        if r.get('error'):
            n_err[r['episode_id']] = n_err.get(r['episode_id'], 0) + 1; last_bad[r['episode_id']] = r
        else:
            good[r['episode_id']] = r
    exhausted = {e: last_bad[e] for e, k in n_err.items() if k >= max_attempts and e not in good}
    pending = sorted(e for e, k in n_err.items() if k < max_attempts and e not in good)
    return dict(good=good, exhausted=exhausted, pending=pending, n_err=n_err, torn=torn, n_records=len(recs))
