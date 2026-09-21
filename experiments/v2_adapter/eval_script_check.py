"""DTR-REQ-002 fixture M03 (part 2): static check of a generated eval script's test-file reset commands.

Regression target: SWE-bench #518/#539, fixed in the selected commit f7bbbb2 (test_spec/python.py make_eval_script_list_py).
Before the fix a test patch that only ADDS files produced `git checkout <base_commit>` with no paths, resetting the whole
working tree and undoing image setup changes (e.g. tox.ini). After it, modified files get `git checkout <base> <files>`
and new files get `rm -f <files>`, both before applying the test patch and after the test output.

check_reset_commands inspects a command list (as the evaluator would generate it) WITHOUT executing anything:
  R1 no bare `git checkout <base_commit>` (a reset with no paths);
  R2 in EACH phase (before the patch application, after the end-of-output marker) the checkout paths equal exactly
     the patch's modified files;
  R3 in EACH phase the `rm -f` paths equal exactly the patch's new files;
  R4 exactly one application and one end marker, application first, and no reset inside the test run;
  unsupported reset/remove syntax is reported, never assumed safe (fail closed).
Repaired after lead review d1d9de6, whose two adversarial probes the first version accepted.
R1-R3 together mean no path outside the test patch's own files is reset, so unrelated setup changes are preserved.
Producing the real generated scripts for the 500 rows is M01 and needs the user's permission (not yet given).
"""
from __future__ import annotations
import re


def patch_files(test_patch):
    """(modified, new) file paths. Pass 1 (original grammar): each `--- SRC` / `+++ DST` pair; SRC /dev/null means new.
    Pass 2: `diff --git a/X b/Y` blocks with a `new file mode` line and NO ---/+++ lines are EMPTY new files, a shape
    found on real SWE-bench Verified patches (e.g. django__django-13837) that pass 1 cannot see."""
    modified, new = [], []
    lines = test_patch.splitlines()
    for i, line in enumerate(lines):
        if line.startswith('--- ') and i + 1 < len(lines) and lines[i + 1].startswith('+++ '):
            src, dst = line[4:].strip(), lines[i + 1][4:].strip()
            if src == '/dev/null':
                new.append(dst[2:] if dst.startswith('b/') else dst)
            else:
                modified.append(src[2:] if src.startswith('a/') else src)
    blocks, cur = [], None
    for line in lines:
        if line.startswith('diff --git '):
            cur = [line]; blocks.append(cur)
        elif cur is not None:
            cur.append(line)
    for b in blocks:
        if any(l.startswith('new file mode') for l in b) and not any(l.startswith('--- ') for l in b):
            head = b[0][len('diff --git '):]
            dst = head.split(' b/', 1)[1] if ' b/' in head else head.split(' ')[-1]
            if dst not in new:
                new.append(dst)
    return modified, new


def check_reset_commands(commands, test_patch, base_commit, apply_marker='git apply', end_marker='END_TEST_OUTPUT'):
    """Phase-aware, fail-closed check (repaired after lead review d1d9de6). Supported grammar only:
    `git checkout <base_commit> <paths...>`, `rm -f <paths...>`, one command starting with `git apply`, one command
    containing END_TEST_OUTPUT. Anything else that resets or removes files is reported as unsupported, not assumed safe."""
    modified, new = set(patch_files(test_patch)[0]), set(patch_files(test_patch)[1])
    problems = []
    applies = [i for i, c in enumerate(commands) if c.strip().startswith(apply_marker)]
    ends = [i for i, c in enumerate(commands) if end_marker in c]
    if len(applies) != 1 or len(ends) != 1:
        problems.append('R4 need exactly one patch application and one end-of-output marker (found %d, %d)'
                        % (len(applies), len(ends)))
        return problems
    apply_i, end_i = applies[0], ends[0]
    if apply_i > end_i:
        problems.append('R4 the test patch is applied after the end-of-output marker')
        return problems
    phases = {'before': commands[:apply_i], 'after': commands[end_i + 1:]}
    for i, cmd in enumerate(commands):
        c = cmd.strip()
        m = re.fullmatch(r'git checkout %s(.*)' % re.escape(base_commit), c)
        if m and not m.group(1).split():
            problems.append('R1 bare checkout resets the whole tree: %r' % cmd)
        elif c.startswith('git checkout') and not m:
            problems.append('UNSUPPORTED checkout syntax: %r' % cmd)
        elif re.match(r'(git (reset|clean|stash|restore)\b|rm(?! -f ))', c):
            problems.append('UNSUPPORTED reset/remove syntax: %r' % cmd)
        elif apply_i < i < end_i and (m or c.startswith('rm -f ')):
            problems.append('R4 reset inside the test run: %r' % cmd)
    for name, cmds in phases.items():
        checkout, removed = set(), set()
        for cmd in cmds:
            c = cmd.strip()
            m = re.fullmatch(r'git checkout %s(.*)' % re.escape(base_commit), c)
            if m:
                checkout |= set(m.group(1).split())
            elif c.startswith('rm -f '):
                removed |= set(c[len('rm -f '):].split())
        if checkout != modified:
            problems.append('R2 %s phase: checkout paths %s != modified files %s' % (name, sorted(checkout), sorted(modified)))
        if removed != new:
            problems.append('R3 %s phase: removed paths %s != new files %s' % (name, sorted(removed), sorted(new)))
    return problems
