"""DTR-REQ-015 (lead 00295d6, docs/theory_feedback_20260925_req014_decision.md): a NO-MODEL, NO-GPU qualification of
the pinned BrowserGym MiniWoB `book-flight` task as the fallback mechanism setting. The committed manifest
configs/v2_req015_miniwob_bookflight_20260925.json is the specification.

    work/venvs/browsergym_9e779f0/bin/python experiments/v2_browser/req015_qualify.py --admission-only   (read-only)
    work/venvs/browsergym_9e779f0/bin/python experiments/v2_browser/req015_qualify.py                    (single shot)

Scripted traces only (no model, no inference): a visible-information positive policy (terminal full success
required), a negative trace (same prefix, a different booking choice) and a no-op trace, plus reset determinism. The
scripted policy reads only the goal and the flattened accessibility tree; the verifier fields (WOB_* globals) are
recorded separately, labelled verifier-only, and never feed a decision. It is a mechanism/feasibility check, not a
repository-repair claim, not a model result and not a change of the fixed primary target.

The pure functions (goal/axtree parsing, choices, verdict) import nothing outside the standard library, so the project
test suite exercises them without BrowserGym.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/v2_adapter'))
import req010_sentinel as S  # noqa: E402  stdlib-only helpers (sanitize, write-once JSON, peer status, username guard)

REQUEST = 'DTR-REQ-015'
MANIFEST_REL = 'configs/v2_req015_miniwob_bookflight_20260925.json'
GIB = 2 ** 30
MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
          'November', 'December')

# ------------------------------------------------------------------ pure parsing and choices (agent-visible only)
GOAL = re.compile(r'^Book the (cheapest|shortest) one-way flight from: (.+) to: (.+) on (\d\d)/(\d\d)/(\d{4})\.$')
AX_LINE = re.compile(r'''^(\t*)(?:\[([^\]]+)\] )?(\S+) ('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")(.*)$''')
CODE = re.compile(r'^[A-Z]{3}$')
DURATION = re.compile(r'^(\d+)h (\d+)m$')
BOOK = re.compile(r'^Book flight for \$(\d+)$')


def parse_goal(goal: str):
    """{'criterion', 'origin', 'destination', 'month', 'day', 'year', 'date'} or None when the goal does not match."""
    m = GOAL.match(goal.strip())
    if not m:
        return None
    crit, origin, dest, mm, dd, yyyy = m.groups()
    return OrderedDict(criterion=crit, origin=origin, destination=dest, month=int(mm), day=int(dd), year=int(yyyy),
                       date='%s/%s/%s' % (mm, dd, yyyy))


def ax_lines(text: str):
    """Flattened BrowserGym axtree -> [(depth, bid or None, role, name, rest)]; unparsable lines are skipped."""
    out = []
    for line in text.splitlines():
        m = AX_LINE.match(line)
        if m:
            tabs, bid, role, quoted, rest = m.groups()
            try:
                name = ast.literal_eval(quoted)          # BrowserGym prints names with repr()
            except (ValueError, SyntaxError):
                continue
            out.append((len(tabs), bid, role, name, rest))
    return out


def bids(text: str):
    return {b for _, b, _, _, _ in ax_lines(text) if b}


def find_bid(text: str, role: str, name: str):
    for _, b, r, n, _ in ax_lines(text):
        if b and r == role and n == name:
            return b
    return None


def autocomplete_options(text: str):
    """[(listitem bid, label)] in page order: a listitem with a descendant StaticText label."""
    rows, out, i = ax_lines(text), [], 0
    while i < len(rows):
        depth, b, role, _, _ = rows[i]
        if role == 'listitem' and b:
            j = i + 1
            while j < len(rows) and rows[j][0] > depth:
                if rows[j][2] == 'StaticText' and rows[j][3]:
                    out.append((b, rows[j][3]))
                    break
                j += 1
        i += 1
    return out


def option_matches(label: str, wanted: str) -> bool:
    """An airport code must appear as '(CODE)'; a city must be the label's prefix before ' ('."""
    if CODE.match(wanted):
        return '(%s)' % wanted in label
    return label.startswith(wanted + ' (')


def choose_option(options, wanted: str):
    """(bid, label, n_matching) for the first visible option matching `wanted`, or (None, None, 0)."""
    hits = [(b, l) for b, l in options if option_matches(l, wanted)]
    return (hits[0][0], hits[0][1], len(hits)) if hits else (None, None, 0)


def calendar_state(text: str):
    """Displayed datepicker month/year, the enabled Prev/Next link bids and the day-link bids, or None."""
    rows = ax_lines(text)
    month = year = None
    prev_bid = next_bid = None
    seen_nav = False
    days = OrderedDict()
    for depth, b, role, name, _ in rows:
        if name == 'Prev' and role in ('link', 'StaticText'):
            seen_nav = True
            prev_bid = b if role == 'link' else prev_bid
        elif name == 'Next' and role in ('link', 'StaticText'):
            seen_nav = True
            next_bid = b if role == 'link' else next_bid
        elif seen_nav and role == 'StaticText' and name in MONTHS and month is None:
            month = MONTHS.index(name) + 1
        elif seen_nav and month is not None and year is None and role == 'StaticText' and re.fullmatch(r'\d{4}', name):
            year = int(name)
        elif seen_nav and role == 'link' and b and re.fullmatch(r'\d{1,2}', name):
            days[int(name)] = b
    if not seen_nav or month is None or year is None:
        return None
    return OrderedDict(month=month, year=year, prev_bid=prev_bid, next_bid=next_bid, days=days)


def month_offset(cur_month: int, cur_year: int, month: int, year: int) -> int:
    """Months from the displayed month to the target (positive = Next, negative = Prev)."""
    return (year * 12 + month) - (cur_year * 12 + cur_month)


def flights(text: str):
    """[{'duration_minutes', 'duration_text', 'price', 'book_bid'}] in page order: each 'Xh Ym' duration pairs with
    the next 'Book flight for $N' button."""
    out, pending = [], None
    for _, b, role, name, _ in ax_lines(text):
        d = DURATION.match(name) if role == 'StaticText' else None
        if d:
            pending = (int(d.group(1)) * 60 + int(d.group(2)), name)
            continue
        m = BOOK.match(name) if role == 'button' else None
        if m and b:
            out.append(OrderedDict(duration_minutes=pending[0] if pending else None,
                                   duration_text=pending[1] if pending else None, price=int(m.group(1)), book_bid=b))
            pending = None
    return out


def choose_flight(rows, criterion: str, worst: bool = False):
    """(bid, visible_tie) for the best (or, for the negative trace, the worst) flight by the goal's criterion, using
    only the displayed price or duration; the first flight in page order wins a displayed tie."""
    key = 'price' if criterion == 'cheapest' else 'duration_minutes'
    vals = [r[key] for r in rows]
    if not rows or any(v is None for v in vals):
        return None, False
    target = max(vals) if worst else min(vals)
    idx = vals.index(target)
    return rows[idx]['book_bid'], vals.count(target) > 1


# ------------------------------------------------------------------ verdict (pure)
QUALIFICATION_CHECKS = ('sources_pinned', 'runtime_pinned', 'reset_reproducible', 'feedback_dependent_decisions',
                        'positive_full_success', 'negative_fails_predicate', 'noop_fails_predicate',
                        'browser_isolation', 'no_harness_error', 'resources_within_caps')


def full_success(task_info: dict) -> bool:
    """The terminal full-success predicate: the episode is done and the RAW MiniWoB reward is exactly 1.0 (not the
    BrowserGym binarized reward and not the time-scaled WOB_REWARD_GLOBAL)."""
    return bool(task_info.get('DONE_GLOBAL')) and task_info.get('RAW_REWARD_GLOBAL') == 1.0


def verdict(host_ok: bool, checks: dict):
    """BLOCKED when the host gates failed (nothing started); QUALIFIED only if every check is True; otherwise
    NOT_QUALIFIED naming each failed or missing check."""
    if not host_ok:
        return OrderedDict(verdict='BLOCKED', failed_checks=[])
    failed = [c for c in QUALIFICATION_CHECKS if checks.get(c) is not True]
    return OrderedDict(verdict='NOT_QUALIFIED' if failed else 'QUALIFIED', failed_checks=failed)


def tree_rss_kb(ps_text: str, root_pid: int) -> int:
    """Sum of RSS (KiB) over root_pid and all its descendants, from `ps -A -o pid=,ppid=,rss=` output."""
    children, rss = {}, {}
    for line in ps_text.splitlines():
        parts = line.split()
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            continue
        pid, ppid, kb = map(int, parts)
        rss[pid] = kb
        children.setdefault(ppid, []).append(pid)
    total, stack, seen = 0, [root_pid], set()
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.add(p)
        total += rss.get(p, 0)
        stack.extend(children.get(p, []))
    return total


# ------------------------------------------------------------------ manifest, sources, host gates
def load_manifest(root=ROOT):
    raw = (root / MANIFEST_REL).read_bytes()
    return json.loads(raw), S.sha_bytes(raw)


def check_sources(manifest, root=ROOT, run=S.sh):
    """Every third-party checkout at its pinned commit with a clean tree, and every recorded file hash equal."""
    d, ok = OrderedDict(), True
    for name, spec in manifest['sources'].items():
        path = root / spec['checkout']
        rc, head, _ = run(['git', '-C', str(path), 'rev-parse', 'HEAD'])
        rc2, status, _ = run(['git', '-C', str(path), 'status', '--porcelain'])
        files = OrderedDict()
        for rel, want in spec.get('files', {}).items():
            fp = path / rel
            got = S.sha_file(fp) if fp.is_file() else None
            files[rel] = OrderedDict(sha256=got, expected=want, equal=got == want)
        row = OrderedDict(commit=head.strip() if rc == 0 else None, expected_commit=spec['commit'],
                          clean=rc2 == 0 and status.strip() == '', license=spec['license'], files=files)
        row['ok'] = (row['commit'] == spec['commit'] and row['clean'] and all(f['equal'] for f in files.values()))
        ok &= row['ok']
        d[name] = row
    return ok, d


INSTALLED_MODULES = (('browsergym.miniwob.base', 'browsergym/miniwob/src/browsergym/miniwob/base.py'),
                     ('browsergym.miniwob.all', 'browsergym/miniwob/src/browsergym/miniwob/all.py'),
                     ('browsergym.miniwob', 'browsergym/miniwob/src/browsergym/miniwob/__init__.py'),
                     ('browsergym.core.env', 'browsergym/core/src/browsergym/core/env.py'),
                     ('browsergym.core.task', 'browsergym/core/src/browsergym/core/task.py'),
                     ('browsergym.core.action.highlevel', 'browsergym/core/src/browsergym/core/action/highlevel.py'),
                     ('browsergym.core.registration', 'browsergym/core/src/browsergym/core/registration.py'),
                     ('browsergym.core.action.functions', 'browsergym/core/src/browsergym/core/action/functions.py'),
                     ('browsergym.core.observation', 'browsergym/core/src/browsergym/core/observation.py'),
                     ('browsergym.utils.obs', 'browsergym/core/src/browsergym/utils/obs.py'))


def check_runtime(manifest):
    """Pinned interpreter and distributions (in-process; run under the BrowserGym venv) and the Chromium build dir."""
    import importlib.metadata as md
    rt = manifest['runtime']
    dists = sorted('%s==%s' % (x.metadata['Name'], x.version) for x in md.distributions())
    want = rt['distributions']
    have = OrderedDict((k, next((x.split('==', 1)[1] for x in dists if x.split('==', 1)[0].lower() == k.lower()), None))
                       for k in want)
    browsers = ROOT / rt['playwright_browsers_path']
    d = OrderedDict(python=platform.python_version(), expected_python_prefix=rt['python_prefix'],
                    distributions=have, expected=want, all_distributions_sha256=S.sha_bytes('\n'.join(dists).encode()),
                    n_distributions=len(dists), chromium_build_dir=rt['chromium_build_dir'],
                    chromium_build_present=(browsers / rt['chromium_build_dir']).is_dir())
    import importlib.util
    bg = manifest['sources']['BrowserGym']['files']
    installed = OrderedDict()
    for module, rel in INSTALLED_MODULES:
        try:
            origin = importlib.util.find_spec(module).origin
            got = S.sha_file(origin)
        except Exception as e:  # noqa: BLE001  recorded; fails the check
            got = '%s: %s' % (type(e).__name__, e)
        installed[module] = OrderedDict(sha256=got, pinned_source=rel, equal=got == bg.get(rel))
    import browsergym.core as core_pkg
    core_dir = Path(core_pkg.__file__).parent
    for rel in ('javascript/frame_mark_elements.js', 'javascript/frame_unmark_elements.js', 'chat.py'):
        src = 'browsergym/core/src/browsergym/core/' + rel
        fp = core_dir / rel
        got = S.sha_file(fp) if fp.is_file() else None
        installed['browsergym.core/' + rel] = OrderedDict(sha256=got, pinned_source=src, equal=got == bg.get(src))
    d['installed_modules_equal_pinned_source'] = installed
    ok = (d['python'].startswith(rt['python_prefix']) and all(have[k] == v for k, v in want.items())
          and d['chromium_build_present'] and all(r['equal'] for r in installed.values()))
    return ok, d


def memory_state(run=S.sh):
    rc, out, _ = run(['memory_pressure'], timeout=10)
    m = re.search(r'System-wide memory free percentage: (\d+)%', out or '')
    rc2, mem, _ = run(['sysctl', '-n', 'hw.memsize'], timeout=5)
    try:
        total = int(mem.strip())
    except ValueError:
        total = None
    pct = int(m.group(1)) if (rc == 0 and m) else None
    avail = pct / 100.0 * total if (pct is not None and total) else None
    return OrderedDict(free_pct=pct, hw_memsize=total, available_bytes=avail)


def host_gates(manifest, root=ROOT, run=S.sh, peer=S.peer_status, usage=shutil.disk_usage):
    g = manifest['host_gates']
    mem = memory_state(run)
    free_disk = usage(str(root)).free
    pok, pdet = peer(run=run)
    rc, rows = S.process_table(run)
    mine = S.ancestors(rows, os.getpid()) | {os.getpid()}
    others = [pid for pid, _, argv in rows if pid not in mine and '--admission-only' not in argv
              and any(Path(a).name == 'req015_qualify.py' for a in argv)]
    rows = OrderedDict(
        memory=OrderedDict(ok=mem['available_bytes'] is not None and mem['available_bytes'] >= g['min_available_memory_gib'] * GIB,
                           detail=mem),
        disk=OrderedDict(ok=free_disk >= g['min_host_disk_free_gib'] * GIB, detail=OrderedDict(host_disk_free_gib=free_disk / GIB)),
        peer=OrderedDict(ok=pok, detail=pdet),
        no_other_req015=OrderedDict(ok=rc == 0 and not others, detail=OrderedDict(ps_rc=rc, other_pids=others)))
    return all(v['ok'] for v in rows.values()), rows


# ------------------------------------------------------------------ resource monitor
class Monitor(threading.Thread):
    """Samples the RSS of this process tree (Chromium children included) every `interval` s; `breached` is set when
    the tree exceeds the peak-memory cap."""

    def __init__(self, cap_bytes, interval=0.5, sh=S.sh):
        super().__init__(daemon=True)
        self.cap, self.interval, self.sh = cap_bytes, interval, sh
        self.peak_kb, self.samples, self.errors = 0, 0, 0
        self.breached = threading.Event()
        self.stop = threading.Event()

    def run_once(self):
        rc, out, _ = self.sh(['ps', '-A', '-o', 'pid=,ppid=,rss='], timeout=5)
        if rc != 0:
            self.errors += 1
            return
        kb = tree_rss_kb(out, os.getpid())
        self.samples += 1
        self.peak_kb = max(self.peak_kb, kb)
        if kb * 1024 > self.cap:
            self.breached.set()

    def run(self):  # noqa: D401  threading entry point
        while not self.stop.is_set():
            self.run_once()
            self.stop.wait(self.interval)


# ------------------------------------------------------------------ episodes (BrowserGym; imported lazily)
class CapExceeded(Exception):
    pass


def make_env(manifest):
    import gymnasium as gym
    import browsergym.miniwob  # noqa: F401  registers browsergym/miniwob.*
    e = manifest['environment']
    return gym.make(manifest['task']['gym_id'], headless=e['headless'], pw_context_kwargs=e['pw_context_kwargs'])


def agent_view(obs):
    from browsergym.utils.obs import flatten_axtree_to_str
    return OrderedDict(goal=obs['goal'], url=obs['url'], axtree=flatten_axtree_to_str(obs['axtree_object']),
                       last_action_error=obs['last_action_error'], focused_element_bid=obs['focused_element_bid'])


def verifier_view(reward, terminated, truncated, info):
    ti = info.get('task_info') or {}
    return OrderedDict(browsergym_reward=reward, terminated=terminated, truncated=truncated,
                       RAW_REWARD_GLOBAL=ti.get('RAW_REWARD_GLOBAL'), REWARD_GLOBAL=ti.get('REWARD_GLOBAL'),
                       DONE_GLOBAL=ti.get('DONE_GLOBAL'), REWARD_REASON=ti.get('REWARD_REASON'),
                       EPISODE_ID=ti.get('EPISODE_ID'))


class Episode:
    """One seeded episode: records every (action, agent-visible observation, verifier-only fields, screenshot)."""

    def __init__(self, env, seed, kind, label, out_dir, deadline, monitor, max_steps):
        self.env, self.seed, self.kind, self.label, self.out, self.deadline = env, seed, kind, label, out_dir, deadline
        self.monitor, self.max_steps = monitor, max_steps
        self.steps, self.requests = [], []
        self.obs = None
        self.initial_bids = set()

    def guard(self):
        if time.time() > self.deadline:
            raise CapExceeded('wall cap reached')
        if self.monitor.breached.is_set():
            raise CapExceeded('peak memory cap reached')

    def shot(self, obs, n):
        from PIL import Image
        p = self.out / 'screenshots' / ('%s_seed%d_step%02d.png' % (self.label, self.seed, n))
        p.parent.mkdir(exist_ok=True)
        Image.fromarray(obs['screenshot']).save(p)
        return 'screenshots/' + p.name

    def reset(self):
        self.guard()
        t = time.time()
        obs, info = self.env.reset(seed=self.seed)
        u = self.env.unwrapped
        u.context.on('request', lambda r: self.requests.append(r.url))
        loaded = u.page.evaluate("""() => [location.href].concat(
            Array.from(document.querySelectorAll('script[src]')).map(e => e.src),
            Array.from(document.querySelectorAll('link[href]')).map(e => e.href),
            Array.from(document.querySelectorAll('img[src]')).map(e => e.src))""")
        self.initial_resources = loaded
        self.browser_version = u.browser.version
        self.obs = obs
        view = agent_view(obs)
        self.initial_bids = bids(view['axtree'])
        self.steps.append(OrderedDict(step=0, action='reset(seed=%d)' % self.seed, reset_seconds=round(time.time() - t, 3),
                                      decision=None, agent_visible=view, screenshot=self.shot(obs, 0),
                                      verifier_only=OrderedDict(task_info=info.get('task_info'))))
        return view

    def act(self, action, decision):
        self.guard()
        if len(self.steps) > self.max_steps:
            raise CapExceeded('step cap reached')
        obs, reward, term, trunc, info = self.env.step(action)
        self.obs = obs
        view = agent_view(obs)
        self.steps.append(OrderedDict(step=len(self.steps), action=action, decision=decision, agent_visible=view,
                                      screenshot=self.shot(obs, len(self.steps)),
                                      verifier_only=verifier_view(reward, term, trunc, info)))
        return view, term or trunc

    def capture_resources(self):
        """Every resource the page loaded (Resource Timing), read before the browser closes."""
        try:
            self.resource_entries = self.env.unwrapped.page.evaluate(
                "() => performance.getEntriesByType('resource').map(e => e.name)")
        except Exception as e:  # noqa: BLE001  recorded
            self.resource_entries = ['<unavailable: %s>' % type(e).__name__]

    def final_task_info(self):
        return self.steps[-1]['verifier_only'] if len(self.steps) > 1 else OrderedDict()

    def record(self):
        return OrderedDict(request=REQUEST, label=self.label, seed=self.seed, kind=self.kind, browser_version=getattr(self, 'browser_version', None),
                           initial_resources=getattr(self, 'initial_resources', []), requests_after_reset=self.requests,
                           resource_timing_entries=getattr(self, 'resource_entries', None), steps=self.steps)


def feedback_decision(kind, decided_from_step, n_alternatives, evidence, consequential=None):
    """A decision the policy made from content of the observation returned at `decided_from_step`. Whether its target
    was actually revealed by an earlier action is MEASURED afterwards (verify_feedback), not asserted here."""
    return OrderedDict(kind=kind, feedback_dependent=True, decided_from_step=decided_from_step,
                       n_visible_alternatives=n_alternatives, evidence=evidence, consequential=consequential)


ACTION_BID = re.compile(r"^click\('([^']+)'\)$")


def verify_feedback(steps):
    """For every feedback-dependent click: the step at which its target bid became (continuously) visible, and whether
    it was absent from the reset observation, present when chosen, and both the revealing and the choosing action ran
    without an action error. Returns [(step index, measurement)] in order."""
    out = []
    for i, st in enumerate(steps):
        d = st.get('decision')
        if not d or not d.get('feedback_dependent'):
            continue
        m = ACTION_BID.match(st.get('action', ''))
        r = d.get('decided_from_step')
        row = OrderedDict(step=i, kind=d['kind'], target_bid=m.group(1) if m else None, decided_from_step=r)
        if m is None or r is None or not (0 <= r < i):
            row.update(verified=False, reason='no click target or decision step')
            out.append((i, row))
            continue
        present = [m.group(1) in bids(steps[j]['agent_visible']['axtree']) for j in range(r + 1)]
        first = r
        while first > 0 and present[first - 1]:
            first -= 1
        errors_ok = (steps[i]['agent_visible']['last_action_error'] == ''
                     and all(steps[j]['agent_visible']['last_action_error'] == '' for j in range(1, r + 1)))
        row.update(present_when_chosen=present[r], target_first_visible_at_step=first if present[r] else None,
                   absent_from_reset_observation=not present[0], action_errors_absent=errors_ok,
                   n_visible_alternatives=d.get('n_visible_alternatives'))
        row['verified'] = bool(present[r] and first >= 1 and not present[0] and errors_ok)
        out.append((i, row))
    return out


def run_booking(ep: Episode, worst: bool):
    """The scripted visible-information policy. worst=False books the best flight by the goal's criterion (positive
    trace); worst=True books the worst one after the identical prefix (negative trace)."""
    view = ep.reset()
    goal = parse_goal(view['goal'])
    notes = OrderedDict(goal=goal)
    if goal is None:
        notes['stopped'] = 'goal did not parse'
        return notes
    ax = view['axtree']
    for field, wanted in (('From:', goal['origin']), ('To:', goal['destination'])):
        tb = find_bid(ax, 'textbox', field)
        view, _ = ep.act("fill('%s', %r)" % (tb, wanted), OrderedDict(kind='type_goal_text', feedback_dependent=False,
                                                                        evidence='goal text %r into %r' % (wanted, field)))
        opts = autocomplete_options(view['axtree'])
        bid, label, n = choose_option(opts, wanted)
        notes['%s_options' % field.rstrip(':').lower()] = [l for _, l in opts]
        if bid is None:
            notes['stopped'] = 'no visible autocomplete option matched %r' % wanted
            return notes
        view, _ = ep.act("click('%s')" % bid, feedback_decision(
            'autocomplete_option', len(ep.steps) - 1, len(opts),
            'option %r chosen among %d options revealed by the previous fill (%d matching)' % (label, len(opts), n)))
        ax = view['axtree']
    date_bid = find_bid(ax, 'textbox', '')
    view, _ = ep.act("click('%s')" % date_bid, OrderedDict(kind='open_datepicker', feedback_dependent=False,
                                                           evidence='the empty date textbox'))
    cal = calendar_state(view['axtree'])
    if cal is None:
        notes['stopped'] = 'no datepicker visible'
        return notes
    notes['calendar_opened_at'] = '%d/%d' % (cal['month'], cal['year'])
    for _ in range(24):
        off = month_offset(cal['month'], cal['year'], goal['month'], goal['year'])
        if off == 0:
            break
        nav = cal['next_bid'] if off > 0 else cal['prev_bid']
        if nav is None:
            notes['stopped'] = 'month navigation unavailable'
            return notes
        view, _ = ep.act("click('%s')" % nav, feedback_decision(
            'month_navigation', len(ep.steps) - 1, 1 + (cal['prev_bid'] is not None) + (cal['next_bid'] is not None),
            'displayed month %d/%d vs goal %d/%d -> %s' % (cal['month'], cal['year'], goal['month'], goal['year'],
                                                         'Next' if off > 0 else 'Prev')))
        cal = calendar_state(view['axtree'])
        if cal is None:
            notes['stopped'] = 'datepicker closed during navigation'
            return notes
    day_bid = cal['days'].get(goal['day'])
    if day_bid is None:
        notes['stopped'] = 'goal day not visible'
        return notes
    view, _ = ep.act("click('%s')" % day_bid, feedback_decision(
        'calendar_day', len(ep.steps) - 1, len(cal['days']),
        'day link %d among %d links of the displayed month' % (goal['day'], len(cal['days']))))
    search = find_bid(view['axtree'], 'button', 'Search')
    view, _ = ep.act("click('%s')" % search, OrderedDict(kind='search', feedback_dependent=False,
                                                         evidence='the Search button'))
    rows = flights(view['axtree'])
    notes['flights_revealed'] = rows
    bid, tie = choose_flight(rows, goal['criterion'], worst=worst)
    notes['visible_tie'] = tie
    if bid is None:
        notes['stopped'] = 'no flights visible'
        return notes
    notes['chosen_bid'] = bid
    ep.act("click('%s')" % bid, feedback_decision(
        'flight_choice', len(ep.steps) - 1, len(rows),
        '%s %s flight by displayed %s among %d revealed results' % ('worst' if worst else 'best', goal['criterion'],
                                                                  'price' if goal['criterion'] == 'cheapest' else 'duration',
                                                                  len(rows)), consequential=True))
    return notes


def run_noop(ep: Episode, n: int):
    ep.reset()
    for _ in range(n):
        ep.act('noop()', OrderedDict(kind='noop', feedback_dependent=False, evidence='no-op'))
    return OrderedDict()


# ------------------------------------------------------------------ orchestration
def summarize(ep, notes):
    fin = ep.final_task_info()
    measured = [row for _, row in verify_feedback(ep.steps)]
    verified = [r for r in measured if r['verified']]
    errors = [s['step'] for s in ep.steps[1:] if s['agent_visible']['last_action_error']]
    return OrderedDict(seed=ep.seed, kind=ep.kind, n_actions=len(ep.steps) - 1, notes=notes,
                       feedback_decisions_measured=measured,
                       feedback_dependent_decisions=len(verified),
                       feedback_decision_kinds=[r['kind'] for r in verified],
                       steps_with_action_error=errors,
                       terminal=OrderedDict((k, fin.get(k)) for k in ('DONE_GLOBAL', 'RAW_REWARD_GLOBAL', 'REWARD_GLOBAL',
                                                                        'browsergym_reward', 'terminated', 'truncated')),
                       full_success=full_success(fin))


def isolation_ok(records):
    urls = [u for r in records for u in (list(r['initial_resources']) + list(r['requests_after_reset'])
                                         + list(r.get('resource_timing_entries') or []))]
    bad = sorted({u.split(':', 1)[0] for u in urls if not u.startswith(('file:', 'data:', 'about:'))})
    return not bad and bool(urls), OrderedDict(n_urls=len(urls), non_local_schemes=bad)


def dir_bytes(p: Path):
    return sum(f.stat().st_size for f in p.rglob('*') if f.is_file())


def publish(raw: Path, pub: Path):
    """Sanitized copies of every text/JSON record and byte copies of the screenshots, with a hash manifest."""
    pub.mkdir(parents=True, exist_ok=False)
    entries = OrderedDict()
    for f in sorted(raw.rglob('*')):
        if not f.is_file():
            continue
        rel = f.relative_to(raw)
        dst = pub / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        data = f.read_bytes()
        sanitized = False
        if f.suffix in ('.json', '.md', '.txt'):
            text = S.sanitize(data.decode())
            sanitized = text.encode() != data
            data = text.encode()
        dst.write_bytes(data)
        entries[str(rel)] = OrderedDict(raw_sha256=S.sha_file(f), published_sha256=S.sha_bytes(data), sanitized=sanitized)
    S.write_json_x(pub / 'publication_manifest.json', entries)
    return entries


def feasibility_md(v, checks, summaries, facts):
    lines = ['# DTR-REQ-015 feasibility verdict (DEVELOPMENT, no model): %s' % v['verdict'], '',
             'No-model qualification of `%s` (BrowserGym MiniWoB `book-flight`) under manifest `%s` (sha256 `%s`, '
             'copied as `manifest.json`).' % (facts['gym_id'], MANIFEST_REL, facts['manifest_sha256'][:16]), '',
             'Failed checks: %s' % (', '.join(v['failed_checks']) or 'none')]
    if facts.get('error'):
        lines += ['', 'Harness error: `%s`' % facts['error']]
    if facts.get('evaluation_error'):
        lines += ['', 'Evaluation error: `%s`' % facts['evaluation_error']]
    lines += ['', '| Check | Result |', '|---|---|'] + ['| %s | %s |' % (c, checks.get(c)) for c in QUALIFICATION_CHECKS]
    if summaries:
        lines += ['', '| Trace | Seed | Actions | Verified feedback-dependent decisions | DONE | RAW reward | Full success |',
                  '|---|---:|---:|---:|---|---:|---|']
        for s in summaries:
            lines.append('| %s | %d | %d | %d | %s | %s | %s |' % (
                s['label'], s['seed'], s['n_actions'], s['feedback_dependent_decisions'], s['terminal']['DONE_GLOBAL'],
                s['terminal']['RAW_REWARD_GLOBAL'], s['full_success']))
    if 'wall_seconds' in facts:
        lines += ['', 'Wall %.1f s (cap %d s); peak process-tree RSS %.2f GiB (cap %d GiB); raw artifacts %.1f MiB '
                  '(cap %d GiB).' % (facts['wall_seconds'], facts['caps']['wall_seconds'], facts['peak_rss_gib'],
                                     facts['caps']['peak_memory_gib'], facts['artifact_bytes'] / 2 ** 20,
                                     facts['caps']['artifact_gib'])]
    lines += ['', 'Scope: a scripted, no-model DEVELOPMENT mechanism check of one pinned task. It is not a model result, '
              'not a routing result and not a repository-repair claim; the fixed primary target is unchanged.', '']
    return '\n'.join(lines)


def compute_checks(manifest, sok, rok, summaries, records, error, wall, mon, art):
    """Every qualification check from the saved records (pure given its inputs); missing records fail closed."""
    caps = manifest['caps']
    by = {s['label']: s for s in summaries}
    recs = {spec['label']: rec for spec, rec in records}

    def reset_view(label):
        steps = (recs.get(label) or {}).get('steps') or []
        return steps[0]['agent_visible'] if steps and 'agent_visible' in steps[0] else None

    def shown(label):
        return [(r['duration_text'], r['price']) for r in (by[label]['notes'].get('flights_revealed') or [])]

    a, b, other = reset_view('reset_repeat_a'), reset_view('reset_repeat_b'), reset_view('reset_other_seed')
    pos, neg, noop = by.get('primary_positive'), by.get('negative'), by.get('noop')
    facts = OrderedDict(
        repeat_goal_equal=bool(a and b and a['goal'] == b['goal']),
        repeat_axtree_equal=bool(a and b and a['axtree'] == b['axtree']),
        other_seed_goal_differs=bool(a and other and other['goal'] != a['goal']),
        positive_negative_goal_equal=bool(pos and neg and pos['notes'].get('goal') == neg['notes'].get('goal')),
        positive_negative_results_equal=bool(pos and neg and shown('primary_positive')
                                             and shown('primary_positive') == shown('negative')))
    checks = OrderedDict()
    checks['sources_pinned'] = sok
    checks['runtime_pinned'] = rok
    checks['reset_reproducible'] = all(facts.values())
    checks['feedback_dependent_decisions'] = bool(
        pos is not None and pos['feedback_dependent_decisions'] >= manifest['min_feedback_dependent_decisions']
        and 'flight_choice' in pos['feedback_decision_kinds'])
    checks['positive_full_success'] = bool(pos is not None and pos['full_success'] and not pos['steps_with_action_error'])
    checks['negative_fails_predicate'] = bool(neg is not None and neg['terminal']['DONE_GLOBAL'] is True
                                              and not neg['full_success'] and not neg['steps_with_action_error'])
    noop_steps = next((p.get('noop_steps') for p in manifest['plan'] if p['label'] == 'noop'), None)
    checks['noop_fails_predicate'] = bool(noop is not None and noop['n_actions'] == noop_steps
                                          and not noop['steps_with_action_error'] and not noop['full_success'])
    iso_ok, iso = isolation_ok([r for _, r in records])
    checks['browser_isolation'] = iso_ok and manifest['environment']['pw_context_kwargs'].get('offline') is True
    checks['no_harness_error'] = error is None and len(records) == len(manifest['plan'])
    checks['resources_within_caps'] = (wall <= caps['wall_seconds'] and not mon.breached.is_set() and mon.samples > 0
                                       and mon.errors == 0 and art <= caps['artifact_gib'] * GIB)
    return checks, facts, iso


def main(argv=None, root=ROOT):
    ap = argparse.ArgumentParser(description='DTR-REQ-015 no-model MiniWoB book-flight qualification')
    ap.add_argument('--admission-only', action='store_true', help='print the host/source/runtime gates; start nothing')
    args = ap.parse_args(argv)
    manifest_bytes = (root / MANIFEST_REL).read_bytes()
    manifest, msha = json.loads(manifest_bytes), S.sha_bytes(manifest_bytes)
    out = manifest['outputs']
    raw, pub = root / out['raw'], root / out['published']
    sok, sdet = check_sources(manifest, root)
    rok, rdet = check_runtime(manifest)
    hok, hdet = host_gates(manifest, root)
    adm = OrderedDict(request=REQUEST, status='DEVELOPMENT', manifest=MANIFEST_REL, manifest_sha256=msha, utc=S.utc(),
                      sources=OrderedDict(ok=sok, detail=sdet), runtime=OrderedDict(ok=rok, detail=rdet),
                      host=OrderedDict(ok=hok, detail=hdet), admitted=sok and rok and hok)
    if args.admission_only:
        print(json.dumps(S.sanitize(adm), indent=1, default=str))
        return 0 if adm['admitted'] else 1
    if raw.exists() or pub.exists():
        print('DTR-REQ-015 is single-shot: %s or %s exists' % (out['raw'], out['published']), file=sys.stderr)
        return 3
    if not (sok and rok):
        print('DTR-REQ-015 refused before its namespace (nothing consumed): the source or runtime pins did not pass: %s'
              % json.dumps(S.sanitize(OrderedDict(sources=sdet, runtime=rdet)), default=str), file=sys.stderr)
        return 3
    raw.mkdir(parents=True)
    with open(raw / 'manifest.json', 'xb') as fh:                 # the immutable specification, byte copy
        fh.write(manifest_bytes)
    S.write_json_x(raw / 'admission.json', adm)
    caps = manifest['caps']
    start = time.time()
    facts = OrderedDict(request=REQUEST, status='DEVELOPMENT', kind=manifest['kind'], gym_id=manifest['task']['gym_id'],
                        manifest=MANIFEST_REL, manifest_sha256=msha, caps=caps, started_utc=S.utc(start),
                        host=OrderedDict(platform=platform.platform(), machine=platform.machine(),
                                         timezone=time.strftime('%Z'), tz_env=os.environ.get('TZ')))
    summaries, records = [], []
    if not hok:
        v = verdict(False, {})
        facts.update(verdict=v, host_gates=hdet, finished_utc=S.utc())
        S.write_json_x(raw / 'verdict.json', facts)
        (raw / 'feasibility.md').write_text(S.sanitize(feasibility_md(v, {}, [], facts)))
        publish(raw, pub)
        print(json.dumps(S.sanitize(v)))
        return 2
    env_vars = manifest['environment']['env']
    clean, removed = S.scrub_env(dict(os.environ))
    os.environ.clear()
    os.environ.update(clean)
    os.environ['MINIWOB_URL'] = (root / env_vars['MINIWOB_URL_under_repo']).as_uri() + '/'
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(root / env_vars['PLAYWRIGHT_BROWSERS_PATH_under_repo'])
    facts['environment_variables_removed'] = removed
    mon = Monitor(caps['peak_memory_gib'] * GIB)
    mon.start()
    deadline = start + caps['wall_seconds']
    error = None
    try:
        for spec in manifest['plan']:
            env = make_env(manifest)
            ep = Episode(env, spec['seed'], spec['kind'], spec['label'], raw, deadline, mon,
                         manifest['max_steps_per_episode'])
            notes = OrderedDict(stopped='episode raised before completion')
            try:
                if spec['kind'] == 'noop':
                    notes = run_noop(ep, spec['noop_steps'])
                elif spec['kind'] == 'reset_only':
                    notes = OrderedDict(goal=parse_goal(ep.reset()['goal']))
                else:
                    notes = run_booking(ep, worst=spec['kind'] == 'negative')
            finally:
                ep.capture_resources()
                try:
                    env.close()
                except Exception as e:  # noqa: BLE001  recorded; never hides the episode's own outcome
                    notes['env_close_error'] = '%s: %s' % (type(e).__name__, str(e)[:300])
                rec = ep.record()
                S.write_json_x(raw / ('trace_%s_seed%d.json' % (spec['label'], spec['seed'])), rec)
                records.append((spec, rec))
                summaries.append(OrderedDict(label=spec['label'], **summarize(ep, notes)))
    except CapExceeded as e:
        error = 'cap: %s' % e
    except Exception as e:  # noqa: BLE001  recorded; the verdict names the failure
        error = '%s: %s' % (type(e).__name__, str(e)[:500])
    finally:
        mon.stop.set()
        mon.join(timeout=5)
    wall = time.time() - start
    art = dir_bytes(raw)
    try:
        checks, repro, iso = compute_checks(manifest, sok, rok, summaries, records, error, wall, mon, art)
        evaluation_error = None
    except Exception as e:  # noqa: BLE001  the verdict and the one-page record are still written
        checks, repro, iso = OrderedDict(), None, None
        evaluation_error = '%s: %s' % (type(e).__name__, str(e)[:500])
    v = verdict(True, checks)
    facts.update(finished_utc=S.utc(), wall_seconds=round(wall, 2), error=error, evaluation_error=evaluation_error,
                 checks=checks, verdict=v, reset_reproducibility=repro, isolation=iso,
                 peak_rss_gib=mon.peak_kb * 1024 / GIB, memory_samples=mon.samples, memory_sample_errors=mon.errors,
                 artifact_bytes=art, summaries=summaries,
                 positive_robustness=OrderedDict(
                     (s['label'], OrderedDict(full_success=s['full_success'],
                                              criterion=(s['notes'].get('goal') or {}).get('criterion'),
                                              visible_tie=s['notes'].get('visible_tie'), stopped=s['notes'].get('stopped')))
                     for s in summaries if s['kind'] == 'positive'))
    S.write_json_x(raw / 'verdict.json', facts)
    (raw / 'feasibility.md').write_text(S.sanitize(feasibility_md(v, checks, summaries, facts)))
    publish(raw, pub)
    hits = S.username_hits(pub)
    print(json.dumps(S.sanitize(OrderedDict(verdict=v, wall_seconds=facts['wall_seconds'], error=error,
                                            evaluation_error=evaluation_error, username_hits=hits))))
    return 0 if not hits else 4


if __name__ == '__main__':
    sys.exit(main())
