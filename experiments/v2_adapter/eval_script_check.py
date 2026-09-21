"""DTR-REQ-002 fixture M03 (part 2): static check of a generated eval script's test-file reset commands.

Regression target: SWE-bench #518/#539, fixed in the selected commit f7bbbb2 (test_spec/python.py make_eval_script_list_py).
Before the fix a test patch that only ADDS files produced `git checkout <base_commit>` with no paths, resetting the whole
working tree and undoing image setup changes (e.g. tox.ini). After it, modified files get `git checkout <base> <files>`
and new files get `rm -f <files>`, both before applying the test patch and after the test output.

check_reset_commands inspects a command list (as the evaluator would generate it) WITHOUT executing anything:
  R1 no bare `git checkout <base_commit>` (a reset with no paths);
  R2 every checkout path is a modified file of the test patch, and all modified files are covered;
  R3 every new file of the test patch is removed with `rm -f`, and no other path is removed;
  R4 resets occur both before the patch application and after the end-of-output marker.
R1-R3 together mean no path outside the test patch's own files is reset, so unrelated setup changes are preserved.
Producing the real generated scripts for the 500 rows is M01 and needs the user's permission (not yet given).
"""
from __future__ import annotations
import re


def patch_files(test_patch):
    """(modified, new) file paths from unified-diff headers; new files have source /dev/null."""
    modified, new = [], []
    lines = test_patch.splitlines()
    for i, line in enumerate(lines):
        if line.startswith('--- ') and i + 1 < len(lines) and lines[i + 1].startswith('+++ '):
            src, dst = line[4:].strip(), lines[i + 1][4:].strip()
            if src == '/dev/null':
                new.append(dst[2:] if dst.startswith('b/') else dst)
            else:
                modified.append(src[2:] if src.startswith('a/') else src)
    return modified, new


def check_reset_commands(commands, test_patch, base_commit, apply_marker='git apply', end_marker='END_TEST_OUTPUT'):
    modified, new = patch_files(test_patch)
    problems = []
    checkout_paths, removed, reset_idx = [], [], []
    for i, cmd in enumerate(commands):
        m = re.fullmatch(r'git checkout %s(.*)' % re.escape(base_commit), cmd.strip())
        if m:
            paths = m.group(1).split()
            if not paths:
                problems.append('R1 bare checkout resets the whole tree: %r' % cmd)
            checkout_paths += paths; reset_idx.append(i)
        elif cmd.strip().startswith('rm -f '):
            removed += cmd.strip()[len('rm -f '):].split(); reset_idx.append(i)
    if set(checkout_paths) - set(modified) or set(modified) - set(checkout_paths):
        problems.append('R2 checkout paths %s differ from modified files %s' % (sorted(set(checkout_paths)), sorted(modified)))
    if set(removed) != set(new):
        problems.append('R3 removed paths %s differ from new files %s' % (sorted(set(removed)), sorted(new)))
    apply_i = next((i for i, c in enumerate(commands) if c.startswith(apply_marker)), None)
    end_i = next((i for i, c in enumerate(commands) if end_marker in c), None)
    if (modified or new) and (apply_i is None or end_i is None or not any(i < apply_i for i in reset_idx)
                              or not any(i > end_i for i in reset_idx)):
        problems.append('R4 resets must occur before the patch is applied and after the test output')
    return problems
