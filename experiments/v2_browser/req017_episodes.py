"""DTR-REQ-017 episode child: the frozen REQ-016 child (req016_episodes.py, imported and never edited) with exactly two
rebindings: its adapter module is req017_adapter (the one bracket-id change) and its record label is DTR-REQ-017.
Started only by req017_screen.py, in the pinned REQ-015 BrowserGym venv:

    work/venvs/browsergym_9e779f0/bin/python experiments/v2_browser/req017_episodes.py --admission CONFIG
    work/venvs/browsergym_9e779f0/bin/python experiments/v2_browser/req017_episodes.py --run CONFIG
"""
from __future__ import annotations

import contextlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import req016_episodes as EP  # noqa: E402
import req017_adapter as AD17  # noqa: E402

REBINDINGS = dict(AD=AD17, REQUEST=AD17.REQUEST)


@contextlib.contextmanager
def installed():
    """Rebind the REQ-016 child's module globals (read at call time) for one call, then restore them."""
    old = {name: getattr(EP, name) for name in REBINDINGS}
    for name, value in REBINDINGS.items():
        setattr(EP, name, value)
    try:
        yield EP
    finally:
        for name, value in old.items():
            setattr(EP, name, value)


def guard_problems(cfg, root=None, run=None, parent_args=None, getppid=None):
    """A --run that touches the pilot seeds or the pilot model port (module constants, never a mutable file) needs the
    lead release the parent verified (re-checked here) and must be the direct child of a live req017_screen.py."""
    import os
    import urllib.parse
    import req017_screen as R17
    root = root or R17.ROOT
    run = run or R17.S.sh
    port = urllib.parse.urlparse(cfg.get('endpoint') or '').port
    if not (set(cfg.get('seeds') or []) & set(R17.PILOT_SEEDS) or port == R17.PILOT_PORT):
        return []
    problems, _ = R17.release_problems(root, cfg.get('lead_release'), run)
    pid = cfg.get('parent_pid')
    ppid = (getppid or os.getppid)()
    args = parent_args(pid) if parent_args else (run(['ps', '-ww', '-o', 'args=', '-p', str(pid)])[1]
                                                 if isinstance(pid, int) else '')
    tokens = (args or '').split()
    if pid != ppid or len(tokens) < 2 or Path(tokens[1]).name != 'req017_screen.py':
        problems.append('the parent %r is not this process\'s live req017_screen.py parent (getppid %r)' % (pid, ppid))
    return problems


def parse_args(argv):
    """Strict: exactly '--admission PATH' or '--run PATH' (no abbreviations, '=' forms or repeats)."""
    import argparse
    ap = argparse.ArgumentParser(prog='req017_episodes.py', allow_abbrev=False)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--admission', metavar='CONFIG')
    g.add_argument('--run', metavar='CONFIG')
    if len(argv) != 2 or argv[0] not in ('--admission', '--run'):
        ap.error('usage: --admission CONFIG | --run CONFIG')
    return ap.parse_args(argv)


def main(argv=None):
    import json
    ns = parse_args(list(sys.argv[1:] if argv is None else argv))
    if ns.run:
        raw = Path(ns.run).read_bytes()                # read once: the guarded bytes are the bytes that run
        problems = guard_problems(json.loads(raw))
        if problems:
            print('DTR-REQ-017 child refused (no model call): %s' % '; '.join(problems), file=sys.stderr)
            return 3
        frozen = Path(ns.run).with_name(Path(ns.run).name + '.guarded')
        with open(frozen, 'xb') as fh:
            fh.write(raw)
        with installed():
            return EP.main(['--run', str(frozen)])
    with installed():
        return EP.main(['--admission', ns.admission])


if __name__ == '__main__':
    sys.exit(main())
