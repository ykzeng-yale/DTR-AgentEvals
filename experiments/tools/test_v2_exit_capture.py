"""Deterministic fixtures for the DTR-REQ-005 all-exit diagnostic capture (binding `xc1`, lead answer 1).

Runs real git in temporary repositories through an injected bash executor: no model, container, server,
evaluator or network. Every expected value here is written out BY HAND in literal form -- state names, sha256
digests of the exact fixture bytes, byte counts, caps, command labels, the full exclusion list -- so a defect
in exit_capture.py cannot be cancelled by the same defect in this file. The digests below are of these
literal contents:
    'n = 1\\n'   -> df31c7f4ef3af48aafd4e8c743ab41d6592018b90fd7913cf82284d50bd18a5b   (6 bytes)
    'hello\\n'   -> 5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03   (6 bytes)
    'x' * 100   -> 09ecb6ebc8bcefc733f6f2ec44f791abeed6a99edf0cc31519637898aebd52d8   (100 bytes)
    b'\\x00\\x01\\x02' -> ae4b3280e56e2faf83f414a6e3dabe9d5fbe18976544c05fed121accb85b53fc   (3 bytes)
    the empty file -> e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  (0 bytes)

Where a git-computed value is needed (the final tree SHA, the diff body) this file computes it with its OWN
explicit git invocations -- never through the module's command templates -- so a wrong template cannot agree
with a wrong expectation. The frozen yaml-v1 sources (pilot_episode/pilot_runner/pilot_cohort) are not
imported or touched.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_agent'))
import exit_capture as XC  # noqa: E402
import workspace_capture as WC  # noqa: E402

EMPTY_SHA = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
N_EQ_1_SHA = 'df31c7f4ef3af48aafd4e8c743ab41d6592018b90fd7913cf82284d50bd18a5b'
HELLO_SHA = '5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03'
X100_SHA = '09ecb6ebc8bcefc733f6f2ec44f791abeed6a99edf0cc31519637898aebd52d8'
BIN_SHA = 'ae4b3280e56e2faf83f414a6e3dabe9d5fbe18976544c05fed121accb85b53fc'

DECLARED_CAPS = dict(status_bytes=65536, diff_bytes=262144, untracked_list_bytes=65536, untracked_paths=64,
                     untracked_content_files=16, untracked_file_bytes=32768, path_chars=512, command_log=64)
DECLARED_EXCLUSIONS = [
    'gitignored paths (excluded by `git add -A` under the private index and by `--exclude-standard`)',
    'anything outside the container workdir',
    'untracked directories are represented by their files only',
    'untracked non-regular files (sockets, symlinks, directories) get no digest or contents',
    'binary untracked contents are omitted; the full-content digest is still recorded',
    'contents/paths beyond the recorded caps are counted but not recorded',
]
DIGEST_SCOPE = 'sha256 over the FULL in-container body before truncation, not over the recorded text'
FILE_DIGEST_SCOPE = 'sha256 over the FULL file content before truncation, not over the recorded content'


def git(repo, *a, **kw):
    return subprocess.run(['git', '-C', str(repo), *a], check=True, capture_output=True, text=True, **kw)


def make_repo(tmp_path):
    r = tmp_path / 'testbed'
    r.mkdir()
    git(r, 'init', '-q')
    git(r, 'config', 'user.email', 'f@x')
    git(r, 'config', 'user.name', 'f')
    (r / 'keep.py').write_text('a = 1\n')
    (r / 'mod.py').write_text('x = 1\n')
    (r / 'gone.py').write_text('bye\n')
    (r / 'staged.py').write_text('s = 1\n')
    (r / 'committed.py').write_text('c = 1\n')
    (r / '.gitignore').write_text('*.pyc\n')
    git(r, 'add', '-A')
    git(r, 'commit', '-qm', 'base')
    return r


def whole_worktree_tree(repo, index_name='independent-index'):
    """The whole working tree's SHA, computed here with explicit git commands through a private index.

    Deliberately NOT routed through workspace_capture.TREE_CMD: a snapshot that silently looked at HEAD, or
    at the agent's index, would disagree with this value instead of matching it."""
    index = Path(repo).parent / index_name
    env = dict(os.environ, GIT_INDEX_FILE=str(index))
    try:
        git(repo, 'read-tree', 'HEAD', env=env)
        git(repo, 'add', '-A', env=env)
        return git(repo, 'write-tree', env=env).stdout.strip()
    finally:
        if index.exists():
            index.unlink()


def tree_paths(repo, tree_sha):
    out = git(repo, 'ls-tree', '-r', '--name-only', tree_sha).stdout
    return sorted(line for line in out.splitlines() if line)


def expected_diff(repo, base, final=None):
    args = ['diff', '--binary', '--full-index', base] + ([final] if final else [])
    return git(repo, *args).stdout


def executor(repo):
    """Same contract as workspace_capture's fixtures: execute(command) -> (returncode, merged output)."""
    def ex(cmd):
        p = subprocess.run(['bash', '-c', cmd], capture_output=True, text=True)
        return p.returncode, p.stdout + p.stderr
    return ex


def states(rec):
    return {name: section['state'] for name, section in rec['sections'].items()}


def labels(rec):
    return [c['label'] for c in rec['commands']]


# ---------------------------------------------------------------- completed observations

