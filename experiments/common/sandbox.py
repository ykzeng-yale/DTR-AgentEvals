# Adapted from ykzeng-yale/ICLR-WinRatioAgentEval experiments/local_stream/sandbox.py
# (same author; audited Seatbelt sandbox + sentinel verifier). Changes: sandbox
# base dir renamed to dtr_sbx; sentinel prefix renamed; per-run read isolation inside the
# shared base dir (a run may read and write only its own temp dir).
"""Restricted execution of candidate programs.

Guards (binding):
  * macOS Seatbelt (`/usr/bin/sandbox-exec -p <profile>`): no network; no
    file reads under $HOME except the interpreter prefix; no file writes
    anywhere under $HOME or in the shared temp directories except the
    program's own temp cwd (and /dev/null); no process-exec of system
    binaries (/bin, /usr/bin, /usr/local/bin, /opt, /sbin, /usr/sbin). The
    profile text is derived from Path.home(), the interpreter prefix and the
    temp directory; its sha256 is returned with every run and recorded in
    the manifest. The base interpreter of the venv (pyvenv.cfg `home`) is
    used, never the venv symlink, so the repository path is not exposed.
  * process group: `start_new_session=True`; on wall-clock timeout the
    whole group is killed with SIGKILL (no orphans).
  * rlimits in the child: RLIMIT_CPU, RLIMIT_NPROC (64; on macOS this is the
    per-uid count, so any fork from the sandbox fails with EAGAIN) and a
    best-effort RLIMIT_AS/RLIMIT_DATA (macOS rejects it; the applied limits
    are recorded).
  * PATH-only environment, stdin closed, stdout/stderr capped.
The static regex list below is NOT a guard any more: every program is
executed; matches are returned as ``flags`` and recorded per episode
(`sandbox_flag`) for post-hoc review only. They do not affect success.
Outside macOS the Seatbelt layer is absent (recorded as sandbox_kind='none').
"""
from __future__ import annotations
import hashlib, os, re, resource, shutil, signal, subprocess, sys, tempfile, time
from pathlib import Path

# heuristic flags (recorded, never blocking)
STATIC_FLAG_RULES = [
    ('os.system', re.compile(r'\bos\s*\.\s*(system|popen|exec[lv]p?e?|spawn\w*|fork|kill|killpg)\s*\(')),
    ('subprocess', re.compile(r'\bsubprocess\b')),
    ('shutil.rmtree', re.compile(r'\bshutil\s*\.\s*(rmtree|move|copytree)\s*\(')),
    ('socket', re.compile(r'\b_?socket\b')),
    ('urllib', re.compile(r'\burllib\b')),
    ('requests', re.compile(r'\brequests\b')),
    ('http.client', re.compile(r'\bhttp\s*\.\s*(client|server)\b')),
    ('ctypes', re.compile(r'\bctypes\b')),
    ('multiprocessing', re.compile(r'\bmultiprocessing\b')),
    ('sys.exit', re.compile(r'\b(?:sys\s*\.\s*)?exit\s*\(|\bSystemExit\b|\bos\s*\.\s*_exit\s*\(')),
    ('os.remove', re.compile(r'\bos\s*\.\s*(remove|unlink|rmdir|removedirs)\s*\(')),
    ('pathlib.unlink', re.compile(r'\.\s*(unlink|rmdir)\s*\(')),
    ('dynamic_import', re.compile(r'\b(__import__|importlib)\b')),
    ('open_abs_path', re.compile(r'\bopen\s*\(\s*[rRfFbB]?[\'"](?:/|~|\.\./)')),
    ('sys.executable', re.compile(r'\bsys\s*\.\s*(executable|modules|_getframe)\b|\b__file__\b')),
]
BLOCKLIST = STATIC_FLAG_RULES  # backwards-compatible name; nothing is blocked
EXEC_DENY_DIRS = ('/bin', '/usr/bin', '/usr/local/bin', '/opt', '/sbin', '/usr/sbin')
NPROC_LIMIT = 64


def static_check(source: str) -> list:
    """Names of every heuristic rule matched by the source text (recorded only)."""
    return [name for name, rx in STATIC_FLAG_RULES if rx.search(source)]


def base_interpreter() -> str:
    """Base interpreter of the running venv from pyvenv.cfg `home` (realpath), never the venv symlink."""
    cfg = Path(sys.prefix) / 'pyvenv.cfg'
    if cfg.exists():
        for line in cfg.read_text().splitlines():
            k, _, v = line.partition('=')
            if k.strip() == 'home':
                home = Path(v.strip())
                for name in ('python%d.%d' % sys.version_info[:2], 'python3', 'python'):
                    cand = home / name
                    if cand.exists():
                        return os.path.realpath(cand)
    base = getattr(sys, '_base_executable', None) or sys.executable
    return os.path.realpath(base)


def sandbox_base_dir() -> str:
    """Fixed per-host parent of all program cwds (the only writable location in the profile)."""
    d = os.path.join(os.path.realpath(tempfile.gettempdir()), 'dtr_sbx')
    os.makedirs(d, exist_ok=True)
    return d


