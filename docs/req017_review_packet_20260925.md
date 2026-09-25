# DTR-REQ-017 review packet: versioned bracket-id adapter (frozen, NO model call)

**Host time:** 2026-09-25T20:26Z (`date -u`). **Frozen build:** worker commit `0127f3a`. **Manifest:**
[`configs/v2_req017_7b_bracket_pilot_20260925.json`](../configs/v2_req017_7b_bracket_pilot_20260925.json), sha256
`72e078df363b8ce35d52d29a4ebd3a8aa2b9a86151b64639b476f0ce1af87ffc`. **Lead request:**
[`c648a84`](theory_feedback_20260925_req016_decision.md).

**Status:** built, reviewed and admitted. **No model request has been made**, and seeds 300–303 have never been used.
The pilot is held until you release it.

## To release the one four-seed pilot (only if you accept this source)

Publish a lead commit on `main` after `0127f3a`. Its subject must start with `lead:`, and its message must contain this
line exactly once, outside any fenced block:

    RELEASE DTR-REQ-017 manifest_sha256=72e078df363b8ce35d52d29a4ebd3a8aa2b9a86151b64639b476f0ce1af87ffc

The runner accepts only the full 40-hex sha of that commit. It checks that:
- the commit is on HEAD and on the actual remote main;
- it descends from the manifest freeze;
- no later lead commit carries `REVOKE DTR-REQ-017` or `HOLD DTR-REQ-017`;
- the manifest sources are unchanged since the release;
- the manifest being run still has this sha256.

To withdraw a release, add a lead commit with a `REVOKE DTR-REQ-017` line. A commit without the exact line, including
your hold commit `c648a84`, is refused, and the real repository test proves this.

## The single interface change (the complete new logic of `req017_adapter.py`)

Every other name in `req017_adapter` is the REQ-016 object itself: the same prompt bytes (sha `119a3984…`), model view,
history feedback, leak guard, request body, allowed functions and causes. Fixture `test_only_parse_action_differs_from_req016`
checks object identity.

```python
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
```

## Manifest differences from REQ-016 (key level)

- **Identical:** assignment (7B, GGUF `87a3665c…`), model_source, lead_pins (llama.cpp `4fea119`), settings (T 0,
  1536 tokens, 16,384 context), accounting, task (book-flight, full-success predicate), capacity, status.
- **Changed, as declared:**
  - `seeds` 200–207 → **300–303**; `caps.batch_wall_s` 5400 → **2700** (all other caps equal: 16/32, 2 GiB).
  - `browser.entry` → `req017_episodes.py` (all other browser fields equal).
  - `statuses.COMPLETED` → "every manifest seed (four)".
  - `serving.code` holder label → REQ-017; `host_gates` → REQ-016/REQ-017 processes plus the release gate.
  - Plus the request/lead/source ids, hypothesis, adapter (bound hashes and the grammar addition), scoring,
    sources (adding the REQ-017 files, and two modules REQ-016 imported but did not list), outputs,
    not_authorized, rehearsals and scope.
- **Added:** `release_gate`, `discriminator`, `req016` (byte bindings) and `inherited_labels`.
- **Discriminator (predeclared):**
  1. At least one executed **click/fill**. An executed noop does not count; canonicalized executions are reported.
  2. At least one full success.
  Zero full successes ends this local 7B browser path; a positive pilot stays DEVELOPMENT and returns to you.

## Fixtures and checks (all no-model)

- **`tests/test_req017_adapter.py`: 58 pass.**
  - On all 68 saved REQ-015 trees, every current bid gives the same single valid action in bare and bracketed form
    (more than 1,000 cases). The frozen REQ-016 parser still rejects the bracketed form.
  - Rejections: unknown, nested and malformed ids (including a trailing newline, a tab or a space), history-only ids,
    forbidden functions, bad arguments, and 2–4 action lines.
  - Execution level: only the first canonical action reaches the fake browser.
  - Discriminator counts ignore noop.
  - Gate and argv attacks, the child guard, a manifest swap after the gate (BLOCKED before serving), and no stale
    console line.
  - REQ-016 sources and all 292 archive files are byte-identical.
- **Non-evidential parser replay of the 128 saved REQ-016 replies** (re-parses text; nothing is executed or rescored):
  the 62 single-line bracketed replies become canonical `fill('19', …)`, and the 66 multi-action replies stay
  `multiple_actions`.
- **Full suite:** 1525 passed. REQ-016 and REQ-017 tests pass in both orders, together with the multiprocessing
  coverage tests.
- **Stub rehearsals** (development seeds 1000–1001, local stub endpoint, real offline browser):
  - `fill('[19]', …)` and `click('[27]')` executed as `fill('19', …)` and `click('27')` with no action error;
    unknown and multi-action replies were not executed.
  - The child refused pilot-seed and pilot-port configs without a release (exit 3).
  - Final-code run at 20:18:58Z.
- **Reviews:** three adversarial passes found:
  - one gate blocker: the first gate accepted `c648a84` by substring-matching its diff;
  - two argv bypasses: an empty `--watchdog`, and abbreviated or `=` forms of `--run`;
  - hardening items.

  All were repaired before this freeze. See the manifest's `development_rehearsals`.
- **Admission on the committed tree (2026-09-25T20:26Z):** admitted. Pins and sources passed (23), the browser runtime and action
  set (click/fill/noop) passed, the model hashes passed, and the REQ-016 archive checked all 292 files. No conflicts,
  peer lease none, physical memory 62 % free, host disk 68.2 GiB. The same `--lead-release <c648a84>` launch was
  refused before any namespace.

## Declared residuals

- **Lead authority is by convention.** Lead and worker share one git identity, so the check is a `lead:` subject on
  the published remote main, not a signature.
- **Inherited REQ-016 labels** appear in some console messages and admission keys, and in the admission scratch path
  (`inherited_labels`).
- **Canonicalization note field:** a canonicalized, executed step keeps `invalid_cause` null and carries its note in
  the inherited field `invalid_detail`.
