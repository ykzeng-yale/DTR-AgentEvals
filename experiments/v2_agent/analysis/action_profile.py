"""DTR-REQ-002 / REQ-004 descriptive analysis: ACTION PROFILE of the v2_agent pilot episodes.

Read-only, offline. Reads the committed episode artifacts of BOTH pilot cohorts
(legacy = results/v2_agent/pilot_20260922, yaml-v1 = results/v2_agent/pilot_20260922_yaml_v1)
and classifies EVERY issued command into exactly one command family, using a fixed rule set
applied in a fixed priority order. Nothing is run, nothing under results/ is modified;
the single output file is opened with mode 'x' (write-once).

Scope note (worker, not scientific lead): this file reports COUNTS and CLASSIFICATIONS of what
the agents issued. It makes no causal claim, no efficacy claim and no recommendation about study
design. Where a mechanism is ambiguous the artifact says so in `limitations`.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RESULTS = REPO / 'results' / 'v2_agent'
COHORTS = OrderedDict([('legacy', 'pilot_20260922'), ('yaml-v1', 'pilot_20260922_yaml_v1')])
OUT_DIR = RESULTS / 'analysis_20260922'
OUT_PATH = OUT_DIR / 'action_profile.json'

SUBMIT_SENTINEL = 'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT'
INSTANCE_TEMPLATE_MARKER = '\n\nYou can execute bash commands and edit files'
INSTANCE_TEMPLATE_PREFIX = 'Please solve this issue: '
CONTAINER_CWD = '/testbed'

# ----------------------------------------------------------------------------------------------
# Command-family rules.
#
# CS ("command start") anchors a token to a shell command position: start of string, a newline, or
# right after one of ; & | ( -- which also covers `&&` and `||` because the class matches the second
# character of the operator -- optionally followed by `sudo ` and/or VAR=value prefixes.
# ----------------------------------------------------------------------------------------------
CS = r"(?:^|[\n;&|(])\s*(?:sudo\s+)?(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"

FAMILY_RULES = OrderedDict([
    ('submit', [
        ('submit.sentinel', re.escape(SUBMIT_SENTINEL)),
    ]),
    ('edit', [
        ('edit.sed_in_place', CS + r"sed\s+(?:-\S+\s+)*-i\b"),
        ('edit.patch', CS + r"patch\b"),
        ('edit.git_apply', r"\bgit\s+apply\b"),
        ('edit.applypatch', r"\bapplypatch\b"),
        ('edit.tee', CS + r"tee\b"),
        ('edit.cat_redirect_or_heredoc_to_file', CS + r"cat\s+[^\n;&|]*?>{1,2}\s*\S+"),
        ('edit.python_stdin_heredoc', r"python[0-9.]*\s+-\s*<<"),
        ('edit.redirect_into_source_file',
         r">{1,2}\s*\S*\.(?:py|rst|txt|cfg|ini|toml|ya?ml|xml|json|md|c|h|cpp|cc|js|ts)\b"),
    ]),
    ('create_file', [
        ('create_file.touch_or_mkdir', CS + r"(?:touch|mkdir)\b"),
        ('create_file.generic_redirect', r">{1,2}\s*(?!/dev/)(?!&)\S+"),
    ]),
    ('run_tests', [
        ('run_tests.runner_at_command_position', CS + r"(?:python[0-9.]*\s+-m\s+)?(?:pytest|py\.test|nosetests|tox)\b"),
        ('run_tests.python_m_unittest', r"python[0-9.]*\s+-m\s+unittest\b"),
        ('run_tests.runtests_script', r"(?:^|[\s;&|(/])runtests(?:\.py)?\b"),
        ('run_tests.manage_py_test', r"\bmanage\.py\s+test\b"),
    ]),
    ('inspect', [
        ('inspect.reader_at_command_position',
         CS + r"(?:cat|head|tail|less|more|grep|egrep|fgrep|rg|ag|find|ls|pwd|wc|nl|which|whereis|"
              r"locate|file|stat|du|tree|realpath|readlink|env|printenv)\b"),
        ('inspect.sed_print', CS + r"sed\s+-n\b"),
        ('inspect.echo_variable', CS + r"echo\s+\$"),
        ('inspect.read_only_package_query', r"\b(?:pip[0-9.]*\s+(?:show|list|freeze)|conda\s+list)\b"),
    ]),
    ('python_eval', [
        ('python_eval.dash_c', r"python[0-9.]*\s+-c\b"),
        ('python_eval.run_script', CS + r"(?:\./)?python[0-9.]*\s+(?!-m\b)\S*\.py\b"),
        ('python_eval.bare_interpreter', CS + r"python[0-9.]*\s*(?:$|\n)"),
    ]),
    ('vcs', [
        ('vcs.git', CS + r"git\b"),
    ]),
    ('install_env', [
        ('install_env.pip', r"\bpip[0-9.]*\s+(?:install|uninstall|download)\b"),
        ('install_env.conda', r"\bconda\s+(?:install|create|remove|env|update)\b"),
        ('install_env.system_pkg', r"\b(?:apt-get|apt|yum|brew)\s+install\b|\beasy_install\b"),
    ]),
])
FAMILY_PRIORITY = list(FAMILY_RULES) + ['other']
COMPILED = OrderedDict((fam, [(rid, re.compile(rx)) for rid, rx in rules]) for fam, rules in FAMILY_RULES.items())

# auxiliary (NOT a family): interactive editors are an attempted edit but match none of the
# edit-family rules above, which are the closed list fixed for this analysis.
INTERACTIVE_EDITOR = re.compile(CS + r"(?:vim?|nano|emacs|ed)\s+\S")

HEREDOC_OPEN = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_]\w*)\1")
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")


def mask_quoted(text: str) -> str:
    """Replace the CONTENT of quoted spans with 'X' of equal length, keeping offsets and the quotes.

    Command words stay matchable (`sed -i 'X...X' f.py`, `python -c "X...X"`), while shell metacharacters
    that merely appear inside a quoted literal (e.g. the `>` of `grep "    <plugin>"`) can no longer be
    mistaken for a redirection or a command separator.
    """
    return QUOTED.sub(lambda m: m.group(0)[0] + 'X' * (len(m.group(0)) - 2) + m.group(0)[-1], text)


def strip_heredoc_bodies(cmd: str):
    """Remove here-document BODIES so that body lines are never matched as shell commands.

    The opener line (e.g. `cat <<'EOF' > f.py`) is kept, so edit-family detection is unaffected.
    Returns (stripped_command, n_heredocs_stripped, n_body_lines_stripped).
    """
    out, n_doc, n_lines, lines, i = [], 0, 0, cmd.split('\n'), 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = HEREDOC_OPEN.search(line)
        i += 1
        if not m:
            continue
        n_doc += 1
        delim = m.group(2)
        while i < len(lines) and lines[i].strip() != delim:
            n_lines += 1
            i += 1
        if i < len(lines):
            i += 1  # drop the terminator line as well
    return '\n'.join(out), n_doc, n_lines


def classify(cmd: str):
    """Return (primary_family, matched_families, matched_rule_ids) for one issued command."""
    text, n_doc, n_lines = strip_heredoc_bodies(cmd)
    text = mask_quoted(text)
    matched_rules, matched_families = [], []
    for fam, rules in COMPILED.items():
        hit = [rid for rid, rx in rules if rx.search(text)]
        if hit:
            matched_families.append(fam)
            matched_rules.extend(hit)
    primary = matched_families[0] if matched_families else 'other'
    return dict(primary=primary, families=matched_families, rules=matched_rules,
                interactive_editor=bool(INTERACTIVE_EDITOR.search(text)),
                heredocs=n_doc, heredoc_body_lines=n_lines, scanned_text=text)


# ----------------------------------------------------------------------------------------------
# Write-target extraction for edit-family commands (coarse, textual).
# ----------------------------------------------------------------------------------------------
SEG_SPLIT = re.compile(r"&&|\|\||[;|\n]")
REDIRECT = re.compile(r">{1,2}\s*(?!/dev/)(?!&)(\S+)")


def edit_write_targets(cmd: str):
    """Textual write targets of an edit-family command.

    Segment splitting and pattern location run on the QUOTE-MASKED text (so separators and `>` inside a
    quoted literal are ignored); the token itself is sliced from the unmasked text at the same offsets,
    because masking preserves length and offsets exactly.
    """
    raw, _, _ = strip_heredoc_bodies(cmd)
    masked = mask_quoted(raw)
    bounds, prev = [], 0
    for m in SEG_SPLIT.finditer(masked):
        bounds.append((prev, m.start()))
        prev = m.end()
    bounds.append((prev, len(masked)))
    targets = []
    for a, b in bounds:
        seg_m, seg_r = masked[a:b], raw[a:b]
        off = len(seg_m) - len(seg_m.lstrip())
        sm, sr = seg_m.strip(), seg_r[off:off + len(seg_m.strip())]
        if re.match(r"^(?:sudo\s+)?sed\s+(?:-\S+\s+)*-i\b", sm):
            toks_m = list(re.finditer(r"\S+", sm))
            if toks_m:
                t = toks_m[-1]
                targets.append(sr[t.start():t.end()])
        m = re.match(r"^(?:sudo\s+)?tee\s+(?:-\S+\s+)*(\S+)", sm)
        if m:
            targets.append(sr[m.start(1):m.end(1)])
        for m in REDIRECT.finditer(sm):
            targets.append(sr[m.start(1):m.end(1)])
    seen, uniq = set(), []
    for t in targets:
        t = t.strip("'\"")
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def target_location_class(target: str, cmd: str) -> str:
    if '/path/to/' in target or '/path/to/' in cmd:
        return 'placeholder_path'
    if 'site-packages' in target or target.startswith('/opt/miniconda3'):
        return 'installed_package_outside_repo_tree'
    if 'git clone' in cmd:
        return 'freshly_cloned_copy_outside_base_tree'
    if target.startswith(CONTAINER_CWD + '/') or target == CONTAINER_CWD:
        return 'inside_testbed_absolute'
    if not target.startswith('/'):
        return 'relative_resolves_under_testbed'
    return 'other_absolute_path'


# ----------------------------------------------------------------------------------------------
# Candidate target-file derivation (see `method.target_path_derivation` in the artifact).
# ----------------------------------------------------------------------------------------------
SRC_EXT_RX = r"py|rst|txt|cfg|ini|toml|ya?ml|xml|md"
# A token boundary that refuses to start MID-path: the previous character may not be a word char,
# '.', '$', '/' or '-' (the last two would let a match begin inside `a/b.py` or after `pytest-`).
NOT_MID_PATH = r"(?<![\w.$/-])"
GITHUB_BLOB = re.compile(r"https?://github\.com/[^/\s]+/[^/\s]+/blob/[^/\s]+/([\w./+-]+\.(?:" + SRC_EXT_RX + r"))")
URL = re.compile(r"https?://\S+")
PATHLIKE = re.compile(NOT_MID_PATH + r"(/?(?:[\w.+-]+/)+[\w.+-]+\.(?:" + SRC_EXT_RX + r"))\b")
BARE_FILE = re.compile(NOT_MID_PATH + r"([\w+-]+\.(?:py|rst))\b")
SOURCE_TOKEN = re.compile(NOT_MID_PATH + r"(/?(?:[\w.+$-]+/)*[\w.+$-]+\.(?:py|rst))\b")
SOURCE_EXT = ('.py', '.rst', '.txt', '.cfg', '.ini', '.toml', '.yaml', '.yml', '.xml', '.md')


def repo_of(instance_id: str):
    owner, rest = instance_id.split('__', 1)
    return owner, re.sub(r'-\d+$', '', rest)


def derive_candidates(instance_id: str, problem_statement: str):
    owner, repo = repo_of(instance_id)
    pkgs = {repo, repo.replace('-', '_')}
    chan_a, chan_b = [], []
    # (a1) repo-relative path carried by a github blob URL, e.g. .../blob/<sha>/src/_pytest/logging.py
    chan_a.extend(GITHUB_BLOB.findall(problem_statement))
    # (a2) plain path / bare filename tokens, with URLs removed first so no URL fragment can leak in
    without_urls = URL.sub(' ', problem_statement)
    for tok in PATHLIKE.findall(without_urls):
        chan_a.append(re.sub(r'^\./', '', tok))
    chan_a.extend(BARE_FILE.findall(without_urls))
    dotted = re.compile(r"\b(" + '|'.join(re.escape(p) for p in sorted(pkgs)) + r")((?:\.[A-Za-z_]\w*)+)\b")
    for m in dotted.finditer(problem_statement):
        parts = [m.group(1)] + m.group(2).lstrip('.').split('.')
        tail = problem_statement[m.end():m.end() + 1]
        if tail == '(' and len(parts) > 1:
            parts = parts[:-1]                          # drop a called attribute, e.g. pkg.f()
        parts = [p for p in parts if p[:1].islower() or p[:1] == '_']
        if len(parts) >= 2:
            chan_b.append('/'.join(parts) + '.py')
    def uniq(xs):
        out = []
        for x in xs:
            if x not in out:
                out.append(x)
        return out
    return dict(owner=owner, repo=repo, packages_assumed=sorted(pkgs),
                channel_a_explicit_path_tokens=uniq(chan_a),
                channel_b_dotted_module_tokens=uniq(chan_b),
                candidates=uniq(chan_a + chan_b))


# ----------------------------------------------------------------------------------------------
# Trajectory walk.
# ----------------------------------------------------------------------------------------------
def parse_run_id(run_id: str):
    """instance_id itself contains '__', so parse from the END: <instance_id>__<backend>__<binding>__<tsZ>-<hex>."""
    seg = run_id.split('__')
    assert len(seg) >= 4, run_id
    stamp_seg = seg[-1]
    ts, _, hexid = stamp_seg.partition('-')
    return dict(instance_id='__'.join(seg[:-3]), backend=seg[-3], binding=seg[-2],
                run_timestamp_utc=ts, run_suffix=hexid)


def walk_episode(cohort: str, run_dir: Path):
    episode = json.loads((run_dir / 'episode.json').read_text())
    grade = json.loads((run_dir / 'grade.json').read_text())
    traj = json.loads((run_dir / 'trajectory.json').read_text())
    msgs = traj['messages']
    parsed = parse_run_id(run_dir.name)
    assert parsed['instance_id'] == episode['instance_id'], run_dir.name
    assert parsed['backend'] == episode['backend'], run_dir.name

    first_user = next(m for m in msgs if m.get('role') == 'user')['content']
    assert first_user.startswith(INSTANCE_TEMPLATE_PREFIX) and INSTANCE_TEMPLATE_MARKER in first_user
    problem = first_user.split(INSTANCE_TEMPLATE_MARKER)[0][len(INSTANCE_TEMPLATE_PREFIX):]

    # Model-call events, in order. A call either yields an assistant message (parsed to exactly one
    # action) or a format-error user message (the response carried != 1 action and mini-swe-agent
    # records only the error). A trailing call that raised before any message is not in the trajectory.
    calls, call_idx, n_format_errors = [], 0, 0
    for i, m in enumerate(msgs):
        role = m.get('role')
        extra = m.get('extra') or {}
        if role == 'assistant':
            call_idx += 1
            actions = extra.get('actions') or []
            nxt = msgs[i + 1] if i + 1 < len(msgs) else None
            obs = nxt if (nxt and nxt.get('role') == 'user' and 'returncode' in (nxt.get('extra') or {})) else None
            calls.append(dict(call_index=call_idx, kind='action',
                              commands=[a.get('command') for a in actions],
                              returncode=(obs.get('extra') or {}).get('returncode') if obs else None,
                              has_observation=obs is not None))
        elif role == 'user' and i > 0 and 'returncode' not in extra and m is not msgs[1]:
            # a user message that is neither the task prompt nor an observation == format-error turn
            call_idx += 1
            n_format_errors += 1
            calls.append(dict(call_index=call_idx, kind='format_error', commands=[],
                              returncode=None, has_observation=False))
    return episode, grade, traj, problem, calls, n_format_errors


def analyse_episode(cohort: str, run_dir: Path, inventory: Counter, inventory_family: dict):
    episode, grade, traj, problem, calls, n_format_errors = walk_episode(cohort, run_dir)
    parsed = parse_run_id(run_dir.name)
    derivation = derive_candidates(episode['instance_id'], problem)
    candidates = derivation['candidates']

    fam_primary, fam_any, rule_counts = Counter(), Counter(), Counter()
    loc_counts, write_targets = Counter(), []
    cmds = []
    n_interactive_editor = 0
    n_nonzero, n_with_obs = 0, 0
    matched_candidates = set()
    source_paths_mentioned = set()
    for call in calls:
        for cmd in call['commands']:
            c = classify(cmd)
            fam_primary[c['primary']] += 1
            for f in c['families']:
                fam_any[f] += 1
            for r in c['rules']:
                rule_counts[r] += 1
            n_interactive_editor += int(c['interactive_editor'])
            if c['primary'] == 'edit' or 'edit' in c['families']:
                for t in edit_write_targets(cmd):
                    cls = target_location_class(t, cmd)
                    loc_counts[cls] += 1
                    write_targets.append(dict(call_index=call['call_index'], target=t, location_class=cls))
            inventory[cmd] += 1
            inventory_family[cmd] = c['primary']
            for cand in candidates:
                if cand in cmd or cand.split('/')[-1] in cmd:
                    matched_candidates.add(cand)
            source_paths_mentioned.update(SOURCE_TOKEN.findall(cmd))
            cmds.append(dict(call_index=call['call_index'], primary=c['primary'], families=c['families'], command=cmd))
        if call['kind'] == 'action':
            if call['has_observation']:
                n_with_obs += 1
                if call['returncode'] not in (None, 0):
                    n_nonzero += 1

    def first_index(fam, mode):
        for c in cmds:
            if (c['primary'] == fam) if mode == 'primary' else (fam in c['families']):
                return c['call_index']
        return None

    n_cmds = len(cmds)
    inspect_primary = fam_primary.get('inspect', 0)
    chan_a = derivation['channel_a_explicit_path_tokens']
    chan_b = derivation['channel_b_dotted_module_tokens']
    if candidates:
        referenced = bool(matched_candidates)
        ref_status = 'candidate_derived'
    else:
        referenced = None
        ref_status = 'no_candidate_derivable_from_problem_statement'
    ref_a = bool(matched_candidates & set(chan_a)) if chan_a else None
    ref_b = bool(matched_candidates & set(chan_b)) if chan_b else None

    return dict(
        cohort=cohort,
        run_id=run_dir.name,
        run_dir=str(run_dir.relative_to(REPO)),
        instance_id=episode['instance_id'],
        backend=episode['backend'],
        binding=parsed['binding'],
        run_timestamp_utc=parsed['run_timestamp_utc'],
        exit_status=episode['exit_status'],
        grade_classification=grade.get('classification'),
        submission_bytes=episode['submission_bytes'],
        final_tree_recorded=episode.get('final_tree') is not None,
        n_model_calls=episode['n_model_calls'],
        n_calls_with_recorded_command=n_cmds,
        n_format_error_calls=n_format_errors,
        n_calls_without_recorded_message=episode['n_model_calls'] - len(calls),
        family_counts_primary={f: fam_primary.get(f, 0) for f in FAMILY_PRIORITY},
        family_counts_any_match={f: fam_any.get(f, 0) for f in FAMILY_PRIORITY if f != 'other'},
        rule_hit_counts=dict(sorted(rule_counts.items())),
        any_edit_primary=fam_primary.get('edit', 0) > 0,
        first_edit_call_index_primary=first_index('edit', 'primary'),
        any_edit_rule_matched_anywhere=fam_any.get('edit', 0) > 0,
        first_edit_rule_call_index=first_index('edit', 'any'),
        any_run_tests_primary=fam_primary.get('run_tests', 0) > 0,
        first_run_tests_call_index_primary=first_index('run_tests', 'primary'),
        any_run_tests_rule_matched_anywhere=fam_any.get('run_tests', 0) > 0,
        first_run_tests_rule_call_index=first_index('run_tests', 'any'),
        any_submit_sentinel=fam_primary.get('submit', 0) > 0,
        first_submit_call_index=first_index('submit', 'any'),
        interactive_editor_commands=n_interactive_editor,
        edit_write_target_location_counts=dict(sorted(loc_counts.items())),
        edit_write_targets=write_targets,
        n_commands_with_observation=n_with_obs,
        n_commands_without_observation=n_cmds - n_with_obs,
        n_nonzero_returncode=n_nonzero,
        nonzero_returncode_fraction=(round(n_nonzero / n_with_obs, 4) if n_with_obs else None),
        inspect_fraction_of_recorded_commands=(round(inspect_primary / n_cmds, 4) if n_cmds else None),
        inspect_fraction_of_model_calls=(round(inspect_primary / episode['n_model_calls'], 4)
                                         if episode['n_model_calls'] else None),
        distinct_commands=len(set(c['command'] for c in cmds)),
        max_identical_command_repeats=(max(Counter(c['command'] for c in cmds).values()) if cmds else 0),
        target_path_reference=dict(
            status=ref_status,
            referenced=referenced,
            referenced_channel_a=ref_a,
            referenced_channel_b=ref_b,
            candidates=candidates,
            channel_a_explicit_path_tokens=chan_a,
            channel_b_dotted_module_tokens=chan_b,
            packages_assumed=derivation['packages_assumed'],
            matched_candidates=sorted(matched_candidates),
            n_commands_mentioning_any_candidate=sum(
                1 for c in cmds if any(cand in c['command'] or cand.split('/')[-1] in c['command']
                                       for cand in candidates)),
        ),
        source_paths_mentioned_in_commands=sorted(source_paths_mentioned),
        n_source_paths_mentioned_in_commands=len(source_paths_mentioned),
        commands=cmds,
    )


def aggregate(eps, label, key):
    groups = OrderedDict()
    for e in eps:
        groups.setdefault(key(e), []).append(e)
    out = OrderedDict()
    for g, rows in groups.items():
        fam = Counter()
        fam_any = Counter()
        loc = Counter()
        for r in rows:
            fam.update(r['family_counts_primary'])
            fam_any.update(r['family_counts_any_match'])
            loc.update(r['edit_write_target_location_counts'])
        n_cmds = sum(r['n_calls_with_recorded_command'] for r in rows)
        ref = [r for r in rows if r['target_path_reference']['referenced'] is not None]
        out[g] = dict(
            n_episodes=len(rows),
            n_model_calls=sum(r['n_model_calls'] for r in rows),
            n_recorded_commands=n_cmds,
            n_format_error_calls=sum(r['n_format_error_calls'] for r in rows),
            family_counts_primary={f: fam.get(f, 0) for f in FAMILY_PRIORITY},
            family_share_primary={f: (round(fam.get(f, 0) / n_cmds, 4) if n_cmds else None)
                                  for f in FAMILY_PRIORITY},
            family_counts_any_match={f: fam_any.get(f, 0) for f in FAMILY_PRIORITY if f != 'other'},
            episodes_with_any_edit_primary=sum(1 for r in rows if r['any_edit_primary']),
            episodes_with_any_edit_rule=sum(1 for r in rows if r['any_edit_rule_matched_anywhere']),
            episodes_with_any_run_tests_primary=sum(1 for r in rows if r['any_run_tests_primary']),
            episodes_with_any_run_tests_rule=sum(1 for r in rows if r['any_run_tests_rule_matched_anywhere']),
            episodes_with_submit_sentinel=sum(1 for r in rows if r['any_submit_sentinel']),
            episodes_with_interactive_editor=sum(1 for r in rows if r['interactive_editor_commands'] > 0),
            edit_write_target_location_counts=dict(sorted(loc.items())),
            n_nonzero_returncode=sum(r['n_nonzero_returncode'] for r in rows),
            n_commands_with_observation=sum(r['n_commands_with_observation'] for r in rows),
            nonzero_returncode_fraction=(
                round(sum(r['n_nonzero_returncode'] for r in rows)
                      / sum(r['n_commands_with_observation'] for r in rows), 4)
                if sum(r['n_commands_with_observation'] for r in rows) else None),
            inspect_fraction_of_recorded_commands=(round(fam.get('inspect', 0) / n_cmds, 4) if n_cmds else None),
            episodes_with_target_reference_defined=len(ref),
            episodes_referencing_candidate_target=sum(1 for r in ref if r['target_path_reference']['referenced']),
            episodes_mentioning_any_source_path=sum(
                1 for r in rows if r['n_source_paths_mentioned_in_commands'] > 0),
            distinct_source_paths_mentioned=sorted({p for r in rows
                                                    for p in r['source_paths_mentioned_in_commands']}),
        )
    return dict(grouped_by=label, groups=out)


def main():
    episodes, inventory, inventory_family = [], Counter(), {}
    for cohort, sub in COHORTS.items():
        base = RESULTS / sub
        run_dirs = sorted(d for d in base.iterdir() if d.is_dir() and (d / 'episode.json').is_file())
        assert len(run_dirs) == 16, (cohort, len(run_dirs))
        for d in run_dirs:
            episodes.append(analyse_episode(cohort, d, inventory, inventory_family))
    assert len(episodes) == 32

    reports = {}
    for cohort, rel in [('legacy', 'pilot_20260922/report_block1_final.json'),
                        ('yaml-v1', 'pilot_20260922_yaml_v1/report_yaml_v1_block1_final.json')]:
        p = RESULTS / rel
        reports[cohort] = dict(path=str(p.relative_to(REPO)), exists=p.is_file())

    total_cmds = sum(e['n_calls_with_recorded_command'] for e in episodes)
    artifact = OrderedDict()
    artifact['artifact'] = dict(
        name='action_profile',
        request='DTR-REQ-002 / DTR-REQ-004 (descriptive, post-hoc)',
        dimension='what the agents actually attempted: command-family profile of every issued command',
        produced_by='experiments/v2_agent/analysis/action_profile.py',
        analysis_date_utc='2026-09-22',
        read_only=True,
        inputs=dict(
            cohorts={c: 'results/v2_agent/' + s for c, s in COHORTS.items()},
            per_episode_files=['episode.json', 'grade.json', 'trajectory.json'],
            committed_reports=reports,
        ),
        n_cohorts=2, n_episodes=len(episodes),
        n_model_calls=sum(e['n_model_calls'] for e in episodes),
        n_recorded_commands=total_cmds,
    )
    artifact['method'] = dict(
        command_source=(
            "Every command is taken from trajectory.json messages with role 'assistant', field "
            "extra.actions[*].command. Only message CONTENT is scanned; info.config (which contains the "
            "prompt templates and their markup, e.g. <format_example>/<returncode>/<output>) is never "
            "scanned for commands. Across all 32 episodes every assistant message carried exactly one action."),
        call_index_definition=(
            "1-based ordinal over model-call events in trajectory order. A call event is (a) an assistant "
            "message, or (b) a format-error user message (the harness rejects a response carrying != 1 action "
            "and records only the error message, so that call has no recorded command). A call that raised "
            "before any message was appended (e.g. ContextWindowExceededError) appears in episode.n_model_calls "
            "but not in the trajectory; it is counted in n_calls_without_recorded_message."),
        family_priority_order=FAMILY_PRIORITY,
        family_assignment=(
            "Each command is tested against every family's rules; the PRIMARY family is the first family in "
            "family_priority_order with a matching rule ('other' if none match). Because many commands are "
            "compound (`a && b && c`), family_counts_any_match additionally reports, per family, how many "
            "commands matched that family's rules at all, so co-occurrence is visible and nothing is hidden by "
            "the priority rule."),
        family_rules={fam: {rid: rx for rid, rx in rules} for fam, rules in FAMILY_RULES.items()},
        command_start_anchor=dict(regex=CS, meaning=(
            "start of string, newline, or immediately after ; & | ( (which also covers && and ||), "
            "optionally followed by `sudo ` and/or VAR=value assignments")),
        heredoc_handling=(
            "Here-document BODIES are removed before matching so that body lines are never mistaken for shell "
            "commands; the opener line is kept, so `cat <<'EOF' > f.py` still matches the edit family."),
        auxiliary_counters=dict(interactive_editor_commands=(
            "commands invoking vi/vim/nano/emacs/ed on a file. These are attempted edits but match none of the "
            "closed edit-family rule list fixed for this analysis, so they are classified 'other' and counted "
            "separately rather than folded into 'edit'.")),
        returncode_rule=(
            "A command's returncode is taken from the immediately following user message's extra.returncode. "
            "Commands with no following observation (the episode ended first) are counted in "
            "n_commands_without_observation and excluded from the nonzero denominator."),
        inspect_fraction_rule=(
            "inspect_fraction_of_recorded_commands = primary-family 'inspect' count / number of calls with a "
            "recorded command. inspect_fraction_of_model_calls uses episode.n_model_calls as denominator "
            "(it counts format-error and errored calls in the denominator)."),
        target_path_derivation=dict(
            rule=(
                "The repo is parsed from instance_id as owner__repo-<number> (run_id is parsed from the END: "
                "<instance_id>__<backend>__<binding>__<timestampZ>-<hex>, since instance_id itself contains '__'). "
                "The problem statement is the first user message sliced between the fixed template prefix "
                "'Please solve this issue: ' and the fixed marker '\\n\\nYou can execute bash commands and edit "
                "files'. Two channels then produce candidate target paths. "
                "Channel A: explicit path-like tokens in the problem statement -- a slash path ending in a source "
                "extension (a github /blob/<ref>/ URL prefix is stripped), or a bare <name>.py / <name>.rst token. "
                "Channel B: dotted module tokens whose head equals the repo name (or repo name with '-'->'_'), "
                "mapped to a/b/c.py; a trailing component immediately followed by '(' is dropped as a call, and "
                "CamelCase components are dropped. "
                "An episode 'referenced' a candidate if any issued command's text contains the candidate path or "
                "its basename."),
            limits=[
                "The channels are text heuristics over the ISSUE TEXT, not the task's gold patch. The gold patch "
                "file list is NOT present in the committed artifacts, so no ground-truth target file can be "
                "checked here and 'referenced' must be read as 'referenced a path named in the issue text'.",
                "For 5 of the 8 instances no candidate is derivable at all (the issue text names no file and no "
                "repo-rooted dotted module); those episodes report referenced=null, not false.",
                "Channel B cannot fire when the import package name differs from the repo name "
                "(scikit-learn -> sklearn is the case here), because no hand-written alias table is used.",
                "A candidate derived from the issue text need not be the file that must change: for "
                "sphinx-doc__sphinx-10323 the derived candidate index.rst is a reproduction fixture named in the "
                "bug report, not necessarily the module under repair.",
                "Basename matching is deliberately loose: a command touching a same-named file in a different "
                "directory (e.g. an installed copy under site-packages rather than the repo tree) counts as a "
                "reference.",
                "Channel B maps a dotted token mechanically and can therefore produce a path that does not exist: "
                "for psf__requests-1142 the issue text says 'requests.get is ALWAYS sending content length', which "
                "yields the candidate requests/get.py (an API function, not a module file). Those episodes "
                "consequently report referenced=false even though they repeatedly named requests/models.py. Read "
                "`source_paths_mentioned_in_commands` (below) instead of `referenced` for that instance.",
                "referenced_channel_a / referenced_channel_b report the same test restricted to one channel "
                "(null when that channel produced no candidate), so a channel-B artefact cannot silently flip the "
                "pooled flag.",
            ]),
        source_paths_mentioned_in_commands=(
            "An always-defined companion to the derivation above, independent of any target guess: the set of "
            "distinct tokens matching a .py/.rst path or basename anywhere in the episode's issued commands. It "
            "records which source paths the episode NAMED; it says nothing about whether the path existed in the "
            "container or was read successfully."),
        edit_write_target_classification=dict(
            rule=(
                "For commands matching an edit rule, write targets are extracted textually: the last token of a "
                "`sed -i` segment, the argument of `tee`, and any `>`/`>>` redirection target (excluding /dev/*). "
                "Each target is labelled placeholder_path (the literal '/path/to/' appears), "
                "installed_package_outside_repo_tree ('site-packages' or '/opt/miniconda3'), "
                "freshly_cloned_copy_outside_base_tree (the command also contains 'git clone'), "
                "inside_testbed_absolute, relative_resolves_under_testbed, or other_absolute_path."),
            basis=(
                "The harness config records environment.cwd='/testbed' and the prompt states that every action "
                "runs in a NEW subshell, so a relative path resolves under /testbed unless the same command "
                "cd's elsewhere first. This is a label on the path string that was written to; it is NOT a claim "
                "that the write succeeded or changed file content."),
        ),
    )
    artifact['limitations'] = [
        "DESCRIPTIVE ONLY. Every number here is a count or a classification of commands the agents ISSUED. "
        "Nothing here is a causal claim, an efficacy claim, a capability claim, or a recommendation about "
        "study design.",
        "An episode having zero edit-family commands is a FACT ABOUT ISSUED COMMANDS ONLY. It is not evidence "
        "about what the model could have done, and it is not a measurement of model capability.",
        "Conversely, an issued edit-family command is not evidence that a file changed. A `sed -i` whose pattern "
        "matches nothing exits 0 with empty output, which is indistinguishable in these artifacts from a "
        "successful substitution.",
        "The committed workspace-capture binding records a final tree and a patch ONLY on an explicit Submitted "
        "exit (experiments/v2_agent/workspace_capture.py); 30 of 32 episodes exited non-Submitted, so "
        "episode.final_tree is null for them and the artifacts contain NO record of the container's final file "
        "state. Whether any issued edit changed a file in /testbed therefore CANNOT be determined from the "
        "committed record for those 30 episodes. This is an ambiguity of the record, stated here as such.",
        "The 2 Submitted episodes (astropy__astropy-12907, backend small, both cohorts) exited on their first "
        "model call and their recorded final_tree equals base_tree, i.e. no change in /testbed for those two.",
        "Compound commands are the norm; the mandated single-family assignment uses the fixed priority order, so "
        "e.g. a `git bisect ... && git bisect run python -c ...` command is counted primary 'python_eval' and a "
        "`git clone ... && sed -i ... && echo <submit sentinel>` command is counted primary 'submit'. "
        "family_counts_any_match and the per-command listing expose every family a command matched.",
        "Classification is textual (regex over the command string). It does not execute, parse or resolve shell "
        "quoting, aliases, or the effective working directory of each segment.",
        "Observation outputs may have been elided/truncated by the harness; this analysis reads returncodes and "
        "command text only, which truncation does not affect.",
        "Commands issued on a call whose response the harness rejected for carrying more than one action are NOT "
        "recorded in the trajectory, so those attempted commands are invisible here and are counted only as "
        "n_format_error_calls.",
    ]
    artifact['episodes'] = episodes
    artifact['aggregates'] = dict(
        overall=aggregate(episodes, 'all', lambda e: 'all')['groups']['all'],
        by_cohort=aggregate(episodes, 'cohort', lambda e: e['cohort']),
        by_backend=aggregate(episodes, 'backend (both cohorts pooled)', lambda e: e['backend']),
        by_cohort_backend=aggregate(episodes, 'cohort x backend', lambda e: e['cohort'] + '/' + e['backend']),
        by_instance=aggregate(episodes, 'instance_id (both cohorts, both backends pooled)',
                              lambda e: e['instance_id']),
    )
    artifact['command_inventory'] = [
        dict(n_occurrences=n, primary_family=inventory_family[c], command=c)
        for c, n in sorted(inventory.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    blob = json.dumps(artifact, indent=1, sort_keys=False)
    # Guardrails: no host username, no absolute host paths in the artifact.
    assert str(REPO) not in blob, 'absolute host path leaked into artifact'
    assert Path.home().name not in blob, 'host account name leaked into artifact'
    assert Path.home().as_posix() not in blob, 'host home path leaked into artifact'
    assert sum(e['n_calls_with_recorded_command'] for e in episodes) == total_cmds
    for e in episodes:
        assert sum(e['family_counts_primary'].values()) == e['n_calls_with_recorded_command']
        assert e['n_calls_with_recorded_command'] + e['n_format_error_calls'] \
            + e['n_calls_without_recorded_message'] == e['n_model_calls'], e['run_id']

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, 'x') as fh:
        fh.write(blob)
    print(json.dumps(dict(written=str(OUT_PATH.relative_to(REPO)), bytes=len(blob),
                          n_episodes=len(episodes), n_commands=total_cmds), indent=1))


if __name__ == '__main__':
    sys.exit(main())
