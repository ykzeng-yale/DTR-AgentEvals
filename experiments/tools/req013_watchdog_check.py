"""DTR-REQ-013 step 1b (lead 702e58a, docs/theory_feedback_20260924_req012_decision.md): the current-host watchdog
command-identity / SIGKILL check. There is no model and no server; the "server" is a sleeping Python stub.

    .venv/bin/python experiments/tools/req013_watchdog_check.py

This reproduces tests/test_req011_pair.py::test_the_server_watchdog_stops_the_recorded_server_after_the_parent_is_sigkilled
with that fixture's own stub parent (STUB_PARENT and SLEEPER, imported, not restated). The stub parent does three
things. It starts a stub server and a decoy, each in its own session. It records both under the DTR-REQ-011 holder in a
private ownership record, never work/code_routing_servers.json. It then starts the unedited req011_pair watchdog.

While the parent lives, the check records for every recorded server the stored command and the live
`ps -ww -o args=` of its PID. It also records whether the two compare equal, both as raw strings and under the
watchdog's own rule (req011_pair.is_recorded_server, which removes the root prefix). It then SIGKILLs the parent. It
records whether the watchdog stopped the owned stub within its grace, left the decoy untouched and exited. Finally it
runs the fixture itself under pytest and records the outcome.

The result goes to results/v2_agent/req013_14b_discriminator_20260924/watchdog_host_check.json (write-once,
sanitized), whatever the outcome. The raw stub files stay under work/runs/req013_14b_discriminator_20260924/. Exit 0
only if the owned stub was stopped within its grace, the decoy was untouched, the watchdog exited and the fixture
passed; otherwise exit 2.
"""
from __future__ import annotations

import json
import os
import platform
import signal
import subprocess
import sys
import time
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / 'experiments/v2_agent', ROOT / 'tests'):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import req011_pair as P11  # noqa: E402  the unedited REQ-011 runner (watchdog, is_recorded_server, live_args)
import test_req011_pair as T11  # noqa: E402  the fixture's own STUB_PARENT, SLEEPER, alive and wait_until

S = P11.S
REQUEST = 'DTR-REQ-013'
OUT = 'results/v2_agent/req013_14b_discriminator_20260924/watchdog_host_check.json'
RAW = 'work/runs/req013_14b_discriminator_20260924/watchdog_check'
FIXTURE = ('tests/test_req011_pair.py::'
           'test_the_server_watchdog_stops_the_recorded_server_after_the_parent_is_sigkilled')
STOP_SLACK_S = 5          # detection and process-table latency allowed on top of the watchdog's poll and grace


def digest(path):
    return S.sha_file(path) if Path(path).is_file() else None


def interpreter():
    exe = Path(sys.executable)
    return OrderedDict(executable=str(exe), is_symlink=exe.is_symlink(), realpath=os.path.realpath(exe),
                       version=sys.version.split()[0], implementation=platform.python_implementation(),
                       platform=platform.platform(), machine=platform.machine())


def compare(server, base, run=S.sh):
    """The stored command against the live `ps -ww -o args=` of its PID, raw and under the watchdog rule."""
    live = P11.live_args(server['pid'], run) if type(server.get('pid')) is int else None
    stripped = None if live is None else live.replace(str(base) + '/', '')
    return OrderedDict(role=server.get('role'), pid=server.get('pid'), port=server.get('port'),
                       recorded_command=server.get('cmd'), live_args=live, live_args_root_prefix_removed=stripped,
                       equal_raw=live == server.get('cmd'), equal_after_root_prefix_removal=stripped == server.get('cmd'),
                       watchdog_rule_match=P11.is_recorded_server(server, base, run))