def test_a_clean_workspace_is_recorded_as_no_change_not_unavailable(tmp_path):
    r = make_repo(tmp_path)
    ex = executor(r)
    base = whole_worktree_tree(r)
    rec = XC.capture(ex, base, exit_status='LimitsExceeded', wd=str(r))
    assert rec['status'] == 'no_change'
    assert rec['changes_observed'] is False
    assert states(rec) == {'tree': 'captured', 'status': 'no_change', 'diff': 'no_change', 'untracked': 'no_change'}
    assert rec['failures'] == []
    assert rec['capture_error'] is None
    assert rec['base_tree_state'] == 'recorded'
    assert rec['sections']['tree']['sha'] == base                 # the independently computed tree
    assert sorted(tree_paths(r, rec['sections']['tree']['sha'])) == [
        '.gitignore', 'committed.py', 'gone.py', 'keep.py', 'mod.py', 'staged.py']
    assert rec['sections']['diff']['mode'] == 'tree_to_tree'
    assert rec['sections']['diff']['final_tree'] == base          # nothing changed, so the trees are equal
    assert rec['sections']['diff']['text'] == ''                  # an OBSERVED empty diff, not an absent one
    assert rec['sections']['diff']['full_bytes'] == 0
    assert rec['sections']['diff']['sha256'] == EMPTY_SHA
    assert rec['sections']['diff']['digest_scope'] == DIGEST_SCOPE
    assert rec['sections']['diff']['truncated'] is False
    assert rec['sections']['diff']['container_preamble'] is None
    assert rec['sections']['status']['text'] == ''
    assert rec['sections']['status']['full_bytes'] == 0
    assert rec['sections']['status']['sha256'] == EMPTY_SHA
    assert rec['sections']['status']['recorded_chars'] == 0
    assert rec['sections']['untracked']['n_paths'] == 0
    assert rec['sections']['untracked']['paths'] == []
    assert rec['sections']['untracked']['paths_complete'] is True
    assert rec['sections']['untracked']['n_paths_is_lower_bound'] is False
    assert rec['sections']['untracked']['incomplete_reason'] is None
    assert labels(rec) == ['tree', 'status', 'diff', 'untracked_list']
    assert [c['state'] for c in rec['commands']] == ['ok', 'ok', 'ok', 'ok']


def test_tracked_modifications_appear_in_the_diff_and_the_status_snapshot(tmp_path):
    r = make_repo(tmp_path)
    ex = executor(r)
    base = whole_worktree_tree(r)
    (r / 'mod.py').write_text('x = 2\n')                                     # modified, unstaged
    (r / 'staged.py').write_text('s = 2\n')
    git(r, 'add', 'staged.py')                                               # staged
    (r / 'gone.py').unlink()                                                 # deleted
    (r / 'committed.py').write_text('c = 2\n')
    git(r, 'commit', '-qm', 'agent commit', '--', 'committed.py')            # committed
    (r / 'junk.pyc').write_text('ignored')                                   # gitignored: declared exclusion
    final = whole_worktree_tree(r, 'independent-index-final')
    body = expected_diff(r, base, final)
    rec = XC.capture(ex, base, exit_status='Submitted', wd=str(r))
    diff = rec['sections']['diff']
    assert rec['status'] == 'changed'
    assert rec['changes_observed'] is True
    assert rec['sections']['tree']['sha'] == final
    assert rec['sections']['tree']['sha'] != base
    assert diff['state'] == 'captured'
    assert diff['mode'] == 'tree_to_tree'
    assert diff['final_tree'] == final
    assert diff['truncated'] is False
    assert diff['text'] == body                                  # the diff git itself produces, byte for byte
    assert diff['full_bytes'] == len(body.encode('utf-8'))
    assert 'gone.py' not in tree_paths(r, final)
    for name in ('mod.py', 'staged.py', 'gone.py', 'committed.py'):
        assert name in diff['text'], name
    assert 'keep.py' not in diff['text']
    assert 'junk.pyc' not in diff['text']
    assert 'junk.pyc' not in rec['sections']['status']['text']
    assert rec['sections']['status']['text'] == ' D gone.py\n M mod.py\nM  staged.py\n'
    assert rec['sections']['untracked']['state'] == 'no_change'               # only the ignored file is untracked
    assert rec['sections']['untracked']['n_paths'] == 0


