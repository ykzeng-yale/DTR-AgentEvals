"""Pilot gate report (protocol.md section 6). Reads results/code_routing/pilot/episodes.jsonl (or the mock one with --mock)."""
from __future__ import annotations
import argparse, json
from collections import Counter

import numpy as np

from common import RESULTS, ROOT, load_config


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--mock', action='store_true'); a = ap.parse_args()
    cfg = load_config(); base = (ROOT / 'work' / 'code_routing_mock') if a.mock else RESULTS
    rows = [json.loads(l) for l in (base / 'pilot' / 'episodes.jsonl').read_text().splitlines() if l.strip()]
    ok = list({r['episode_id']: r for r in rows if not r.get('error')}.values())
    out = ['# Pilot gate' + (' **[MOCK: meaningless numbers]**' if a.mock else ''), '',
           'episodes %d, tasks %d, infrastructure errors %d' % (len(rows), len({r['task_uid'] for r in rows}), len(rows) - len(ok)), '',
           '| first model | n | validated at t=0 | first candidate passes HIDDEN tests | final success | mean completion tokens at t=0 |', '|---|---:|---:|---:|---:|---:|']
    gate = {}
    for a0, name in ((0, 'small'), (1, 'large')):
        g = [r for r in ok if r['decisions'][0]['a'] == a0]
        if not g:
            continue
        first = float(np.mean([r['success_first_candidate'] for r in g])); gate[name] = first
        out.append('| %s | %d | %.3f | %.3f | %.3f | %.0f |' % (name, len(g), np.mean([r['decisions'][0]['validation']['passed'] for r in g]), first,
                                                             np.mean([r['success'] for r in g]), np.mean([r['decisions'][0]['completion_tokens'] for r in g])))
    nd = Counter(r['n_decisions'] for r in ok); failed0 = [r for r in ok if r['n_decisions'] > 1]; passed0 = [r for r in ok if r['n_decisions'] == 1]
    calls = sum(r['n_decisions'] for r in ok); toks = sum(r['completion_tokens'] for r in ok); secs = sum(r['agent_seconds'] for r in ok)
    trunc = np.mean([d['finish'] == 'length' for r in ok for d in r['decisions']])
    vt = sum(r.get('validation_timeouts', 0) for r in ok)
    out += ['', 'decisions per episode: %s  ->  P(t=1 eligible) = %.3f, P(t=2 eligible) = %.3f' % (dict(sorted(nd.items())), 1 - nd[1] / len(ok), nd[3] / len(ok)),
            'visible-test FALSE ALARM rate, P(first candidate hidden-correct | failed validation) = %.3f (n=%d)' % (np.mean([r['success_first_candidate'] for r in failed0]) if failed0 else float('nan'), len(failed0)),
            'visible-test FALSE PASS rate, P(hidden-wrong | validated at t=0) = %.3f (n=%d)' % (1 - np.mean([r['success'] for r in passed0]) if passed0 else float('nan'), len(passed0)),
            'failure classes at t>=1: %s' % dict(Counter(d['state']['fail_class'] for r in ok for d in r['decisions'] if d['t'] > 0)),
            'truncated generations (finish=length): %.3f; validation timeouts: %d; hidden-test timeouts: %d; episodes with hack flags: %d' % (
                trunc, vt, sum(bool(r.get('verify_timed_out')) for r in ok), sum(bool(r.get('hack_flags')) for r in ok)),
            'episodes that began under foreign GPU load: %d of %d' % (sum(bool(r.get('foreign_gpu_load_at_start')) for r in ok), len(ok)), '',
            'throughput: %.2f calls/episode, %.0f completion tokens/episode, %.1f agent-seconds/episode (sum over %d workers)' % (calls / len(ok), toks / len(ok), secs / len(ok), cfg['workers'])]
    per_ep = secs / len(ok) / cfg['workers']
    n_log = 561 * cfg['runs_per_task']; n_live = 330 * 6 * cfg['live_runs_per_task']
    out += ['projected wall-clock at this rate: randomized log %d episodes = %.1f h; live %d episodes = %.1f h; branch 800 continuations = %.1f h' % (
        n_log, n_log * per_ep / 3600, n_live, n_live * per_ep / 3600, 800 * per_ep / 3600), '',
        '## Gate', '', 'first-call hidden-test success within 15-85%% for both models: %s  (%s)' % (
            all(0.15 <= v <= 0.85 for v in gate.values()), ', '.join('%s %.3f' % kv for kv in gate.items())),
        'large better than small on first call: %s (size is a descriptor, not a claim; the pair is frozen either way)' % (gate.get('large', 0) > gate.get('small', 0)), '']
    (base / 'pilot' / 'pilot_gate.md').write_text('\n'.join(out)); print('\n'.join(out))


if __name__ == '__main__':
    main()
