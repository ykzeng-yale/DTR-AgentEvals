"""DTR-REQ-016 restricted model adapter (lead 97656b5, docs/theory_feedback_20260925_req015_decision.md).

Standard library only. It decides everything the model sees and everything it may do:

* model_view(obs, flatten) keeps ONLY the goal, the flattened accessibility tree and the last action error of a
  BrowserGym observation; the DOM, URL, screenshot, element properties, pages, chat, rewards, DONE and every
  verifier field are never read.
* build_messages(view, history, remaining) is the frozen prompt (SYSTEM_PROMPT, USER_TEMPLATE): the goal, the tree,
  the prior actions with their errors, and the remaining logical-action budget.
* parse_action(reply, axtree) accepts exactly one action line: click('<bid>'), fill('<bid>', '<text>') or noop(),
  with a bid present in the current tree, and returns the canonical action string. Everything else (no action,
  several actions, any other function such as goto/new_tab/tab_focus/upload_file/scroll/press/send_msg_to_user,
  extra or keyword arguments, non-string arguments, code, an unknown bid) is an invalid action with a declared cause;
  it is not executed.
* leak_problems(body) is the dispatch guard: a request body containing any forbidden marker is never sent.

Nothing here is tuned after seeing model outputs; the committed manifest records the sha256 of this file and of the
prompt text before any call.
"""
from __future__ import annotations

import ast
import json
import re

REQUEST = 'DTR-REQ-016'
ALLOWED = ('click', 'fill', 'noop')
MAX_FILL_CHARS = 200
EXCERPT_CHARS = 160

SYSTEM_PROMPT = (
    "You are a web agent. You operate one web page through its accessibility tree. Every element you can act on "
    "has an id in square brackets, for example [19].\n"
    "Each reply must end with exactly one action, alone on its own line, chosen from:\n"
    "click('<id>')\n"
    "fill('<id>', '<text>')\n"
    "noop()\n"
    "Use only ids that appear in the current accessibility tree. No other function and no second action is "
    "allowed. You may write one short line of reasoning before the action.")

USER_TEMPLATE = (
    "Goal: {goal}\n\n"
    "Current page (accessibility tree):\n{axtree}\n\n"
    "Previous actions (oldest first):\n{history}\n\n"
    "Actions remaining: {remaining}\n\n"
    "Reply with your next action.")

FORBIDDEN_MARKERS = ('file:', 'data-price', 'data-duration', 'data-result', 'WOB_', 'RAW_REWARD', 'REWARD_GLOBAL',
                     'DONE_GLOBAL', 'core.endEpisode', 'book-flight.html', 'miniwob', 'screenshot', 'dom_object')
CAUSES = ('no_action', 'multiple_actions', 'forbidden_function', 'bad_arguments', 'unknown_bid', 'fill_too_long')
BID_TOKEN = re.compile(r'^\t*\[([^\]\s]+)\] ', re.M)   # the bid that leads a flattened-tree line
FENCE = re.compile(r'^`{3,}\w*$')


def model_view(obs, flatten):
    """The only three observation fields the model sees; `flatten` turns obs['axtree_object'] into text."""
    return dict(goal=str(obs['goal']), axtree=flatten(obs['axtree_object']),
                last_action_error=str(obs.get('last_action_error') or ''))


def error_excerpt(err: str) -> str:
    """What the model sees of a BrowserGym action error: its first line, without any <...> markup (Playwright call logs
    can quote element HTML with data-* attributes), at most EXCERPT_CHARS characters."""
    first = (err or '').strip().splitlines()[0] if (err or '').strip() else ''
    return re.sub(r'<[^>]*>?', '', first)[:EXCERPT_CHARS]


def fill_text(action: str) -> str:
    """The text of a canonical fill('<bid>', '<text>') action."""
    return ast.parse(action, mode='eval').body.args[1].value


def history_lines(history):
    if not history:
        return '(none)'
    rows = []
    for i, h in enumerate(history, 1):
        if h.get('action') is None:
            rows.append('%d. invalid reply (%s): not executed' % (i, h['cause']))
        elif h.get('error'):
            rows.append('%d. %s -> error: %s' % (i, h['action'], error_excerpt(h['error'])))
        else:
            rows.append('%d. %s -> ok' % (i, h['action']))
    return '\n'.join(rows)


def build_messages(view, history, remaining):
    user = USER_TEMPLATE.format(goal=view['goal'], axtree=view['axtree'], history=history_lines(history),
                                remaining=remaining)
    return [dict(role='system', content=SYSTEM_PROMPT), dict(role='user', content=user)]


def leak_problems(text: str, typed=()):
    """Forbidden markers in the unmodified text sent to the model (an empty list means it may be dispatched). A marker
    is exempt only when the model itself typed a fill value containing it (its own text echoed back is not a leak)."""
    return [m for m in FORBIDDEN_MARKERS if m in text and not any(m in t for t in typed if t)]


def tree_bids(axtree: str):
    return set(BID_TOKEN.findall(axtree))


def _candidate(line: str):
    """A line that is exactly one call of a bare name (after trimming backticks and an optional 'Action:' prefix):
    returns the ast.Call, or None."""
    s = line.strip().strip('`').strip()
    if s.lower().startswith('action:'):
        s = s[7:].strip().strip('`').strip()
    if not s or FENCE.match(s):
        return None
    try:
        node = ast.parse(s, mode='eval').body
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None
    return node if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) else None


def parse_action(reply: str, axtree: str):
    """-> (canonical action or None, cause or None, detail). Exactly one action line is accepted."""
    calls = [c for c in (_candidate(l) for l in (reply or '').splitlines()) if c is not None]
    if not calls:
        return None, 'no_action', 'no line is a single function call'
    if len(calls) > 1:
        return None, 'multiple_actions', '%d action lines' % len(calls)
    call = calls[0]
    name = call.func.id
    if name not in ALLOWED:
        return None, 'forbidden_function', name
    args = call.args
    if call.keywords or any(isinstance(a, ast.Starred) for a in args):
        return None, 'bad_arguments', 'keyword or starred arguments'
    if not all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in args):
        return None, 'bad_arguments', 'arguments must be string literals'
    values = [a.value for a in args]
    want = dict(click=1, fill=2, noop=0)[name]
    if len(values) != want:
        return None, 'bad_arguments', '%s takes %d argument(s), got %d' % (name, want, len(values))
    if name == 'noop':
        return 'noop()', None, ''
    bid = values[0]
    if bid not in tree_bids(axtree):
        return None, 'unknown_bid', bid[:40]
    if name == 'click':
        return 'click(%r)' % bid, None, ''
    if len(values[1]) > MAX_FILL_CHARS:
        return None, 'fill_too_long', '%d characters' % len(values[1])
    return 'fill(%r, %r)' % (bid, values[1]), None, ''


def canonical_body(alias, messages, settings):
    """The exact JSON request body sent to the OpenAI-compatible endpoint (sorted keys; the receipt hashes it)."""
    body = dict(model=alias, messages=messages, temperature=settings['temperature'],
                max_tokens=settings['max_tokens'], stream=False)
    return json.dumps(body, sort_keys=True, ensure_ascii=False)