def test_untracked_files_are_recorded_with_digests_and_bounded_contents(tmp_path):
    r = make_repo(tmp_path)
    ex = executor(r)
    base = whole_worktree_tree(r)
    (r / 'new_file.py').write_text('n = 1\n')
    (r / 'sub').mkdir()
    (r / 'sub' / 'notes.txt').write_text('hello\n')
    (r / 'junk.pyc').write_text('ignored')
    rec = XC.capture(ex, base, exit_status='ContextWindowExceeded', wd=str(r))
    u = rec['sections']['untracked']
    assert rec['status'] == 'changed'
    assert rec['changes_observed'] is True
    assert u['state'] == 'captured'
    assert u['n_paths'] == 2
    assert u['n_recorded'] == 2
    assert u['n_with_content'] == 2
    assert u['n_with_digest'] == 2
    assert u['paths_complete'] is True
    assert u['list_truncated'] is False
    assert u['path_cap_reached'] is False
    assert u['partial_path_dropped'] is False
    assert u['incomplete_reason'] is None
    by = {e['path']: e for e in u['paths']}
    assert sorted(by) == ['new_file.py', 'sub/notes.txt']
    assert by['new_file.py']['bytes'] == 6
    assert by['new_file.py']['sha256'] == N_EQ_1_SHA
    assert by['new_file.py']['digest_scope'] == FILE_DIGEST_SCOPE
    assert by['new_file.py']['content'] == 'n = 1\n'
    assert by['new_file.py']['content_state'] == 'recorded'
    assert by['new_file.py']['truncated'] is False
    assert by['sub/notes.txt']['bytes'] == 6
    assert by['sub/notes.txt']['sha256'] == HELLO_SHA
    assert by['sub/notes.txt']['content'] == 'hello\n'
    assert by['sub/notes.txt']['content_state'] == 'recorded'
    # the private-index tree includes new non-ignored paths, so they also show up as diff additions
    assert 'new_file.py' in rec['sections']['diff']['text']
    assert 'sub/notes.txt' in rec['sections']['diff']['text']
    assert 'junk.pyc' not in rec['sections']['diff']['text']
    assert 'new_file.py' in tree_paths(r, rec['sections']['tree']['sha'])
    assert 'junk.pyc' not in tree_paths(r, rec['sections']['tree']['sha'])


def test_an_oversized_file_and_diff_are_truncated_with_flags_and_recorded_caps(tmp_path):
    r = make_repo(tmp_path)
    ex = executor(r)
    base = whole_worktree_tree(r)
    (r / 'big.txt').write_text('x' * 100)
    rec = XC.capture(ex, base, exit_status='Submitted', wd=str(r),
                     caps=dict(untracked_file_bytes=10, diff_bytes=20))
    entry = rec['sections']['untracked']['paths'][0]
    assert entry['path'] == 'big.txt'
    assert entry['bytes'] == 100                                   # the FULL size, not the recorded slice
    assert entry['sha256'] == X100_SHA                             # digest of the FULL content
    assert entry['digest_scope'] == FILE_DIGEST_SCOPE
    assert entry['content'] == 'xxxxxxxxxx'
    assert entry['truncated'] is True
    assert entry['content_state'] == 'truncated'
    assert entry['cap_bytes'] == 10
    diff = rec['sections']['diff']
    full = expected_diff(r, base, whole_worktree_tree(r, 'independent-index-final'))
    assert diff['state'] == 'captured'
    assert diff['truncated'] is True
    assert diff['cap_bytes'] == 20
    assert diff['text'] == full[:20]                               # the first 20 bytes git itself produced
    assert diff['recorded_chars'] == 20
    assert diff['full_bytes'] == len(full.encode('utf-8'))
    assert diff['full_bytes'] > 20
    assert rec['caps']['untracked_file_bytes'] == 10
    assert rec['caps']['diff_bytes'] == 20
    assert rec['caps']['untracked_paths'] == 64                    # unspecified caps keep the declared defaults
    assert rec['status'] == 'changed'
    assert rec['changes_observed'] is True


def test_untracked_path_and_content_caps_are_counted_and_flagged(tmp_path):
    r = make_repo(tmp_path)
    ex = executor(r)
    base = whole_worktree_tree(r)
    for name in ('a1.txt', 'a2.txt', 'a3.txt', 'a4.txt', 'a5.txt'):
        (r / name).write_text('n = 1\n')
    rec = XC.capture(ex, base, wd=str(r), caps=dict(untracked_paths=3, untracked_content_files=1))
    u = rec['sections']['untracked']
    assert u['state'] == 'captured'
    assert u['n_paths'] == 5                                       # all five are counted
    assert u['n_recorded'] == 3                                    # only three are recorded
    assert u['n_with_content'] == 1                                # only one carries contents
    assert u['n_with_digest'] == 1
    assert u['path_cap_reached'] is True
    assert u['list_truncated'] is False
    assert u['paths_complete'] is True
    assert u['n_paths_is_lower_bound'] is False                    # the COUNT is complete; the detail is capped
    assert u['incomplete_reason'] is None
    assert [e['path'] for e in u['paths']] == ['a1.txt', 'a2.txt', 'a3.txt']
    assert u['paths'][0]['content'] == 'n = 1\n'
    assert u['paths'][0]['sha256'] == N_EQ_1_SHA
    assert u['paths'][1]['content'] is None
    assert u['paths'][1]['sha256'] is None
    assert u['paths'][1]['content_state'] == 'not_requested'
    assert u['paths'][1]['reason'] == 'beyond the recorded content-file cap; path counted only'
    assert u['paths'][2]['content_state'] == 'not_requested'
    assert rec['caps']['untracked_paths'] == 3
    assert rec['caps']['untracked_content_files'] == 1
    assert rec['status'] == 'changed'
    assert rec['failures'] == []


def test_a_binary_file_keeps_its_digest_and_a_broken_symlink_is_unavailable(tmp_path):
    r = make_repo(tmp_path)
    ex = executor(r)
    base = whole_worktree_tree(r)
    (r / 'blob.bin').write_bytes(b'\x00\x01\x02')
    (r / 'link.txt').symlink_to('nowhere-xyz')
    rec = XC.capture(ex, base, exit_status='Submitted', wd=str(r))
    u = rec['sections']['untracked']
    by = {e['path']: e for e in u['paths']}
    assert sorted(by) == ['blob.bin', 'link.txt']
    assert by['blob.bin']['bytes'] == 3
    assert by['blob.bin']['sha256'] == BIN_SHA
    assert by['blob.bin']['content'] is None
    assert by['blob.bin']['content_state'] == 'binary_omitted'
    assert by['link.txt']['content'] is None
    assert by['link.txt']['sha256'] is None
    assert by['link.txt']['content_state'] == 'unavailable'        # absent content, not empty content
    assert by['link.txt']['bytes'] is None
    # a captured digest without recorded text still counts as captured evidence
    assert u['n_recorded'] == 2
    assert u['n_with_content'] == 0
    assert u['n_with_digest'] == 1
    assert u['state'] == 'captured'
    assert rec['status'] == 'changed'


