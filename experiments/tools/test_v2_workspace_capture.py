"""Git fixtures for the workspace-capture binding v2 (lead 93588ab acceptance): modified, staged, added, deleted and
committed changes are all captured; the patch applied to a clean initial tree reproduces the final tree; failed
captures and existing outputs are rejected without overwriting. Runs real git in temporary repositories (no model,
no container)."""
import subprocess, sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_agent'))
import workspace_capture as W  # noqa: E402


def git(repo, *a, check=True):
    return subprocess.run(['git', '-C', str(repo), *a], check=check, capture_output=True, text=True)


def make_repo(tmp_path):
    r = tmp_path / 'testbed'; r.mkdir()
    git(r, 'init', '-q'); git(r, 'config', 'user.email', 'f@x'); git(r, 'config', 'user.name', 'f')
    (r / 'keep.py').write_text('a = 1\n'); (r / 'mod.py').write_text('x = 1\n'); (r / 'gone.py').write_text('bye\n')
    (r / 'staged.py').write_text('s = 1\n'); (r / 'committed.py').write_text('c = 1\n')
    (r / '.gitignore').write_text('*.pyc\n')
    git(r, 'add', '-A'); git(r, 'commit', '-qm', 'base')
    return r


def executor(repo):
    def ex(cmd):
        p = subprocess.run(['bash', '-c', cmd.replace(W.WORKDIR, str(repo))], capture_output=True, text=True)
        return p.returncode, p.stdout + p.stderr
    return ex


def test_all_change_kinds_are_captured_and_the_patch_reproduces_the_final_tree(tmp_path):
    r = make_repo(tmp_path)
    ex = executor(r)
    base = W.tree(ex)
    (r / 'mod.py').write_text('x = 2\n')                                   # modified (unstaged)
    (r / 'staged.py').write_text('s = 2\n'); git(r, 'add', 'staged.py')      # staged
    (r / 'new_file.py').write_text('n = 1\n')                              # added, untracked
    (r / 'gone.py').unlink()                                               # deleted
    (r / 'committed.py').write_text('c = 2\n'); git(r, 'commit', '-qam', 'agent commit')   # committed
    (r / 'junk.pyc').write_text('ignored')                                 # ignored: excluded by declaration
    out = W.patch(ex, base)
    p = out['patch']
    for name in ('mod.py', 'staged.py', 'new_file.py', 'gone.py', 'committed.py'):
        assert name in p, name
    assert 'junk.pyc' not in p and 'keep.py' not in p
    assert git(r, 'diff', '--cached', '--name-only').stdout.strip() == ''   # agent index untouched
    # apply to a clean initial tree and compare with the captured final tree
    clean = tmp_path / 'clean'
    git(tmp_path, 'clone', '-q', str(r), str(clean)); git(clean, 'checkout', '-q', 'HEAD~1')
    (tmp_path / 'p.diff').write_text(p)
    git(clean, 'apply', '--binary', str(tmp_path / 'p.diff'))
    assert W.tree(executor(clean)) == out['final_tree']


def test_no_changes_give_an_empty_patch_not_an_error(tmp_path):
    r = make_repo(tmp_path)
    ex = executor(r)
    base = W.tree(ex)
    assert W.patch(ex, base)['patch'] == ''


def test_capture_failures_are_errors_not_empty_submissions(tmp_path):
    r = make_repo(tmp_path)
    ex = executor(r)
    with pytest.raises(W.CaptureError):
        W.patch(ex, 'not-a-sha')
    with pytest.raises(W.CaptureError):
        W.patch(ex, '0' * 40)                                               # unknown base tree -> git diff fails
    with pytest.raises(W.CaptureError):
        W.tree(executor(tmp_path / 'missing'))                              # no repository


def test_run_ids_are_unique_and_outputs_are_never_overwritten(tmp_path):
    a, da = W.new_run_dir(tmp_path, 'x__y-1', 'large', 'wc2')
    b, db = W.new_run_dir(tmp_path, 'x__y-1', 'large', 'wc2')
    assert a != b and da.exists() and db.exists()
    W.write_once(da / 'submission.diff', 'one')
    with pytest.raises(FileExistsError):
        W.write_once(da / 'submission.diff', 'two')
    assert (da / 'submission.diff').read_text() == 'one'
    (tmp_path / 'taken').mkdir()
    with pytest.raises(FileExistsError):
        (tmp_path / 'taken').mkdir(parents=True, exist_ok=False)