def scenario(base, python=sys.executable, clock=time.monotonic):
    """The fixture scenario with measurements; every started process is killed at the end."""
    script = base / 'stub_parent.py'
    script.write_text(T11.STUB_PARENT % dict(module_dir=str(ROOT / 'experiments/v2_agent'), sleeper=T11.SLEEPER))
    parent = subprocess.Popen([str(python), str(script), str(base)], start_new_session=True)
    pids, out = {}, OrderedDict(stub_parent_pid=parent.pid)
    try:
        out['pids_written'] = T11.wait_until(lambda: (base / 'pids.json').exists(), 60)
        if not out['pids_written']:
            return out
        pids = json.loads((base / 'pids.json').read_text())
        cfg = json.loads((base / 'raw' / 'watchdog_config.json').read_text())
        out.update(pids=pids, watchdog_ready=pids.get('ready') is True, holder=cfg['holder'], poll_s=cfg['poll_s'],
                   grace_s=cfg['grace_s'], stop_bound_s=cfg['poll_s'] + cfg['grace_s'] + STOP_SLACK_S)
        record = json.loads((base / 'servers.json').read_text())
        out['recorded_servers'] = [compare(s, base) for s in record['servers']]      # while the parent lives
        time.sleep(1.0)
        out['server_alive_while_parent_lives'] = T11.alive(pids['server'])
        os.kill(parent.pid, signal.SIGKILL)                                         # no handler, no finally
        parent.wait(timeout=10)
        t0 = clock()
        stopped = T11.wait_until(lambda: not T11.alive(pids['server']), 30)
        out['seconds_from_parent_sigkill_to_stub_stop'] = round(clock() - t0, 2) if stopped else None
        out['owned_stub_stopped'] = stopped
        out['watchdog_exited'] = T11.wait_until(lambda: not T11.alive(pids['watchdog']), 30)
        out['decoy_untouched'] = T11.alive(pids['decoy'])
        action = P11.load_json(base / 'raw' / 'watchdog_action.json')
        out['watchdog_action'] = action
        owned = next((r for r in (action or {}).get('servers') or [] if r.get('pid') == pids['server']), {})
        out['stopped_within_grace'] = bool(
            stopped and out['seconds_from_parent_sigkill_to_stub_stop'] <= out['stop_bound_s']
            and owned.get('matched') is True and owned.get('signals') == ['SIGTERM']
            and owned.get('recorded_command_still_running') is False)
        return out
    finally:
        for pid in [parent.pid] + [pids[k] for k in ('server', 'decoy', 'watchdog') if k in pids]:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def run_fixture(base, root=ROOT, run=S.sh, python=sys.executable):
    """The existing fixture under pytest; its full output stays in the raw directory (it may hold pytest temp paths)."""
    cmd = [str(python), '-m', 'pytest', '-q', '-p', 'no:cacheprovider', FIXTURE]
    env = dict(S.scrub_env(dict(os.environ))[0], PYTHONPATH=str(root / 'src'))
    rc, out, err = run(cmd, env=env, timeout=300)
    text = (out or '') + (err or '')
    with open(base / 'fixture_output.txt', 'x') as fh:
        fh.write(text)
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    return OrderedDict(nodeid=FIXTURE, command=['<python>'] + cmd[1:], returncode=rc,
                       summary=lines[-1] if lines else None,
                       passed=rc == 0 and bool(lines) and ' passed' in lines[-1] and 'failed' not in lines[-1],
                       output=str((base / 'fixture_output.txt').relative_to(root)),
                       output_sha256=S.sha_bytes(text.encode()))


def main(argv=None, root=ROOT, run_scenario=scenario, fixture=run_fixture, clock=time.time):
    root = Path(root)
    out = root / OUT
    if out.exists():
        print('%s already exists (write-once)' % OUT, file=sys.stderr)
        return 3
    base = root / RAW / ('%s-%d' % (time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(clock())), os.getpid()))
    base.mkdir(parents=True, exist_ok=False)
    started = clock()
    s = run_scenario(base)
    f = fixture(base)
    rows = s.get('recorded_servers') or []
    owned = next((r for r in rows if r['pid'] == (s.get('pids') or {}).get('server')), {})
    passed = bool(s.get('watchdog_ready') and owned.get('watchdog_rule_match') and s.get('server_alive_while_parent_lives')
                  and s.get('stopped_within_grace') and s.get('decoy_untouched') and s.get('watchdog_exited')
                  and f['passed'])
    record = OrderedDict(
        request=REQUEST, kind='DTR-REQ-013 step 1b: current-host watchdog command-identity / SIGKILL check (no model, '
                              'no server; a sleeping Python stub is the recorded server)',
        lead_decision='docs/theory_feedback_20260924_req012_decision.md', started_utc=S.utc(started),
        finished_utc=S.utc(clock()), host=OrderedDict(interpreter=interpreter(), ps='ps -ww -o args= -p <pid>'),
        scenario_source=OrderedDict(fixture=FIXTURE, stub_parent='tests/test_req011_pair.py STUB_PARENT and SLEEPER',
                                    fixture_file_sha256=digest(Path(root) / 'tests/test_req011_pair.py'),
                                    watchdog_source_sha256=digest(Path(root) / 'experiments/v2_agent/req011_pair.py')),
        raw_dir=str(base.relative_to(root)), recorded_servers=rows,
        owned_stub=OrderedDict(recorded_vs_live_equal_raw=owned.get('equal_raw'),
                               recorded_vs_live_equal_under_the_watchdog_rule=owned.get('watchdog_rule_match'),
                               stopped=s.get('owned_stub_stopped'),
                               seconds_from_parent_sigkill_to_stop=s.get('seconds_from_parent_sigkill_to_stub_stop'),
                               stop_bound_s=s.get('stop_bound_s'), stopped_within_grace=s.get('stopped_within_grace')),
        decoy_untouched=s.get('decoy_untouched'), watchdog_exited=s.get('watchdog_exited'),
        scenario={k: v for k, v in s.items() if k != 'recorded_servers'}, fixture=f, passed=passed,
        rule='passed = the watchdog was ready; the owned stub matched its record under the watchdog rule while the '
             'parent lived and stayed alive until the parent was SIGKILLed; the watchdog then stopped it with SIGTERM '
             'within poll_s + grace_s + %d s; the decoy (recorded PID, other command) was untouched; the watchdog '
             'exited; and the existing fixture passed' % STOP_SLACK_S)
    out.parent.mkdir(parents=True, exist_ok=True)
    S.write_json_x(out, record)
    if S.username_hits(out.parent):
        print('username found under %s: do not publish until redacted' % out.parent, file=sys.stderr)
        return 2
    print(json.dumps(S.sanitize(OrderedDict(passed=passed, record=OUT, owned_stub=record['owned_stub'],
                                            fixture=OrderedDict((k, f[k]) for k in ('returncode', 'summary'))))))
    return 0 if passed else 2


if __name__ == '__main__':
    sys.exit(main())