def test_an_unsafe_or_oversized_path_is_not_published_as_a_truncated_prefix(tmp_path):
    r = make_repo(tmp_path)
    ex = executor(r)
    base = whole_worktree_tree(r)
    (r / ('long_' + 'q' * 40 + '.txt')).write_text('n = 1\n')
    rec = XC.capture(ex, base, wd=str(r), caps=dict(path_chars=12))
    entry = rec['sections']['untracked']['paths'][0]
    assert entry['path'] is None                                   # never a prefix that looks like a real path
    assert entry['path_chars'] == 49
    assert entry['content'] is None
    assert entry['bytes'] is None
    assert entry['sha256'] is None
    assert entry['content_state'] == 'unavailable'
    assert entry['reason'] == 'path not recorded: unsafe or beyond the 12-character path cap'
    assert rec['sections']['untracked']['n_paths'] == 1
    assert rec['sections']['untracked']['n_with_digest'] == 0


# ---------------------------------------------------------------- absent is never empty

def test_an_executor_that_raises_is_recorded_as_failed_without_raising(tmp_path):
    def ex(cmd):
        raise RuntimeError('container is gone')
    rec = XC.capture(ex, '0' * 40, exit_status='RuntimeError', wd='/testbed')
    assert rec['status'] == 'failed'
    assert rec['changes_observed'] is None
    assert states(rec) == {'tree': 'failed', 'status': 'failed', 'diff': 'failed', 'untracked': 'failed'}
    assert rec['sections']['diff']['text'] is None                 # never an empty diff
    assert rec['sections']['diff']['full_bytes'] is None
    assert rec['sections']['status']['text'] is None
    u = rec['sections']['untracked']
    assert u['paths'] is None                                      # never an empty workspace
    assert u['n_paths'] is None
    assert u['n_recorded'] is None                                 # unknown stays unknown, never 0
    assert u['n_with_content'] is None
    assert u['n_with_digest'] is None
    assert u['paths_complete'] is None
    assert u['list_truncated'] is None
    assert [f['section'] for f in rec['failures']] == ['tree', 'status', 'diff', 'untracked']
    assert all(f['reason'] for f in rec['failures'])
    assert labels(rec) == ['tree', 'status', 'diff', 'untracked_list']
    assert rec['commands'][0]['error'] == 'RuntimeError: container is gone'
    assert rec['sections']['diff']['mode'] == 'base_to_worktree'   # no final tree was obtainable


def test_an_executor_that_times_out_is_recorded_as_timeout_without_raising(tmp_path):
    def ex(cmd):
        raise subprocess.TimeoutExpired(cmd='docker exec', timeout=60)
    rec = XC.capture(ex, '1' * 40, exit_status='EpisodeDeadline', wd='/testbed')
    assert rec['status'] == 'timeout'
    assert rec['changes_observed'] is None
    assert states(rec) == {'tree': 'timeout', 'status': 'timeout', 'diff': 'timeout', 'untracked': 'timeout'}
    assert rec['sections']['diff']['text'] is None
    assert rec['sections']['untracked']['paths'] is None
    assert rec['per_command_timeout_s'] == 60
    assert rec['per_command_timeout_enforced_by'] == 'injected executor'
    assert [c['state'] for c in rec['commands']] == ['timeout', 'timeout', 'timeout', 'timeout']


def test_a_mixture_of_degraded_states_never_rolls_up_as_a_completed_observation(tmp_path):
    """Nothing was captured, so the roll-up may not read 'partial' as if something had been."""
    def ex(cmd):
        if 'write-tree' in cmd:
            raise subprocess.TimeoutExpired(cmd='docker exec', timeout=60)
        raise RuntimeError('container is gone')
    rec = XC.capture(ex, None, exit_status='RuntimeError', wd='/testbed')
    assert states(rec) == {'tree': 'timeout', 'status': 'failed', 'diff': 'unavailable', 'untracked': 'failed'}
    assert rec['status'] == 'degraded'
    assert rec['changes_observed'] is None
    assert [f['section'] for f in rec['failures']] == ['tree', 'status', 'diff', 'untracked']


def test_the_total_budget_stops_dispatch_and_is_recorded_as_timeout():
    calls = []

    def ex(cmd):
        calls.append(cmd)
        return 0, ''
    rec = XC.capture(ex, '2' * 40, exit_status='LimitsExceeded', wd='/testbed', budget_s=0, clock=lambda: 1000.0)
    assert calls == []                                             # cleanup is never delayed by a spent budget
    assert rec['status'] == 'timeout'
    assert rec['total_budget_s'] == 0
    assert states(rec) == {'tree': 'timeout', 'status': 'timeout', 'diff': 'timeout', 'untracked': 'timeout'}
    assert rec['commands'][0]['reason'] == 'total diagnostic budget exhausted before dispatch'