def seatbelt_profile(python: str, base_dir: str, run_dir: str | None = None) -> str:
    home = os.path.realpath(str(Path.home()))
    prefix = os.path.dirname(os.path.dirname(os.path.realpath(python)))
    tmp_real = os.path.realpath(tempfile.gettempdir())
    write_deny = [tmp_real, '/tmp', '/private/tmp', '/var/tmp', '/private/var/tmp']
    lines = ['(version 1)', '(allow default)', '(deny network*)',
             '(deny file-read* (subpath "%s"))' % home,
             '(allow file-read* (subpath "%s"))' % prefix,
             '(deny file-write* (subpath "%s"))' % home,
             '(deny file-write* %s)' % ' '.join('(subpath "%s")' % p for p in write_deny),
             '(deny file-read* (subpath "%s"))' % base_dir,             # concurrent runs must not read each other's programs
             '(allow file-read* (subpath "%s"))' % (run_dir or base_dir),
             '(allow file-write* (subpath "%s"))' % (run_dir or base_dir),
             '(allow file-write* (literal "/dev/null"))',
             '(deny process-exec %s)' % ' '.join('(subpath "%s")' % p for p in EXEC_DENY_DIRS)]
    return '\n'.join(lines) + '\n'


def sandbox_info(python: str | None = None) -> dict:
    """Describe the sandbox configuration on this host (for the run manifest)."""
    python = python or base_interpreter()
    base = sandbox_base_dir()
    if sys.platform == 'darwin' and os.path.exists('/usr/bin/sandbox-exec'):
        prof = seatbelt_profile(python, base)
        return dict(kind='seatbelt', python=python, base_dir=base, profile=prof, profile_sha256=hashlib.sha256(prof.encode()).hexdigest(),
                    nproc_limit=NPROC_LIMIT, exec_deny_dirs=list(EXEC_DENY_DIRS))
    return dict(kind='none', python=python, base_dir=base, profile=None, profile_sha256=None, nproc_limit=NPROC_LIMIT, exec_deny_dirs=[])


def _make_preexec(mem_bytes: int, cpu_seconds: int, report_path: str):
    def pre():
        applied = []
        for lim_name in ('RLIMIT_AS', 'RLIMIT_DATA'):
            lim = getattr(resource, lim_name, None)
            if lim is None:
                continue
            soft, hard = resource.getrlimit(lim)
            want = mem_bytes if hard == resource.RLIM_INFINITY else min(mem_bytes, hard)
            try:
                resource.setrlimit(lim, (want, hard))
                applied.append('%s=%d' % (lim_name, want))
            except (ValueError, OSError):
                pass
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
            applied.append('RLIMIT_CPU=%d' % cpu_seconds)
        except (ValueError, OSError):
            pass
        try:
            soft, hard = resource.getrlimit(resource.RLIMIT_NPROC)
            want = NPROC_LIMIT if hard == resource.RLIM_INFINITY else min(NPROC_LIMIT, hard)
            resource.setrlimit(resource.RLIMIT_NPROC, (want, hard))
            applied.append('RLIMIT_NPROC=%d' % want)
        except (ValueError, OSError, AttributeError):
            pass
        try:
            with open(report_path, 'w') as f:
                f.write(','.join(applied))
        except OSError:
            pass
    return pre


def run_program(source: str, timeout_s: float = 10.0, mem_bytes: int = 2 << 30, cpu_seconds: int = 10,
                output_cap: int = 65536, python: str | None = None) -> dict:
    """Execute ``source`` under the restrictions above.

    Returns dict(passed, returncode, stdout, stderr, stdout_tail, timed_out, seconds,
    executed, flags, limits_applied, sandbox_kind, profile_sha256). ``passed`` is
    True iff the program exited with code 0 and did not time out. ``flags`` are
    the heuristic matches (recorded only). ``stdout_tail`` is the last 512 bytes
    of the raw stdout (not subject to the cap) for sentinel checks.
    """
    flags = static_check(source)
    info = sandbox_info(python)
    python = info['python']
    tmp = tempfile.mkdtemp(prefix='p_', dir=info['base_dir'])
    prog = os.path.join(tmp, 'prog.py')
    report = os.path.join(tmp, '.limits')
    with open(prog, 'w', encoding='utf-8') as f:
        f.write(source)
    env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'PYTHONIOENCODING': 'utf-8'}
    cmd = [python, '-I', '-S', prog]
    if info['kind'] == 'seatbelt':
        cmd = ['/usr/bin/sandbox-exec', '-p', seatbelt_profile(python, info['base_dir'], tmp)] + cmd   # profile_sha256 stays that of the template
    t0 = time.perf_counter()
    timed_out = False
    proc = subprocess.Popen(cmd, cwd=tmp, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True, preexec_fn=_make_preexec(mem_bytes, cpu_seconds, report))
    try:
        out, err = proc.communicate(timeout=timeout_s)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            out, err = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:  # pragma: no cover
            proc.kill(); out, err = proc.communicate()
        rc = None
        err = (err or b'') + b'\n[wall-clock timeout after %.1fs; process group killed]' % timeout_s
    seconds = time.perf_counter() - t0
    limits = ''
    try:
        if os.path.exists(report):
            with open(report) as f:
                limits = f.read()
    except OSError:
        pass
    shutil.rmtree(tmp, ignore_errors=True)
    out = out or b''; err = err or b''

    def cap(b: bytes) -> str:
        s = b[:output_cap].decode('utf-8', errors='replace')
        return s + ('\n[output truncated at %d bytes]' % output_cap if len(b) > output_cap else '')
    return dict(passed=(rc == 0 and not timed_out), returncode=rc, stdout=cap(out), stderr=cap(err),
                stdout_tail=out[-512:].decode('utf-8', errors='replace'), timed_out=timed_out, seconds=seconds, executed=True,
                flags=flags, limits_applied=limits, sandbox_kind=info['kind'], profile_sha256=info['profile_sha256'])
