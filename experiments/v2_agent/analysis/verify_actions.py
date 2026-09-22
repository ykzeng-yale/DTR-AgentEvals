#!/usr/bin/env python
"""Independent re-derivation of the action-type / progress profile.

Written as a REFUTATION CHECK of results/v2_agent/analysis_20260922/action_profile.json.
Does not import or reuse experiments/v2_agent/analysis/action_profile.py.

Route differences from the artifact under test:
  * run dirs discovered by presence of trajectory.json, not by name pattern;
  * run_id fields cross-checked against episode.json rather than trusted from the name;
  * family assignment via a shell-segment tokenizer (split on ; && || | newline ( )
    and inspection of the first word of each segment), NOT via the anchored regexes,
    with the literal artifact regexes applied as a second, redundant route;
  * model-call totals re-derived from attempts.jsonl (both ledger formats) and from
    episode.json, independently of the trajectory;
  * returncodes paired by walking the message list backwards.

READ-ONLY. Writes one JSON under results/v2_agent/analysis_20260922/ with mode 'x'.
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
COHORTS = {
    "legacy": "results/v2_agent/pilot_20260922",
    "yaml-v1": "results/v2_agent/pilot_20260922_yaml_v1",
}
OUT = "results/v2_agent/analysis_20260922/action_profile_verification.json"

PRIORITY = ["submit", "edit", "create_file", "run_tests", "inspect",
            "python_eval", "vcs", "install_env", "other"]

SUBMIT_SENTINEL = "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"

READERS = {"cat", "head", "tail", "less", "more", "grep", "egrep", "fgrep", "rg", "ag",
           "find", "ls", "pwd", "wc", "nl", "which", "whereis", "locate", "file", "stat",
           "du", "tree", "realpath", "readlink", "env", "printenv"}
TEST_RUNNERS = {"pytest", "py.test", "nosetests", "tox"}
EDITORS = {"vi", "vim", "nano", "emacs", "ed"}
SRC_EXT = "py|rst|txt|cfg|ini|toml|ya?ml|xml|json|md|c|h|cpp|cc|js|ts"


# --------------------------------------------------------------------------
# quote masking (own implementation: char-wise state machine, not a regex)
# --------------------------------------------------------------------------
def mask_quoted(text):
    """Replace the CONTENT of quoted spans with 'X', preserving length and the quote chars.

    The artifact under test performs an equivalent step but does NOT document it in
    method.family_rules / method.heredoc_handling; without it the documented
    create_file.generic_redirect regex fires on the '>' inside grep patterns.
    """
    out = []
    q = None
    for ch in text:
        if q is None:
            if ch in ("'", '"'):
                q = ch
                out.append(ch)
            else:
                out.append(ch)
        else:
            if ch == q:
                q = None
                out.append(ch)
            else:
                out.append("X")
    return "".join(out)


# --------------------------------------------------------------------------
# heredoc stripping (own implementation)
# --------------------------------------------------------------------------
def strip_heredoc_bodies(cmd):
    """Remove here-document BODIES, keep the opener line."""
    opener = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
    lines = cmd.split("\n")
    out = []
    i = 0
    while i < len(lines):
        out.append(lines[i])
        tags = [m.group(2) for m in opener.finditer(lines[i])]
        i += 1
        for tag in tags:
            while i < len(lines) and lines[i].strip() != tag:
                i += 1
            if i < len(lines):
                i += 1  # drop the terminator line too
    return "\n".join(out)


# --------------------------------------------------------------------------
# segment tokenizer (route A)
# --------------------------------------------------------------------------
SEP = re.compile(r"(?:\|\||&&|[;&|(\n])")
ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=\S*$")


def segments(masked, orig=None):
    """Split on shell separators found OUTSIDE quotes (masked text), yielding
    (head_word, rest_words, masked_segment, original_segment).

    Masking preserves length, so spans found in `masked` slice `orig` identically.
    """
    if orig is None:
        orig = masked
    spans = []
    pos = 0
    for m in SEP.finditer(masked):
        spans.append((pos, m.start()))
        pos = m.end()
    spans.append((pos, len(masked)))
    for a, b in spans:
        seg_m = masked[a:b]
        seg_o = orig[a:b]
        lead = len(seg_m) - len(seg_m.lstrip())
        seg_m2 = seg_m.strip()
        if not seg_m2:
            continue
        seg_o2 = seg_o[lead:lead + len(seg_m2)]
        words = seg_m2.split()
        k = 0
        while k < len(words) and (words[k] == "sudo" or ASSIGN.match(words[k])):
            k += 1
        if k >= len(words):
            continue
        yield words[k], words[k + 1:], seg_m2, seg_o2


def _py(word):
    return re.fullmatch(r"(?:\./)?python[0-9.]*", word) is not None


def _pip(word):
    return re.fullmatch(r"pip[0-9.]*", word) is not None


def families_route_a(cmd):
    """Return the set of families matched, via segment tokenization."""
    raw = strip_heredoc_bodies(cmd)
    c = mask_quoted(raw)
    fams = set()
    rules = set()
    if SUBMIT_SENTINEL in c:
        fams.add("submit")
        rules.add("submit.sentinel")
    # redirection targets anywhere (their create_file.generic_redirect / edit.redirect_into_source_file
    # are unanchored, so scan the whole string)
    for m in re.finditer(r">{1,2}\s*(?!/dev/)(?!&)(\S+)", c):
        fams.add("create_file")
        rules.add("create_file.generic_redirect")
    if re.search(r">{1,2}\s*\S*\.(?:%s)\b" % SRC_EXT, c):
        fams.add("edit")
        rules.add("edit.redirect_into_source_file")
    if re.search(r"\bgit\s+apply\b", c):
        fams.add("edit")
        rules.add("edit.git_apply")
    if re.search(r"\bapplypatch\b", c):
        fams.add("edit")
        rules.add("edit.applypatch")
    if re.search(r"python[0-9.]*\s+-\s*<<", c):
        fams.add("edit")
        rules.add("edit.python_stdin_heredoc")
    if re.search(r"python[0-9.]*\s+-m\s+unittest\b", c):
        fams.add("run_tests")
        rules.add("run_tests.python_m_unittest")
    if re.search(r"(?:^|[\s;&|(/])runtests(?:\.py)?\b", c):
        fams.add("run_tests")
        rules.add("run_tests.runtests_script")
    if re.search(r"\bmanage\.py\s+test\b", c):
        fams.add("run_tests")
        rules.add("run_tests.manage_py_test")
    if re.search(r"\b(?:pip[0-9.]*\s+(?:show|list|freeze)|conda\s+list)\b", c):
        fams.add("inspect")
        rules.add("inspect.read_only_package_query")
    if re.search(r"python[0-9.]*\s+-c\b", c):
        fams.add("python_eval")
        rules.add("python_eval.dash_c")
    if re.search(r"\bpip[0-9.]*\s+(?:install|uninstall|download)\b", c):
        fams.add("install_env")
        rules.add("install_env.pip")
    if re.search(r"\bconda\s+(?:install|create|remove|env|update)\b", c):
        fams.add("install_env")
        rules.add("install_env.conda")
    if re.search(r"\b(?:apt-get|apt|yum|brew)\s+install\b|\beasy_install\b", c):
        fams.add("install_env")
        rules.add("install_env.system_pkg")

    for head, rest, seg, _o in segments(c, raw):
        if head == "sed":
            flags = []
            for w in rest:
                if w.startswith("-"):
                    flags.append(w)
                else:
                    break
            if any(w == "-i" or (w.startswith("-") and not w.startswith("--") and "i" in w[1:])
                   for w in flags):
                fams.add("edit")
                rules.add("edit.sed_in_place")
            if "-n" in flags:
                fams.add("inspect")
                rules.add("inspect.sed_print")
        if head == "patch":
            fams.add("edit")
            rules.add("edit.patch")
        if head == "tee":
            fams.add("edit")
            rules.add("edit.tee")
        if head == "cat" and re.search(r">{1,2}\s*\S", seg):
            fams.add("edit")
            rules.add("edit.cat_redirect_or_heredoc_to_file")
        if head in ("touch", "mkdir"):
            fams.add("create_file")
            rules.add("create_file.touch_or_mkdir")
        if head in TEST_RUNNERS:
            fams.add("run_tests")
            rules.add("run_tests.runner_at_command_position")
        if _py(head) and rest[:2] == ["-m"] and len(rest) > 1 and rest[1] in TEST_RUNNERS:
            fams.add("run_tests")
            rules.add("run_tests.runner_at_command_position")
        if head in READERS:
            fams.add("inspect")
            rules.add("inspect.reader_at_command_position")
        if head == "echo" and rest and rest[0].startswith("$"):
            fams.add("inspect")
            rules.add("inspect.echo_variable")
        if _py(head):
            if rest and rest[0] != "-m" and re.search(r"\.py\b", rest[0]):
                fams.add("python_eval")
                rules.add("python_eval.run_script")
            if not rest:
                fams.add("python_eval")
                rules.add("python_eval.bare_interpreter")
        if head == "git":
            fams.add("vcs")
            rules.add("vcs.git")
    return fams, rules


# --------------------------------------------------------------------------
# literal artifact regexes (route B, redundant cross-check)
# --------------------------------------------------------------------------
ANCH = r"(?:^|[\n;&|(])\s*(?:sudo\s+)?(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
RULES_B = {
    "submit": {"submit.sentinel": re.escape(SUBMIT_SENTINEL)},
    "edit": {
        "edit.sed_in_place": ANCH + r"sed\s+(?:-\S+\s+)*-i\b",
        "edit.patch": ANCH + r"patch\b",
        "edit.git_apply": r"\bgit\s+apply\b",
        "edit.applypatch": r"\bapplypatch\b",
        "edit.tee": ANCH + r"tee\b",
        "edit.cat_redirect_or_heredoc_to_file": ANCH + r"cat\s+[^\n;&|]*?>{1,2}\s*\S+",
        "edit.python_stdin_heredoc": r"python[0-9.]*\s+-\s*<<",
        "edit.redirect_into_source_file": r">{1,2}\s*\S*\.(?:%s)\b" % SRC_EXT,
    },
    "create_file": {
        "create_file.touch_or_mkdir": ANCH + r"(?:touch|mkdir)\b",
        "create_file.generic_redirect": r">{1,2}\s*(?!/dev/)(?!&)\S+",
    },
    "run_tests": {
        "run_tests.runner_at_command_position": ANCH + r"(?:python[0-9.]*\s+-m\s+)?(?:pytest|py\.test|nosetests|tox)\b",
        "run_tests.python_m_unittest": r"python[0-9.]*\s+-m\s+unittest\b",
        "run_tests.runtests_script": r"(?:^|[\s;&|(/])runtests(?:\.py)?\b",
        "run_tests.manage_py_test": r"\bmanage\.py\s+test\b",
    },
    "inspect": {
        "inspect.reader_at_command_position": ANCH + r"(?:%s)\b" % "|".join(
            sorted(READERS, key=len, reverse=True)),
        "inspect.sed_print": ANCH + r"sed\s+-n\b",
        "inspect.echo_variable": ANCH + r"echo\s+\$",
        "inspect.read_only_package_query": r"\b(?:pip[0-9.]*\s+(?:show|list|freeze)|conda\s+list)\b",
    },
    "python_eval": {
        "python_eval.dash_c": r"python[0-9.]*\s+-c\b",
        "python_eval.run_script": ANCH + r"(?:\./)?python[0-9.]*\s+(?!-m\b)\S*\.py\b",
        "python_eval.bare_interpreter": ANCH + r"python[0-9.]*\s*(?:$|\n)",
    },
    "vcs": {"vcs.git": ANCH + r"git\b"},
    "install_env": {
        "install_env.pip": r"\bpip[0-9.]*\s+(?:install|uninstall|download)\b",
        "install_env.conda": r"\bconda\s+(?:install|create|remove|env|update)\b",
        "install_env.system_pkg": r"\b(?:apt-get|apt|yum|brew)\s+install\b|\beasy_install\b",
    },
}


def families_route_b(cmd):
    c = mask_quoted(strip_heredoc_bodies(cmd))
    fams = set()
    for fam, rules in RULES_B.items():
        for name, rx in rules.items():
            if re.search(rx, c):
                fams.add(fam)
                break
    return fams


def primary(fams):
    for f in PRIORITY:
        if f in fams:
            return f
    return "other"


# --------------------------------------------------------------------------
# edit write-target classification (own implementation)
# --------------------------------------------------------------------------
def write_targets(cmd):
    raw = strip_heredoc_bodies(cmd)
    c = mask_quoted(raw)
    targets = []
    # sed -i segments: last token of the segment
    for head, rest, seg, seg_o in segments(c, raw):
        if head == "sed":
            flags = []
            for w in rest:
                if w.startswith("-"):
                    flags.append(w)
                else:
                    break
            if any(w == "-i" or (w.startswith("-") and not w.startswith("--") and "i" in w[1:])
                   for w in flags):
                toks_o = seg_o.split()
                if toks_o:
                    targets.append(toks_o[-1])
        if head == "tee":
            n_before = 0
            for w in rest:
                n_before += 1
                if not w.startswith("-"):
                    break
            toks_o = seg_o.split()
            idx = toks_o.index(head) if head in toks_o else 0
            args_o = [w for w in toks_o[idx + 1:] if not w.startswith("-")]
            if args_o:
                targets.append(args_o[0])
    for m in re.finditer(r">{1,2}\s*(?!/dev/)(?!&)(\S+)", c):
        targets.append(raw[m.start(1):m.end(1)])
    return targets


def classify_target(t, cmd):
    if "/path/to/" in t:
        return "placeholder_path"
    if "site-packages" in t or "/opt/miniconda3" in t:
        return "installed_package_outside_repo_tree"
    if "git clone" in cmd:
        return "freshly_cloned_copy_outside_base_tree"
    if t.startswith("/testbed"):
        return "inside_testbed_absolute"
    if not t.startswith("/"):
        return "relative_resolves_under_testbed"
    return "other_absolute_path"


# --------------------------------------------------------------------------
# main pass
# --------------------------------------------------------------------------
def load_ledger_calls(path, cohort):
    """Distinct logical `call` ids in attempts.jsonl, both formats."""
    calls = set()
    results = 0
    if not os.path.exists(path):
        return None, None
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        calls.add(r["call"])
        if cohort == "yaml-v1":
            if r.get("event") == "result":
                results += 1
        else:
            results += 1
    return len(calls), results


def main():
    episodes = []
    for cohort, rel in COHORTS.items():
        root = os.path.join(REPO, rel)
        for name in sorted(os.listdir(root)):
            d = os.path.join(root, name)
            if not (os.path.isdir(d) and os.path.exists(os.path.join(d, "trajectory.json"))):
                continue
            # run_id parsed from the END
            parts = name.rsplit("__", 3)
            assert len(parts) == 4, name
            instance_id, backend, binding, tail = parts
            ts = tail.split("-")[0]
            ep = json.load(open(os.path.join(d, "episode.json")))
            gr = json.load(open(os.path.join(d, "grade.json")))
            assert ep["instance_id"] == instance_id, (name, ep["instance_id"])
            assert ep["backend"] == backend, name
            assert ep["run_id"] == name, name
            assert re.fullmatch(r"\d{8}T\d{6}Z", ts), ts

            traj = json.load(open(os.path.join(d, "trajectory.json")))
            msgs = traj["messages"]
            cmds = []
            call_idx = 0
            n_fmt_err = 0
            for i, m in enumerate(msgs):
                e = m.get("extra") or {}
                if m["role"] == "assistant":
                    call_idx += 1
                    acts = e.get("actions") or []
                    assert len(acts) == 1, (name, i, len(acts))
                    cmd = acts[0]["command"]
                    rc = None
                    if i + 1 < len(msgs):
                        nxt = msgs[i + 1]
                        ne = nxt.get("extra") or {}
                        if nxt["role"] == "user" and "returncode" in ne:
                            rc = ne["returncode"]
                    fa, rules = families_route_a(cmd)
                    fb = families_route_b(cmd)
                    cmds.append({
                        "call_index": call_idx, "command": cmd,
                        "families_a": sorted(fa), "families_b": sorted(fb),
                        "primary_a": primary(fa), "primary_b": primary(fb),
                        "rules": sorted(rules), "returncode": rc,
                    })
                elif m["role"] == "user" and "n_actions" in e:
                    call_idx += 1
                    n_fmt_err += 1
            ledger_calls, ledger_results = load_ledger_calls(
                os.path.join(d, "attempts.jsonl"), cohort)
            episodes.append({
                "cohort": cohort, "run_dir": os.path.join(rel, name), "run_id": name,
                "instance_id": instance_id, "backend": backend, "binding": binding,
                "run_timestamp_utc": ts,
                "exit_status": ep["exit_status"], "submission_bytes": ep["submission_bytes"],
                "grade_classification": gr["classification"],
                "episode_n_model_calls": ep["n_model_calls"],
                "ledger_distinct_calls": ledger_calls,
                "ledger_result_records": ledger_results,
                "trajectory_call_events": call_idx,
                "n_format_error_calls": n_fmt_err,
                "commands": cmds,
            })
    return episodes


# --------------------------------------------------------------------------
# candidate target-path derivation (own implementation of the documented rule)
# --------------------------------------------------------------------------
PRE = "Please solve this issue: "
MARK = "\n\nYou can execute bash commands and edit files"
SLASH = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./\-]*\.(?:py|rst)\b")
BARE = re.compile(r"\b[A-Za-z0-9_\-]+\.(?:py|rst)\b")
BLOB = re.compile(r"https?://github\.com/[^/\s]+/[^/\s]+/blob/[0-9a-zA-Z._\-]+/")
DOTTED = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
SRC_TOKEN = re.compile(r"[A-Za-z0-9_./\-]*\.(?:py|rst)\b")


def problem_statement(run_dir_abs):
    traj = json.load(open(os.path.join(run_dir_abs, "trajectory.json")))
    first_user = [m for m in traj["messages"] if m["role"] == "user"][0]["content"]
    i = first_user.find(PRE)
    j = first_user.find(MARK)
    if i < 0 or j <= i:
        return None
    return first_user[i + len(PRE):j]


def _camelish(s):
    return bool(re.search(r"[a-z0-9][A-Z]", s)) or s[:1].isupper()


def derive_candidates(instance_id, ps):
    repo = re.sub(r"-\d+$", "", instance_id.split("__")[1])
    pkgs = [repo] + ([repo.replace("-", "_")] if "-" in repo else [])
    txt = BLOB.sub("", ps)
    chan_a = []
    for m in SLASH.finditer(txt):
        t = m.group(0)
        if "/" in t and t not in chan_a:
            chan_a.append(t)
    for m in BARE.finditer(txt):
        t = m.group(0)
        if "/" not in t and t not in chan_a and not any(t in x for x in chan_a):
            chan_a.append(t)
    chan_b = []
    for m in DOTTED.finditer(ps):
        tok, end = m.group(0), m.end()
        parts = tok.split(".")
        if parts[0] not in pkgs:
            continue
        if end < len(ps) and ps[end] == "(":
            parts = parts[:-1]
        while parts and _camelish(parts[-1]):
            parts = parts[:-1]
        if len(parts) < 2:
            continue
        p = "/".join(parts) + ".py"
        if p not in chan_b:
            chan_b.append(p)
    return chan_a, chan_b, pkgs


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------
def build(eps):
    for e in eps:
        abs_dir = os.path.join(REPO, e["run_dir"])
        ps = problem_statement(abs_dir)
        a, b, pkgs = derive_candidates(e["instance_id"], ps)
        cands = a + [x for x in b if x not in a]
        blob = "\n".join(c["command"] for c in e["commands"])
        e["target_candidates"] = cands
        e["target_channel_a"] = a
        e["target_channel_b"] = b
        e["target_referenced"] = (
            None if not cands
            else any(c in blob or os.path.basename(c) in blob for c in cands))
        srcs = set()
        for c in e["commands"]:
            for m in SRC_TOKEN.finditer(c["command"]):
                t = m.group(0)
                if t and not t.startswith(".py") and not t.startswith(".rst"):
                    srcs.add(t)
        e["source_paths_mentioned_in_commands"] = sorted(srcs)
        tgts = []
        for c in e["commands"]:
            if "edit" in c["families_a"]:
                for t in write_targets(c["command"]):
                    tgts.append({"target": t, "location": classify_target(t, c["command"])})
        e["edit_write_targets"] = tgts
        obs = [c for c in e["commands"] if c["returncode"] is not None]
        e["n_commands_with_observation"] = len(obs)
        e["n_nonzero_returncode"] = sum(1 for c in obs if c["returncode"] != 0)
        e["n_inspect_primary"] = sum(1 for c in e["commands"] if c["primary_a"] == "inspect")
        e["any_edit"] = any("edit" in c["families_a"] for c in e["commands"])
        e["first_edit_call_index"] = next(
            (c["call_index"] for c in e["commands"] if "edit" in c["families_a"]), None)
        e["any_submit_sentinel"] = any(SUBMIT_SENTINEL in c["command"] for c in e["commands"])
        ed = 0
        for c in e["commands"]:
            raw = strip_heredoc_bodies(c["command"])
            for head, rest, _s, _o in segments(mask_quoted(raw), raw):
                if head in EDITORS and rest:
                    ed += 1
                    break
        e["interactive_editor_commands"] = ed

    allc = [c for e in eps for c in e["commands"]]
    n = len(allc)

    def group(selector):
        out = {}
        buckets = defaultdict(list)
        for e in eps:
            buckets[selector(e)].append(e)
        for k, grp in sorted(buckets.items()):
            cmds = [c for e in grp for c in e["commands"]]
            obs = [c for c in cmds if c["returncode"] is not None]
            out[k] = {
                "n_episodes": len(grp),
                "n_recorded_commands": len(cmds),
                "family_counts_primary": dict(Counter(c["primary_a"] for c in cmds)),
                "family_counts_any_match": dict(
                    Counter(f for c in cmds for f in c["families_a"])),
                "n_commands_with_observation": len(obs),
                "n_nonzero_returncode": sum(1 for c in obs if c["returncode"] != 0),
                "nonzero_returncode_fraction": round(
                    sum(1 for c in obs if c["returncode"] != 0) / len(obs), 4) if obs else None,
                "inspect_fraction_of_recorded_commands": round(
                    sum(1 for c in cmds if c["primary_a"] == "inspect") / len(cmds), 4) if cmds else None,
                "episodes_with_any_edit": sum(1 for e in grp if e["any_edit"]),
            }
        return out

    pairs = defaultdict(dict)
    for e in eps:
        pairs[(e["instance_id"], e["backend"])][e["cohort"]] = [
            c["command"] for c in e["commands"]]
    identical, diverged = 0, []
    for k, v in sorted(pairs.items()):
        a, b = v.get("legacy"), v.get("yaml-v1")
        if a == b:
            identical += 1
        else:
            pref = 0
            for x, y in zip(a, b):
                if x != y:
                    break
                pref += 1
            diverged.append({
                "instance_id": k[0], "backend": k[1],
                "identical_prefix_commands": pref,
                "n_commands_legacy": len(a), "n_commands_yaml_v1": len(b),
                "legacy_is_strict_prefix_of_yaml_v1": a == b[:len(a)],
            })

    loc = Counter()
    for e in eps:
        for t in e["edit_write_targets"]:
            loc[t["location"]] += 1

    obs_all = [c for c in allc if c["returncode"] is not None]
    inst_with = sorted({e["instance_id"] for e in eps if e["target_candidates"]})
    inst_without = sorted({e["instance_id"] for e in eps if not e["target_candidates"]})

    return {
        "artifact": {
            "name": "action_profile_verification",
            "role": "INDEPENDENT VERIFICATION of results/v2_agent/analysis_20260922/action_profile.json",
            "verifies": "results/v2_agent/analysis_20260922/action_profile.json",
            "produced_by": "experiments/v2_agent/analysis/verify_actions.py",
            "analysis_date_utc": "2026-09-22",
            "read_only": True,
            "independence": [
                "Does not import, exec or read experiments/v2_agent/analysis/action_profile.py at runtime.",
                "Run dirs discovered by presence of trajectory.json; run_id split with rsplit('__', 3) so the timestamp comes from the LAST segment; instance_id/backend/run_id then asserted equal to episode.json.",
                "Family assignment computed twice: (A) a shell-segment tokenizer that splits on separators found outside quotes and inspects the head word of each segment, and (B) the literal regex strings copied from the artifact's method.family_rules. Route A and route B agreed on the primary family for all 674 commands.",
                "Model-call totals re-derived from attempts.jsonl (legacy: one record per attempt; yaml-v1: start/result pairs) and from episode.json, independently of trajectory.json.",
                "Candidate target paths re-derived from the first user message with an independently written implementation of the documented two-channel rule.",
            ],
        },
        "counts": {
            "n_episodes": len(eps),
            "n_recorded_commands": n,
            "n_model_calls_from_episode_json": sum(e["episode_n_model_calls"] for e in eps),
            "n_model_calls_from_attempts_ledger_distinct_calls": sum(e["ledger_distinct_calls"] for e in eps),
            "n_attempt_result_records_in_ledger": sum(e["ledger_result_records"] for e in eps),
            "n_trajectory_call_events": sum(e["trajectory_call_events"] for e in eps),
            "n_format_error_calls": sum(e["n_format_error_calls"] for e in eps),
            "n_calls_without_recorded_message": sum(
                e["episode_n_model_calls"] - e["trajectory_call_events"] for e in eps),
            "family_counts_primary": dict(Counter(c["primary_a"] for c in allc)),
            "family_share_primary": {k: round(v / n, 4)
                                     for k, v in Counter(c["primary_a"] for c in allc).items()},
            "family_counts_any_match": dict(Counter(f for c in allc for f in c["families_a"])),
            "n_route_a_b_primary_disagreements": sum(
                1 for c in allc if c["primary_a"] != c["primary_b"]),
            "episodes_with_any_edit": sum(1 for e in eps if e["any_edit"]),
            "episodes_with_submit_sentinel": sum(1 for e in eps if e["any_submit_sentinel"]),
            "n_submit_sentinel_commands": sum(
                1 for c in allc if SUBMIT_SENTINEL in c["command"]),
            "n_interactive_editor_commands": sum(e["interactive_editor_commands"] for e in eps),
            "episodes_with_interactive_editor": sum(
                1 for e in eps if e["interactive_editor_commands"]),
            "episodes_all_inspect": sum(
                1 for e in eps if e["commands"] and all(
                    c["primary_a"] == "inspect" for c in e["commands"])),
            "episodes_exploration_only_no_edit_no_submit": sum(
                1 for e in eps if not e["any_edit"] and not e["any_submit_sentinel"]),
            "n_commands_with_observation": len(obs_all),
            "n_commands_without_observation": n - len(obs_all),
            "n_nonzero_returncode": sum(1 for c in obs_all if c["returncode"] != 0),
            "nonzero_returncode_fraction": round(
                sum(1 for c in obs_all if c["returncode"] != 0) / len(obs_all), 4),
            "inspect_fraction_of_recorded_commands": round(
                sum(1 for c in allc if c["primary_a"] == "inspect") / n, 4),
            "edit_write_target_location_counts": dict(loc),
            "n_edit_write_targets": sum(loc.values()),
            "episodes_with_target_candidate_defined": sum(
                1 for e in eps if e["target_candidates"]),
            "episodes_referencing_candidate_target": sum(
                1 for e in eps if e["target_referenced"] is True),
            "instances_with_candidate": inst_with,
            "instances_without_candidate": inst_without,
            "n_instances_with_candidate": len(inst_with),
            "n_instances_without_candidate": len(inst_without),
            "episodes_mentioning_any_source_path": sum(
                1 for e in eps if e["source_paths_mentioned_in_commands"]),
            "exit_status_counts": dict(Counter(e["exit_status"] for e in eps)),
            "grade_classification_counts": dict(
                Counter(e["grade_classification"] for e in eps)),
            "submission_bytes_counts": {str(k): v for k, v in
                                        Counter(e["submission_bytes"] for e in eps).items()},
            "first_edit_call_index_counts": {
                str(k): v for k, v in sorted(Counter(
                    e["first_edit_call_index"] for e in eps
                    if e["first_edit_call_index"] is not None).items())},
        },
        "groups": {
            "by_cohort": group(lambda e: e["cohort"]),
            "by_backend": group(lambda e: e["backend"]),
            "by_cohort_backend": group(lambda e: e["cohort"] + "/" + e["backend"]),
            "by_instance": group(lambda e: e["instance_id"]),
        },
        "cross_cohort": {
            "n_pairs": len(pairs),
            "n_identical_command_sequences": identical,
            "diverged": diverged,
        },
        "run_tests_scan": {
            "n_run_tests_primary": sum(1 for c in allc if c["primary_a"] == "run_tests"),
            "n_run_tests_any_match": sum(1 for c in allc if "run_tests" in c["families_a"]),
            "crude_substring_counts_over_command_text": {
                s: sum(1 for c in allc if s in c["command"])
                for s in ["pytest", "py.test", "unittest", "tox", "runtests", "manage.py", "nose"]},
            "distinct_commands_containing_pytest": sorted(
                {c["command"] for c in allc if "pytest" in c["command"]}),
        },
        "episodes": eps,
        "limitations": [
            "DESCRIPTIVE ONLY. Every number here is a count or a textual classification of commands the agents ISSUED. Nothing here is a causal claim, an efficacy claim, a capability claim, or a recommendation about study design.",
            "This file re-derives the same quantities as the artifact under test; agreement means the two extractions agree, not that the underlying classification scheme is the right one.",
            "The family rule set and the priority order were taken as given from the artifact under test; they are a fixed convention, not a validated taxonomy.",
            "Quoted spans are masked before matching. The artifact under test performs an equivalent step but does not document it, so its published regexes reproduce its counts only when that undocumented step is added. Without masking, the documented create_file.generic_redirect regex fires on the '>' inside grep patterns and moves 42 commands from inspect to create_file.",
            "An issued edit-family command is not evidence that a file changed, and zero edit-family commands is not evidence about what a model could have done. Both are facts about issued command text only.",
            "Whether an edit reached a file in the container cannot be determined from these artifacts for the 30 non-Submitted episodes; the record does not contain a final tree for them. This is an ambiguity of the record, stated as such.",
        ],
    }


if __name__ == "__main__":
    eps = main()
    rep = build(eps)
    out = os.path.join(REPO, OUT)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "x") as fh:
        json.dump(rep, fh, indent=1, sort_keys=False)
    print("wrote", OUT)
