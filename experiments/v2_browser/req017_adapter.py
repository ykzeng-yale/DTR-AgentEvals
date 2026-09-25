"""DTR-REQ-017 versioned adapter (lead c648a84, docs/theory_feedback_20260925_req016_decision.md).

Exactly ONE change from the frozen REQ-016 adapter (experiments/v2_browser/req016_adapter.py, imported and never
edited): parse_action also accepts the bracketed display form of a CURRENT-tree id, '[19]', and canonicalizes it to the
bare id '19' before anything reaches BrowserGym. Everything else is the REQ-016 object itself (the same prompt bytes,
model view, history feedback, leak guard, request body, allowed functions, causes): unknown ids, malformed or nested
brackets, ids seen only in history, forbidden functions, arguments and 2-4 action lines are still rejected, and nothing
rejected is executed.
"""
from __future__ import annotations

import re

import req016_adapter as BASE

REQUEST = 'DTR-REQ-017'
BASE_REQUEST = BASE.REQUEST

# unchanged REQ-016 objects (the same objects, not copies)
ALLOWED = BASE.ALLOWED
MAX_FILL_CHARS = BASE.MAX_FILL_CHARS
EXCERPT_CHARS = BASE.EXCERPT_CHARS
SYSTEM_PROMPT = BASE.SYSTEM_PROMPT
USER_TEMPLATE = BASE.USER_TEMPLATE
FORBIDDEN_MARKERS = BASE.FORBIDDEN_MARKERS
CAUSES = BASE.CAUSES
model_view = BASE.model_view
error_excerpt = BASE.error_excerpt
fill_text = BASE.fill_text
history_lines = BASE.history_lines
build_messages = BASE.build_messages
leak_problems = BASE.leak_problems
tree_bids = BASE.tree_bids
canonical_body = BASE.canonical_body

BRACKETED = re.compile(r'\[([^\[\]\s]+)\]')     # (fullmatch) exactly one pair of brackets around a non-empty id, no whitespace
CANONICALIZED = 'bracketed current-tree id canonicalized'


def canonical_bid(bid: str, axtree: str):
    """The bare current-tree id for `bid` ('19' or '[19]'), or None when it is not a current-tree id."""
    current = tree_bids(axtree)
    if bid in current:
        return bid
    m = BRACKETED.fullmatch(bid)                    # fullmatch: '$' alone would also accept a trailing newline
    return m.group(1) if m and m.group(1) in current else None


def parse_action(reply: str, axtree: str):
    """REQ-016 parse_action with the single REQ-017 change: an unknown_bid whose argument is '[<id>]' with <id> in the
    current tree is re-parsed with the bare id. -> (canonical action or None, cause or None, detail)."""
    action, cause, detail = BASE.parse_action(reply, axtree)
    if cause != 'unknown_bid':
        return action, cause, detail
    calls = [c for c in (BASE._candidate(l) for l in (reply or '').splitlines()) if c is not None]
    bid = calls[0].args[0].value                     # BASE reached the bid check: one call, string args, click/fill
    bare = canonical_bid(bid, axtree)
    if bare is None or bare == bid:
        return action, cause, detail
    values = [a.value for a in calls[0].args]
    name = calls[0].func.id
    if name == 'click':
        return 'click(%r)' % bare, None, CANONICALIZED
    if len(values[1]) > MAX_FILL_CHARS:
        return None, 'fill_too_long', '%d characters' % len(values[1])
    return 'fill(%r, %r)' % (bare, values[1]), None, CANONICALIZED
