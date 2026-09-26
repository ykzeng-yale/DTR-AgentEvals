"""DTR-REQ-023 deterministic fixtures for the non-overlap process gate (experiments/v2_sim/process_gate_v1.py). Every
case uses an injected process table (pid, ppid, comm, args); no process, model, peer job or simulation is started."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments/v2_sim'))
import process_gate_v1 as P  # noqa: E402

MOD = 'null_control_batch'
PY = '/Users/u/repo/.venv/bin/python'
BASE = [(1, 0, '/sbin/launchd', '/sbin/launchd'),
        (50, 1, '/Applications/Term.app/Contents/MacOS/Term', 'Term'),
        (60, 50, '/bin/zsh', '-zsh')]


def table(*rows):
    return BASE + list(rows)


def test_self_wrapper_naming_the_module_is_owned_not_a_peer():
    # the REQ-022 attempt-1 case: the parent shell's command line names the script
    t = table((70, 60, '/bin/zsh', "/bin/zsh -c 'cd experiments/v2_sim && python null_control_batch.py run'"),
              (71, 70, PY, PY + ' null_control_batch.py run'))
    r = P.evaluate(t, 71, MOD)
    assert r['passed'] is True and r['peers'] == [] and {70, 60, 50, 1} <= set(r['owned'])


def test_grandparent_wrapper_and_own_worker_pool_are_owned():
    t = table((70, 60, '/bin/zsh', 'zsh -c "echo null_control_batch.py; python -c \'import null_control_batch\'"'),
              (71, 70, '/bin/bash', 'bash -c "python -c \'import null_control_batch as N; N.run()\'"'),
              (72, 71, PY, PY + " -c import null_control_batch as N; N.run()"),
              (73, 72, PY, PY + ' -c from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=5)'),
              (74, 72, PY, PY + " -c import null_control_batch as N; N.run()"))      # a forked worker copy
    r = P.evaluate(t, 72, MOD)
    assert r['passed'] is True and {70, 71, 73, 74} <= set(r['owned'])


def test_same_module_peer_launched_by_python_c_is_detected():
    # the blind spot of the frozen gate: a sibling started with python -c, without the file name
    t = table((71, 60, PY, PY + ' null_control_batch.py run'),
              (90, 1, PY, PY + " -c import null_control_batch as N; N.run()"))
    r = P.evaluate(t, 71, MOD)
    assert r['passed'] is False and [p['pid'] for p in r['peers']] == [90]
    assert r['peers'][0]['reason'] == 'same module'


def test_same_module_peers_by_file_name_and_by_dash_m_are_detected():
    t = table((71, 60, PY, PY + ' -c "import null_control_batch as N; N.run()"'),
              (91, 1, PY, PY + ' experiments/v2_sim/null_control_batch.py run'),
              (92, 1, PY, PY + ' -m null_control_batch analyze'))
    r = P.evaluate(t, 71, MOD)
    assert sorted(p['pid'] for p in r['peers']) == [91, 92] and r['passed'] is False


def test_unrelated_python_and_similar_names_are_not_peers():
    t = table((71, 60, PY, PY + ' null_control_batch.py run'),
              (93, 1, PY, PY + ' -m http.server'),
              (94, 1, PY, PY + ' null_control_batch_notes.py'),         # a different word, not the module
              (95, 1, '/usr/libexec/sharingd', '(sharingd)'))            # unreadable but not a suspect executable
    r = P.evaluate(t, 71, MOD)
    assert r['passed'] is True and r['peers'] == [] and r['refusals'] == []


def test_other_stage_batch_and_server_peers_are_detected():
    t = table((71, 60, PY, PY + ' null_control_batch.py run'),
              (96, 1, PY, PY + ' experiments/code_routing/run.py --stage live --allow-contention'),
              (97, 1, '/opt/llama/llama-server', '/opt/llama/llama-server -m x.gguf --port 8193'),
              (98, 1, PY, PY + ' experiments/v2_sim/dev_batch_dr.py run'))
    r = P.evaluate(t, 71, MOD)
    assert sorted(p['pid'] for p in r['peers']) == [96, 97, 98]
    assert {p['reason'] for p in r['peers']} == {'peer pattern'}


def test_unknown_identity_refuses_conservatively():
    t = table((71, 60, PY, PY + ' null_control_batch.py run'),
              (99, 1, '/opt/homebrew/bin/python3.12', '(python3.12)'))  # a python whose command line is hidden
    r = P.evaluate(t, 71, MOD)
    assert r['passed'] is False and r['peers'] == [] and 'pid 99' in r['refusals'][0]
    assert P.evaluate(None, 71, MOD)['refusals'] == ['unknown process identity: process table unreadable']
    assert 'not in the table' in P.evaluate(table(), 71, MOD)['refusals'][0]
    broken = [(71, 60, PY, PY + ' null_control_batch.py run')]           # parent 60 absent: chain broken
    assert 'ancestor chain' in P.evaluate(broken, 71, MOD)['refusals'][0]
    cyclic = [(71, 72, PY, 'x'), (72, 71, PY, 'y')]
    assert 'ancestor chain' in P.evaluate(cyclic, 71, MOD)['refusals'][0]


def test_real_ps_text_hidden_interpreter_refuses_and_hidden_system_process_does_not():
    # macOS ps prints hidden command lines as '(name)'; comm is read by its own ps call (last column, not truncated)
    args_text = ('    1     0 /sbin/launchd\n   60     1 -zsh\n   71    60 %s null_control_batch.py run\n'
                 '   99     1 (python3.12)\n  100     1 (mlhostd)\n  101     1 (Python)\n' % PY)
    comm_text = ('    1 /sbin/launchd\n   60 -zsh\n   71 %s\n   99 (python3.12)\n  100 (mlhostd)\n'
                 '  101 (Python)\n' % PY)
    tab = P.parse_ps(args_text, comm_text)
    r = P.evaluate(tab, 71, MOD)
    assert r['passed'] is False and r['peers'] == []
    assert sorted(int(x.split('pid ')[1].split()[0]) for x in r['refusals']) == [99, 101]   # mlhostd is not suspect


def test_parse_ps_keeps_names_with_spaces_and_full_command_lines():
    tab = P.parse_ps('  200     1 /System/Library/Core Audio Driver --x\n',
                     '  200 /System/Library/Core Audio Driver\n')
    assert tab == [(200, 1, '/System/Library/Core Audio Driver', '/System/Library/Core Audio Driver --x')]


def test_more_same_module_forms_are_detected_and_non_interpreters_are_not():
    t = table((71, 60, PY, PY + ' null_control_batch.py run'),
              (81, 1, PY, PY + ' -mnull_control_batch run'),                    # -m without a space
              (82, 1, PY, PY + ' /Users/u/repo/NULL_CONTROL_BATCH.py run'),      # case variant path
              (83, 1, '/Users/u/.local/bin/uv', 'uv run python null_control_batch.py run'),
              (84, 1, '/usr/bin/vim', 'vim experiments/v2_sim/null_control_batch.py'),   # editor, not a peer
              (85, 60, '/usr/bin/tee', 'tee null_control_batch.log'))            # own pipeline stage, not a peer
    r = P.evaluate(t, 71, MOD)
    assert sorted(p['pid'] for p in r['peers']) == [81, 82, 83]
    assert {p['command'] for p in r['peers']} == {'python', 'uv'}


def test_stage_runner_detected_whatever_the_flag_order():
    t = table((71, 60, PY, PY + ' null_control_batch.py run'),
              (86, 1, PY, PY + ' experiments/code_routing/run.py --allow-contention --stage live'),
              (87, 1, PY, PY + ' run.py --limit 5 --stage log'))
    assert sorted(p['pid'] for p in P.evaluate(t, 71, MOD)['peers']) == [86, 87]


def test_live_gate_records_version_and_the_real_source_hash():
    import hashlib
    r = P.process_gate(MOD)                                               # read-only ps; result depends on the host
    assert r['version'] == 'process_gate_v1'
    src = ROOT / 'experiments/v2_sim/process_gate_v1.py'
    assert r['source_sha256'] == hashlib.sha256(src.read_bytes()).hexdigest()
    assert set(r) >= {'passed', 'peers', 'refusals', 'owned'} and r['self_pid'] in r['owned']


def test_interpreter_under_a_path_with_spaces_is_detected():
    sp = '/Users/u/My Drive/repo/.venv/bin/python'
    tab = P.parse_ps('    1     0 /sbin/launchd\n   60     1 -zsh\n   71    60 %s null_control_batch.py run\n'
                     '   88     1 %s null_control_batch.py run\n' % (PY, sp),
                     '    1 /sbin/launchd\n   60 -zsh\n   71 %s\n   88 %s\n' % (PY, sp))
    r = P.evaluate(tab, 71, MOD)
    assert r['peers'] == [{'pid': 88, 'reason': 'same module', 'command': 'python'}]


def test_stdin_heredoc_and_repl_peers_are_detected_and_the_own_heredoc_is_not():
    # macOS ps prints heredoc newlines inside the launching shell's arguments as the four characters \012
    doc = "bash -c %s - <<EOF\\012import null_control_batch as N\\012N.run()\\012EOF" % PY
    t = table((70, 60, '/bin/bash', doc), (71, 70, PY, PY + ' -'),                          # self: own heredoc
              (80, 1, '/bin/bash', doc), (81, 80, PY, PY + ' -'),                           # a peer heredoc
              (82, 1, '/bin/bash', 'bash -c cd v2_sim && python3 -i  # null_control_batch'),
              (83, 82, '/usr/bin/python3', 'python3 -i'),                                   # a peer REPL
              (84, 1, '/bin/zsh', 'zsh -c cat null_control_batch.log; python3 other.py'),
              (85, 84, '/usr/bin/python3', 'python3 other.py'),                             # a script: not a peer
              (86, 60, '/usr/bin/python3', 'python3 -'))                                    # launcher names nothing
    r = P.evaluate(t, 71, MOD)
    assert sorted(p['pid'] for p in r['peers']) == [81, 83] and {70, 60} <= set(r['owned'])
    assert all(p['reason'].startswith('same module (stdin') for p in r['peers'])
    assert P.normalized('a\\012import x') == 'a import x'
    assert not P.reads_stdin(PY, PY + ' -Bc import x') and not P.reads_stdin(PY, PY + ' -X dev -m x')
    assert P.reads_stdin(PY, PY + ' -X dev -') and P.reads_stdin(PY, PY + ' -u')


def test_stdin_forms_under_spaced_paths_clusters_dev_stdin_and_a_shared_wrapper():
    sp = '/Users/u/Library/Application Support/hatch/env/bin/python'
    for comm, args in [(sp, sp + ' -'), (sp, sp + ' -i'), (sp, sp), (PY, PY + ' -uX dev -'), (PY, PY + ' -uW error -'),
                       (PY, PY + ' -uXimporttime -'), (PY, PY + ' -BXfrozen_modules=off -'), (PY, PY + ' /dev/stdin'),
                       (PY, PY + ' /dev/fd/0'), (PY, PY + ' -- -')]:
        assert P.reads_stdin(comm, args), args
    for comm, args in [(sp, sp + ' x.py'), (PY, PY + ' -uX dev s.py'), (PY, PY + ' -Wd s.py'), (PY, PY + ' -qc pass'),
                       (PY, PY + ' -- s.py'), (PY, PY + ' -mmod')]:
        assert not P.reads_stdin(comm, args), args
    two = "bash -c python - <<EOF &\\012import null_control_batch as N; N.run(1)\\012EOF\\012python - <<EOF\\012" \
          "import null_control_batch as N; N.run(2)\\012EOF\\012wait"
    t = table((70, 60, '/bin/bash', two), (71, 70, PY, PY + ' -'), (72, 70, PY, PY + ' -'))
    assert [p['pid'] for p in P.evaluate(t, 71, MOD)['peers']] == [72]           # the other copy, same wrapper
    t = table((70, 60, '/bin/bash', "bash -c %s - <<EOF\\012import null_control_batch\\012EOF" % sp),
              (71, 60, PY, PY + ' null_control_batch.py run'), (80, 70, sp, sp + ' -'))
    assert [p['pid'] for p in P.evaluate(t, 71, MOD)['peers']] == [80]


def test_suffixed_interpreter_builds_and_batch_successors_are_detected():
    t = table((71, 60, PY, PY + ' null_control_batch.py run'),
              (61, 1, '/u/.local/bin/python3.13t', '/u/.local/bin/python3.13t null_control_batch.py run'),
              (62, 1, '/usr/local/bin/python3.12-intel64', 'python3.12-intel64 -m null_control_batch'),
              (63, 1, '/opt/py/python3.12d', 'python3.12d null_control_batch.py'),
              (64, 1, PY, PY + ' experiments/v2_sim/coverage_batch_v2.py run'),
              (65, 1, PY, PY + ' run_dev_batch.py'),
              (66, 1, '/opt/pyfoo/pythonfoo', 'pythonfoo null_control_batch.py'))          # not an interpreter name
    r = P.evaluate(t, 71, MOD)
    assert {p['pid']: p['reason'] for p in r['peers']} == {61: 'same module', 62: 'same module', 63: 'same module',
                                                           64: 'peer pattern', 65: 'peer pattern'}


def test_hidden_macos_daemons_named_uv_do_not_refuse_but_a_hidden_uv_does():
    t = table((71, 60, PY, PY + ' null_control_batch.py run'),
              (570, 1, '/System/Library/UVCAssistant', '(UVCAssistant)'),
              (1141, 1, '/System/Library/UVFSService', '(UVFSService)'))
    assert P.evaluate(t, 71, MOD)['passed'] is True
    r = P.evaluate(t + [(1200, 1, '/u/.local/bin/uv', '(uv)')], 71, MOD)
    assert r['passed'] is False and 'pid 1200 (uv)' in r['refusals'][0]