def test_a_slow_executor_exhausts_the_budget_and_the_remaining_sections_are_timeout(tmp_path):
    r = make_repo(tmp_path)
    real = executor(r)
    base = whole_worktree_tree(r)
    now = [0.0]

    def ex(cmd):
        now[0] += 100.0
        return real(cmd)
    rec = XC.capture(ex, base, exit_status='Submitted', wd=str(r), budget_s=150, clock=lambda: now[0])
    # deadline 150 s: tree dispatches at 0, status at 100, and nothing after 200.
    assert states(rec) == {'tree': 'captured', 'status': 'no_change', 'diff': 'timeout', 'untracked': 'timeout'}
    assert rec['status'] == 'partial'
    assert rec['changes_observed'] is None
    assert rec['sections']['diff']['text'] is None
    assert rec['commands'][0]['seconds'] == 100.0
    assert [f['section'] for f in rec['failures']] == ['diff', 'untracked']


def test_a_missing_starting_tree_is_unavailable_not_no_change(tmp_path):
    r = make_repo(tmp_path)
    ex = executor(r)
    rec = XC.capture(ex, None, exit_status='Submitted', wd=str(r))
    assert rec['base_tree'] is None
    assert rec['base_tree_state'] == 'unavailable'
    diff = rec['sections']['diff']
    assert diff['state'] == 'unavailable'
    assert diff['text'] is None
    assert diff['full_bytes'] is None
    assert diff['mode'] is None
    assert diff['reason'] == 'no recorded starting tree for this episode'
    assert rec['status'] == 'partial'
    assert rec['changes_observed'] is None
    assert [f['section'] for f in rec['failures']] == ['diff']
    assert labels(rec) == ['tree', 'status', 'untracked_list']      # no diff was attempted


@pytest.mark.parametrize('base', [12, b'0' * 40, 0.5, ['0' * 40], {'sha': '0' * 40}, True])
def test_a_base_tree_that_is_not_a_sha_string_cannot_block_the_capture(tmp_path, base):
    """A non-string base tree must degrade the diff, never raise out of capture() into cleanup."""
    r = make_repo(tmp_path)
    ex = executor(r)
    rec = XC.capture(ex, base, exit_status='LimitsExceeded', wd=str(r))
    assert rec['base_tree'] is None
    assert rec['base_tree_state'] == 'unavailable'
    assert rec['capture_error'] is None
    assert rec['sections']['diff']['state'] == 'unavailable'
    assert rec['sections']['tree']['state'] == 'captured'
    assert rec['status'] == 'partial'
    assert json.loads(json.dumps(rec)) == rec


def test_an_internal_capture_error_still_records_every_section_key(tmp_path):
    r = make_repo(tmp_path)
    ex = executor(r)
    rec = XC.capture(ex, '3' * 40, exit_status='Submitted', wd=Path(r))   # a Path, not a str: shlex refuses it
    assert rec['status'] == 'failed'
    assert rec['changes_observed'] is None
    assert sorted(rec['sections']) == ['diff', 'status', 'tree', 'untracked']
    assert rec['sections']['diff']['state'] == 'unavailable'
    assert rec['sections']['diff']['reason'] == 'section not reached: the capture did not complete'
    assert rec['sections']['diff']['text'] is None
    assert rec['sections']['untracked']['n_paths'] is None
    assert rec['capture_error'].startswith('TypeError')
    assert rec['failures'][0]['section'] == 'capture'
    assert [f['section'] for f in rec['failures']] == ['capture', 'status', 'diff', 'untracked']
    assert rec['sections']['tree']['state'] == 'captured'                 # the tree ran before the break
    assert labels(rec) == ['tree']


def test_a_truncated_untracked_listing_is_never_recorded_as_an_empty_workspace(tmp_path):
    r = make_repo(tmp_path)
    ex = executor(r)
    base = whole_worktree_tree(r)
    (r / 'brand_new.py').write_text('n = 1\n')
    rec = XC.capture(ex, base, exit_status='LimitsExceeded', wd=str(r),
                     caps=dict(untracked_list_bytes=3))
    u = rec['sections']['untracked']
    assert u['state'] == 'incomplete'                       # NOT no_change: the listing is known partial
    assert u['n_paths'] == 0
    assert u['n_paths_is_lower_bound'] is True
    assert u['paths_complete'] is False
    assert u['list_truncated'] is True
    assert u['partial_path_dropped'] is True
    assert u['cap_list_bytes'] == 3
    assert u['incomplete_reason'] == (
        'the untracked listing is incomplete (byte-truncated at the 3-byte list cap; a partial trailing '
        'path was dropped): the recorded paths are a subset and n_paths is a lower bound, not an '
        'observation of how many exist')
    assert [f['section'] for f in rec['failures']] == ['untracked']
    assert rec['failures'][0]['state'] == 'incomplete'
    assert rec['status'] == 'partial'
    # the new file is still observed, by the tree snapshot, the diff and the porcelain status
    assert rec['changes_observed'] is True
    assert rec['sections']['status']['text'] == '?? brand_new.py\n'
    assert 'brand_new.py' in rec['sections']['diff']['text']


