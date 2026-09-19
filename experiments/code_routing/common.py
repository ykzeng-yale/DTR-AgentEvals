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
