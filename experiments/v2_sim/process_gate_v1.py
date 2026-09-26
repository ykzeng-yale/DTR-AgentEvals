"""DTR-REQ-023 (lead 4bbf7e0, docs/theory_feedback_20260926_req022_decision.md): a reusable non-overlap process gate,
version 1, replacing the name scan in the frozen REQ-022 launcher (experiments/v2_sim/null_control_batch.py at bc4a71e,
left unchanged).

The REQ-022 gate had two defects. It matched its own launch wrapper, because it excluded only its own PID and not the
ancestor shell whose command line named the script. It also could not see a peer of the same module started as
`python -c "import null_control_batch ..."`, because it searched only for the file name.

This gate:
  - reads the process table with two ps calls, each keeping its variable-width column last so nothing is truncated:
    (pid, ppid, args) and (pid, comm). Tests inject the raw ps text or the parsed table, so no process is started.
  - identifies the current process and its ancestor chain up to pid 1, and excludes only that chain (the owned launch
    wrappers) and the current process's own descendants (e.g. its worker pool).
  - reports as a SAME-MODULE PEER any other INTERPRETER process (python, pypy, ipython and suffixed builds such as
    python3.13t or python3.12-intel64; uv, pipx, conda-style runners) whose command line references the guarded
    module, case-insensitively, as `<module>.py`, as an import, as `-m <module>` or `-m<module>`, or as a bare token.
    The executable name is taken from comm without splitting, so an interpreter under a path with spaces is seen.
    A python that reads its program from stdin or starts a REPL (`python -`, `python /dev/stdin`, a heredoc) is a
    peer when any ancestor's command line references the module. bash keeps a `-c` heredoc's text in its own
    arguments, including when two copies share one wrapper. Non-interpreter processes are not flagged for the module
    name, so an editor holding the file or `tee <module>.log` is not a peer. ps octal escapes such as `\\012`
    (newline) are read as spaces.
  - reports as a PEER any other process, interpreter or not, matching the extra patterns: stage runners with `--stage`
    anywhere after `run.py`, any command line containing `dev_batch` or `coverage_batch` (suffixed successors
    included), and model servers.
  - refuses conservatively (passed = False, reason 'unknown process identity') when the table cannot be read, the
    current process is missing from it, its ancestor chain is broken or cyclic, or a process outside the owned chain
    has a hidden command line (ps shows it as '(name)' or empty) and a name that could be an interpreter or a model
    server.

Conservative false positives (the gate blocks; the operator inspects and retries): a concurrent read-only
`process_gate('<module>')` check by another process; a monitor such as `pgrep -f llama-server` or `tail` of a server
log; any foreign process whose arguments name a model server (for example another project's `--llama-bin` path); an
editor, `tail` or test run whose arguments contain `dev_batch` or `coverage_batch`; and an unrelated stdin python
under a wrapper whose text names the module.

Limits: a command-line gate cannot see a peer whose module name is built at run time (string pieces, environment
variables), a copied or symlinked script under another name, code imported indirectly (for example by a test run),
code typed into an interactive shell or REPL whose command lines never name the module, a heredoc launched by
`zsh -c` / `zsh -lc` (zsh 5.9 execs its last command, so the heredoc text is in no process's arguments), or a process
whose argv[0] was renamed (`exec -a`, setproctitle; on macOS comm follows argv[0]). Such peers need an ownership
lease, not a process scan.

It never kills, signals or starts a process.

    from process_gate_v1 import process_gate
    process_gate('null_control_batch')        # live table from ps; a dict with passed / peers / refusals
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
from collections import OrderedDict
from pathlib import Path

VERSION = 'process_gate_v1'
DEFAULT_EXTRA_PEERS = (r'\brun\.py\b.*\s--stage\b', r'dev_batch', r'coverage_batch',
                       r'\bllama-server\b', r'\bmlx_lm\b', r'\bollama\b', r'\bvllm\b')
PY_NAME = r'(python|pythonw|pypy|ipython)[0-9.]*[dmtu]{0,2}(-[a-z0-9_]+)?'   # python3.13t, python3.12-intel64
PY_LIKE = re.compile(r'^%s$' % PY_NAME, re.I)
INTERPRETER = re.compile(r'^(%s|uv|uvx|pipx|conda|mamba|micromamba|pdm|poetry|hatch|nox|tox|python\.app)$' % PY_NAME,
                         re.I)
# names that could hide a peer when a command line is unreadable (prefix match: ps may shorten names; the short
# runner names must match whole, so macOS daemons such as UVFSService are not suspects)
SUSPECT_NAME = re.compile(r'^(python|pypy|ipython|llama|ollama|vllm|mlx|node)|^(uv|uvx|pipx|conda|mamba|micromamba)$',
                          re.I)
OCTAL_ESCAPE = re.compile(r'\\[0-7]{3}')


def source_sha256():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def parse_ps(args_text, comm_text):
    """[(pid, ppid, comm, args)] from `ps -o pid=,ppid=,args=` and `ps -o pid=,comm=` text."""
    comm = {}
    for line in comm_text.splitlines():
        f = line.strip().split(None, 1)
        if f and f[0].isdigit():
            comm[int(f[0])] = f[1].strip() if len(f) > 1 else ''
    rows = []
    for line in args_text.splitlines():
        f = line.strip().split(None, 2)
        if len(f) < 2 or not f[0].isdigit() or not f[1].isdigit():
            continue
        pid = int(f[0])
        rows.append((pid, int(f[1]), comm.get(pid, ''), f[2] if len(f) > 2 else ''))
    return rows


def read_process_table(run=subprocess.run):
    """the live table, or None if either ps call fails."""
    out = []
    for cols in ('pid=,ppid=,args=', 'pid=,comm='):
        try:
            p = run(['ps', '-axww', '-o', cols], capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if p.returncode != 0:
            return None
        out.append(p.stdout)
    return parse_ps(out[0], out[1])


def module_pattern(module):
    m = re.escape(module)
    return re.compile(r'((?<![A-Za-z0-9_])%s\.py(?![A-Za-z0-9_])|\bimport\s+%s(?![A-Za-z0-9_])|'
                      r'\bfrom\s+%s(?![A-Za-z0-9_])|-m\s*%s(?![A-Za-z0-9_])|(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_]))'
                      % (m, m, m, m, m), re.I)


def normalized(args):
    """ps shows control characters as octal escapes (a heredoc newline is `\\012`); read them as spaces."""
    return OCTAL_ESCAPE.sub(' ', args)


def unreadable(args):
    a = args.strip()
    return not a or (a.startswith('(') and a.endswith(')'))


def bare_name(text):
    t = text.strip().strip('()').strip()
    return Path(t.split()[0]).name if t else ''


def exe_name(comm):
    """the executable name from comm, which keeps spaces (it is the last column of its own ps call)."""
    c = comm.strip().strip('()').strip()
    return Path(c).name if c else ''


def is_interpreter(comm, args):
    return bool(INTERPRETER.match(exe_name(comm)) or INTERPRETER.match(bare_name(args)))


STDIN_PATHS = ('-', '/dev/stdin', '/dev/fd/0')


def reads_stdin(comm, args):
    """a python-like interpreter with no script, -c or -m, or with a stdin path as its script: it reads stdin (`-`,
    `/dev/stdin`, a heredoc) or starts a REPL."""
    if not (PY_LIKE.match(exe_name(comm)) or PY_LIKE.match(bare_name(args))):
        return False
    a, c = normalized(args).strip(), comm.strip()
    rest = a[len(c):] if c and a.startswith(c) else ' '.join(a.split()[1:])   # drop argv[0], which may hold spaces
    toks = rest.split()
    i = 0
    while i < len(toks):
        t = toks[i]
        if t in STDIN_PATHS:
            return True
        if t == '--':
            return i + 1 >= len(toks) or toks[i + 1] in STDIN_PATHS
        if not t.startswith('-'):
            return False                                  # a script path
        if t.startswith('--'):
            i += 2 if t == '--check-hash-based-pycs' else 1
            continue
        step = 1
        for j, ch in enumerate(t[1:], 1):                 # a short-option cluster such as -uBc or -uX dev
            if ch in 'cm':
                return False                              # -c code or -m module
            if ch in 'XW':
                step = 1 if j + 1 < len(t) else 2         # the value is attached or the next argument
                break
        i += step
    return True


def launch_ancestors(pid, table):
    """all ancestors of pid up to pid 1, stopping at a missing parent or a cycle."""
    parent = {p: pp for p, pp, _, _ in table}
    out, cur = [], parent.get(pid)
    while cur is not None and cur not in (0, 1) and cur not in out and cur != pid:
        out.append(cur)
        cur = parent.get(cur)
    return out


def ancestors(pid, table):
    """ordered ancestor pids of pid (excluding pid), or None if the chain breaks or cycles before pid 1 / 0."""
    parent = {p: pp for p, pp, _, _ in table}
    chain, cur, seen = [], pid, {pid}
    while True:
        pp = parent.get(cur)
        if pp is None:
            return None
        if pp == 0:
            return chain
        if pp == 1:
            chain.append(1)
            return chain
        if pp in seen:
            return None
        seen.add(pp)
        chain.append(pp)
        cur = pp


def descendants(pid, table):
    kids = {}
    for p, pp, _, _ in table:
        kids.setdefault(pp, []).append(p)
    out, stack = set(), [pid]
    while stack:
        for c in kids.get(stack.pop(), []):
            if c not in out:
                out.add(c)
                stack.append(c)
    return out


def evaluate(table, self_pid, module, extra_peer_patterns=DEFAULT_EXTRA_PEERS):
    """pure decision on an (injected) process table."""
    res = OrderedDict(version=VERSION, module=module, self_pid=self_pid, peers=[], refusals=[], owned=[])
    if table is None:
        res['refusals'].append('unknown process identity: process table unreadable')
    elif self_pid not in {p for p, _, _, _ in table}:
        res['refusals'].append('unknown process identity: current process %d not in the table' % self_pid)
    else:
        chain = ancestors(self_pid, table)
        if chain is None:
            res['refusals'].append('unknown process identity: ancestor chain of %d is broken' % self_pid)
        else:
            owned = {self_pid} | set(chain) | descendants(self_pid, table)
            res['owned'] = sorted(owned)
            mod = module_pattern(module)
            extra = [re.compile(x) for x in extra_peer_patterns]
            args_of = {p: normalized(a) for p, _, _, a in table}
            for p, pp, comm, args in table:
                if p in owned:
                    continue
                name = exe_name(comm) or bare_name(args)
                if unreadable(args):
                    if SUSPECT_NAME.match(name):
                        res['refusals'].append('unknown process identity: pid %d (%s) has no readable command line'
                                               % (p, name))
                    continue
                a = args_of[p]
                if is_interpreter(comm, args) and mod.search(a):
                    res['peers'].append(OrderedDict(pid=p, reason='same module', command=name))
                elif is_interpreter(comm, args) and reads_stdin(comm, args) and any(
                        mod.search(args_of.get(q, '')) for q in launch_ancestors(p, table)):
                    res['peers'].append(OrderedDict(pid=p, reason='same module (stdin; named by a launching '
                                                                   'process)', command=name))
                elif any(x.search(a) for x in extra):
                    res['peers'].append(OrderedDict(pid=p, reason='peer pattern', command=name))
    res['passed'] = not res['peers'] and not res['refusals']
    return res


def process_gate(module, self_pid=None, table=None, extra_peer_patterns=DEFAULT_EXTRA_PEERS):
    """live gate: reads ps unless a table is injected; the result records the gate version and source hash."""
    t = read_process_table() if table is None else table
    res = evaluate(t, os.getpid() if self_pid is None else self_pid, module, extra_peer_patterns)
    res['source_sha256'] = source_sha256()
    return res