def test_a_truncated_listing_with_a_failed_tree_still_reports_changes_from_the_status_snapshot(tmp_path):
    """base_to_worktree cannot see an untracked file, so the porcelain status must count as a change signal."""
    r = make_repo(tmp_path)
    real = executor(r)
    base = whole_worktree_tree(r)
    (r / 'brand_new.py').write_text('n = 1\n')

    def ex(cmd):
        if 'write-tree' in cmd:
            return 1, 'fatal: simulated private-index failure'
        return real(cmd)
    rec = XC.capture(ex, base, exit_status='LimitsExceeded', wd=str(r), caps=dict(untracked_list_bytes=3))
    assert states(rec) == {'tree': 'failed', 'status': 'captured', 'diff': 'no_change',
                           'untracked': 'incomplete'}
    assert rec['sections']['diff']['mode'] == 'base_to_worktree'
    assert rec['sections']['diff']['text'] == ''            # git diff <base> is blind to untracked files
    assert rec['sections']['status']['text'] == '?? brand_new.py\n'
    assert rec['changes_observed'] is True                  # and NOT False
    assert rec['status'] == 'partial'


def test_a_partially_truncated_listing_keeps_its_recorded_paths_and_flags_the_gap(tmp_path):
    r = make_repo(tmp_path)
    ex = executor(r)
    base = whole_worktree_tree(r)
    for name in ('a.txt', 'b.txt', 'c.txt'):
        (r / name).write_text('n = 1\n')
    # `a.txt\0b.txt\0c.txt\0` is 18 bytes; 12 bytes keeps a.txt and b.txt only.
    rec = XC.capture(ex, base, wd=str(r), caps=dict(untracked_list_bytes=12))
    u = rec['sections']['untracked']
    assert u['state'] == 'captured'
    assert [e['path'] for e in u['paths']] == ['a.txt', 'b.txt']
    assert u['n_paths'] == 2
    assert u['n_paths_is_lower_bound'] is True
    assert u['list_truncated'] is True
    assert u['paths_complete'] is False
    assert u['partial_path_dropped'] is False               # 12 bytes ends exactly after b.txt's NUL
    assert u['incomplete_reason'] == (
        'the untracked listing is incomplete (byte-truncated at the 12-byte list cap): the recorded paths '
        'are a subset and n_paths is a lower bound, not an observation of how many exist')
    assert [f['section'] for f in rec['failures']] == ['untracked']
    assert rec['status'] == 'partial'                       # something was observed, but not all of it
    assert rec['changes_observed'] is True


# ---------------------------------------------------------------- executor and container contract

def test_dict_shaped_executor_results_and_timeout_return_codes_are_classified(tmp_path):
    def ex_timeout_info(cmd):
        return dict(returncode=-1, output='', exception_info='An error occurred: Command timed out after 60 s')
    rec = XC.capture(ex_timeout_info, '3' * 40, wd='/testbed')
    assert rec['status'] == 'timeout'
    assert states(rec) == {'tree': 'timeout', 'status': 'timeout', 'diff': 'timeout', 'untracked': 'timeout'}
    assert [c['state'] for c in rec['commands']] == ['timeout'] * 4
    assert 'error' not in rec['commands'][0]                # a reported container timeout, not a contract error

    def ex_124(cmd):
        return 124, ''
    rec = XC.capture(ex_124, '3' * 40, wd='/testbed')
    assert rec['status'] == 'timeout'
    assert rec['commands'][0]['returncode'] == 124

    def ex_other(cmd):
        return dict(returncode=-1, output='boom', exception_info='An error occurred: no such container')
    rec = XC.capture(ex_other, '3' * 40, wd='/testbed')
    assert rec['status'] == 'failed'
    assert rec['commands'][0]['output_tail'] == 'boom'
    assert rec['commands'][0]['returncode'] == -1
    assert 'error' not in rec['commands'][0]


@pytest.mark.parametrize('result,shape', [((0, 'out', 'extra'), 'tuple'), ('just a string', 'str'),
                                          (None, 'NoneType'), (0, 'int'), ([], 'list')])
def test_an_executor_result_the_module_cannot_parse_is_named_as_a_contract_failure(result, shape):
    def ex(cmd):
        return result
    rec = XC.capture(ex, '4' * 40, wd='/testbed')
    assert rec['status'] == 'failed'
    assert states(rec) == {'tree': 'failed', 'status': 'failed', 'diff': 'failed', 'untracked': 'failed'}
    assert rec['commands'][0]['error'] == (
        'injected executor returned %s, not (returncode, output) or a '
        "{'returncode','output'} mapping" % shape)
    assert rec['commands'][0]['returncode'] is None


def test_one_line_of_container_noise_does_not_demote_a_successful_capture(tmp_path):
    r = make_repo(tmp_path)
    real = executor(r)
    base = whole_worktree_tree(r)
    (r / 'new_file.py').write_text('n = 1\n')

    def ex(cmd):
        rc, out = real(cmd)
        return rc, 'warning: core.fsmonitor is unset\n' + out
    rec = XC.capture(ex, base, exit_status='Submitted', wd=str(r))
    assert states(rec) == {'tree': 'captured', 'status': 'captured', 'diff': 'captured',
                           'untracked': 'captured'}
    assert rec['status'] == 'changed'
    assert rec['sections']['status']['text'] == '?? new_file.py\n'
    assert rec['sections']['status']['container_preamble'] == 'warning: core.fsmonitor is unset\n'
    assert rec['sections']['untracked']['container_preamble'] == 'warning: core.fsmonitor is unset\n'
    assert [e['path'] for e in rec['sections']['untracked']['paths']] == ['new_file.py']
    assert rec['sections']['untracked']['paths'][0]['sha256'] == N_EQ_1_SHA
    assert rec['failures'] == []


def test_output_without_the_bound_header_is_a_failure_not_an_empty_observation():
    def ex(cmd):
        if 'write-tree' in cmd:
            return 0, '5' * 40 + '\n'
        return 0, 'no header here at all\n'
    rec = XC.capture(ex, '5' * 40, wd='/testbed')
    assert states(rec) == {'tree': 'captured', 'status': 'failed', 'diff': 'failed', 'untracked': 'failed'}
    assert rec['sections']['status']['reason'] == 'status produced no parsable bound header'
    assert rec['sections']['status']['text'] is None
    assert rec['sections']['untracked']['reason'] == 'untracked listing produced no parsable bound header'
    assert rec['status'] == 'partial'
    assert rec['changes_observed'] is None


def test_a_body_that_disagrees_with_its_own_byte_count_is_not_a_clean_capture(tmp_path):
    """The recorded text must be the observation: a failed body read may never pass as captured."""
    r = make_repo(tmp_path)
    real = executor(r)
    base = whole_worktree_tree(r)
    (r / 'mod.py').write_text('x = 2\n')

    def ex(cmd):
        rc, out = real(cmd)
        if 'git status' in cmd:
            header, _, _body = out.partition('\n')
            return rc, header + '\nhead: illegal byte count -- -1'
        return rc, out
    rec = XC.capture(ex, base, exit_status='Submitted', wd=str(r))
    status = rec['sections']['status']
    assert status['state'] == 'failed'
    assert status['text'] is None
    assert status['full_bytes'] is None
    assert status['sha256'] is None
    assert status['reason'] == ('status body is not consistent with its own bound header: recorded body is '
                               '30 bytes but the container reported 10 full bytes; the recorded text is '
                               'not the observation')
    assert status['full_bytes_reported'] == 10
    assert [f['section'] for f in rec['failures']] == ['status']
    assert rec['status'] == 'partial'
    assert rec['changes_observed'] is True                  # the diff still observed the modification


def test_the_command_log_cap_drops_entries_but_keeps_the_count(tmp_path):
    r = make_repo(tmp_path)
    ex = executor(r)
    base = whole_worktree_tree(r)
    for name in ('a1.txt', 'a2.txt', 'a3.txt', 'a4.txt', 'a5.txt', 'a6.txt'):
        (r / name).write_text('n = 1\n')
    rec = XC.capture(ex, base, wd=str(r), caps=dict(command_log=2))
    assert labels(rec) == ['tree', 'status']
    assert rec['dropped_log_entries'] == 8                  # 4 sections + 6 per-file reads = 10 commands
    assert rec['caps']['command_log'] == 2
    assert rec['sections']['untracked']['n_paths'] == 6     # the evidence itself is unaffected
    assert rec['sections']['untracked']['n_with_content'] == 6
    assert rec['status'] == 'changed'


# ---------------------------------------------------------------- endpoint and bounds

def test_the_diagnostic_is_never_written_to_submission_diff(tmp_path):
    r = make_repo(tmp_path)
    ex = executor(r)
    out = tmp_path / 'run'
    out.mkdir()
    (out / 'submission.diff').write_text('')                       # the frozen endpoint file, empty as in yaml-v1
    (r / 'edit.py').write_text('n = 1\n')
    rec = XC.capture_exit_diagnostic(ex, whole_worktree_tree(r), exit_status='LimitsExceeded', out_dir=out,
                                     wd=str(r))
    assert XC.OUTPUT_NAME == 'exit_diagnostic.json'
    assert rec['write'] == dict(state='written', file='exit_diagnostic.json')
    assert sorted(p.name for p in out.iterdir()) == ['exit_diagnostic.json', 'submission.diff']
    assert (out / 'submission.diff').read_text() == ''              # endpoint bytes unchanged
    # this machine's filesystem is case-insensitive, so an uppercase spelling would occupy the frozen
    # endpoint file itself: every spelling must be refused, and nothing new may appear in the directory
    for name in ('submission.diff', 'SUBMISSION.DIFF', 'Submission.Diff', 'anything.diff', 'ANYTHING.DIFF',
                 'submission.patch', 'SUBMISSION.PATCH', 'anything.patch'):
        with pytest.raises(ValueError):
            XC.write_diagnostic(out / name, rec)
    assert (out / 'submission.diff').read_text() == ''
    assert sorted(p.name for p in out.iterdir()) == ['exit_diagnostic.json', 'submission.diff']
    written = json.loads((out / 'exit_diagnostic.json').read_text())
    assert written['endpoint'] == dict(writes_submission_diff=False, marks_submitted=False, graded=False,
                                       changes_eligibility=False, changes_endpoint_bytes=False,
                                       output_file='exit_diagnostic.json')
    assert written['write'] == dict(state='attempted', file='exit_diagnostic.json')
    assert 'submission' not in written
    assert 'grade' not in written
    # the workspace evidence lives here, and only here
    assert [e['path'] for e in written['sections']['untracked']['paths']] == ['edit.py']
    assert written['sections']['untracked']['paths'][0]['content'] == 'n = 1\n'
    assert written['sections']['untracked']['paths'][0]['sha256'] == N_EQ_1_SHA


def test_a_nonexistent_out_dir_is_refused_rather_than_written_as_a_file(tmp_path):
    r = make_repo(tmp_path)
    ex = executor(r)
    missing = tmp_path / 'run8_does_not_exist'
    rec = XC.capture_exit_diagnostic(ex, whole_worktree_tree(r), exit_status='Submitted', out_dir=missing,
                                     wd=str(r))
    assert rec['write']['state'] == 'refused_missing_out_dir'
    assert rec['write']['file'] is None
    assert not missing.exists()                                     # no file named after the intended directory
    assert rec['status'] == 'no_change'                             # the capture itself still completed


def test_capture_output_is_write_once_and_a_second_write_refuses(tmp_path):
    r = make_repo(tmp_path)
    ex = executor(r)
    out = tmp_path / 'run'
    out.mkdir()
    base = whole_worktree_tree(r)
    first = XC.capture_exit_diagnostic(ex, base, exit_status='Submitted', out_dir=out, wd=str(r))
    assert first['write']['state'] == 'written'
    body = (out / 'exit_diagnostic.json').read_text()
    (r / 'late.py').write_text('late = 1\n')
    second = XC.capture_exit_diagnostic(ex, base, exit_status='Submitted', out_dir=out, wd=str(r))
    assert second['write']['state'] == 'refused_existing'
    assert second['status'] == 'changed'                            # the second capture still observed the change
    assert (out / 'exit_diagnostic.json').read_text() == body       # the first record is never overwritten
    with pytest.raises(FileExistsError):
        XC.write_diagnostic(out, second)
    assert (out / 'exit_diagnostic.json').read_text() == body
    assert XC.capture_exit_diagnostic(ex, base, out_dir=None, wd=str(r))['write'] == dict(state='not_requested',
                                                                                          file=None)


def test_every_exit_kind_is_captured_and_none_is_marked_submitted_or_graded(tmp_path):
    r = make_repo(tmp_path)
    ex = executor(r)
    base = whole_worktree_tree(r)
    (r / 'edit.py').write_text('n = 1\n')
    final = whole_worktree_tree(r, 'independent-index-final')
    for exit_status in ('Submitted', 'LimitsExceeded', 'ContextWindowExceeded', 'EpisodeDeadline', 'RuntimeError'):
        rec = XC.capture(ex, base, exit_status=exit_status, wd=str(r))
        assert rec['exit_status'] == exit_status
        assert rec['status'] == 'changed'
        assert rec['request'] == 'DTR-REQ-005'
        assert rec['binding'] == 'xc1'
        assert rec['sections']['tree']['sha'] == final
        assert rec['sections']['untracked']['n_paths'] == 1
        assert rec['endpoint'] == dict(writes_submission_diff=False, marks_submitted=False, graded=False,
                                       changes_eligibility=False, changes_endpoint_bytes=False,
                                       output_file='exit_diagnostic.json')


def test_all_bounds_and_exclusions_are_recorded_explicitly(tmp_path):
    r = make_repo(tmp_path)
    ex = executor(r)
    rec = XC.capture(ex, whole_worktree_tree(r), exit_status='LimitsExceeded', wd=str(r))
    assert rec['per_command_timeout_s'] == 60
    assert rec['total_budget_s'] == 300
    assert rec['caps'] == DECLARED_CAPS
    assert XC.DEFAULT_CAPS == DECLARED_CAPS
    assert rec['workdir'] == str(r)
    assert rec['dropped_log_entries'] == 0
    assert rec['exclusions'] == DECLARED_EXCLUSIONS               # all six, verbatim and in order
    assert len(rec['exclusions']) == 6
    assert rec['caps_error'] is None
    assert json.loads(json.dumps(rec)) == rec                     # the record is JSON-serializable as recorded


@pytest.mark.parametrize('caps,expected', [
    (['not-a-mapping'], 'declared caps ignored: not a mapping of cap name to a non-negative integer; '
                        'the defaults above apply'),
    ('262144', 'declared caps ignored: not a mapping of cap name to a non-negative integer; '
               'the defaults above apply'),
    (dict(diff_bytes='262144'), "cap 'diff_bytes'='262144' ignored (a non-negative integer is required); "
                                'the default 262144 applies'),
    (dict(untracked_paths=None), "cap 'untracked_paths'=None ignored (a non-negative integer is required); "
                                 'the default 64 applies'),
    (dict(untracked_list_bytes=-1), "cap 'untracked_list_bytes'=-1 ignored (a non-negative integer is "
                                    'required); the default 65536 applies'),
    (dict(diff_bytes=True), "cap 'diff_bytes'=True ignored (a non-negative integer is required); "
                            'the default 262144 applies'),
    (dict(nonsense=5), "unknown cap 'nonsense' ignored"),
])
def test_a_malformed_cap_declaration_is_named_and_the_declared_default_is_published(tmp_path, caps, expected):
    r = make_repo(tmp_path)
    ex = executor(r)
    rec = XC.capture(ex, whole_worktree_tree(r), exit_status='Submitted', wd=str(r), caps=caps)
    assert rec['caps_error'] == expected
    assert rec['caps'] == DECLARED_CAPS                           # the unusable value is never published
    assert rec['capture_error'] is None
    assert rec['status'] == 'no_change'
    assert rec['sections']['status']['state'] == 'no_change'
