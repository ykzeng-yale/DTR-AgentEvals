"""DTR-REQ-016 episode child: the eight fixed-backend 7B episodes on MiniWoB book-flight, one per seed, in order.

Started only by req016_screen.py (the supervising parent), in the pinned REQ-015 BrowserGym venv:

    work/venvs/browsergym_9e779f0/bin/python experiments/v2_browser/req016_episodes.py --admission CONFIG
    work/venvs/browsergym_9e779f0/bin/python experiments/v2_browser/req016_episodes.py --run CONFIG

The model sees only what req016_adapter builds; the environment executes only click/fill/noop (a BrowserGym custom
action set without multiaction, strict parsing). Every request body is written durably BEFORE dispatch and every
outcome after it; every step (pre-action observation shown to the model, reply, parse result, executed action,
action error, verifier-only fields) is appended durably as it happens. The verifier fields are recorded and never
reach the model. No rescue, re-prompting rule change or scripted help exists here.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import signal
import sys
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
for _p in (HERE, ROOT / 'experiments/v2_adapter'):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import req010_sentinel as S  # noqa: E402  stdlib-only helpers
import req016_adapter as AD  # noqa: E402

REQUEST = AD.REQUEST
TRANSPORT_RETRYABLE = 'transport'      # connection error, timeout or HTTP 5xx: one more attempt of the same call
CAUSES = ('full_success', 'wrong_booking', 'core_timeout', 'page_or_url_changed', 'logical_budget_exhausted',
          'physical_budget_exhausted', 'context_limit', 'transport_failure', 'http_error', 'deadline',
          'stopped_by_supervisor', 'leak_guard', 'harness_error', 'not_started')


BATCH_STOP_CAUSES = ('deadline', 'leak_guard', 'transport_failure', 'http_error', 'harness_error', 'artifact_cap',
                     'stopped_by_supervisor')


class Stopped(BaseException):
    """The supervisor asked this child to stop (SIGTERM/SIGINT), or the supervising parent is gone."""


STOP = dict(requested=False, reason=None, in_transport=False, parent=None)


def on_stop(signum, _frame):
    """Only records the request. It raises only while a model request is in flight (plain urllib, safe to abandon);
    Playwright calls are never interrupted: the episode loop checks the flag at its safe points."""
    STOP.update(requested=True, reason='signal %d from the supervisor' % signum)
    if STOP['in_transport']:
        STOP['in_transport'] = False
        raise Stopped(STOP['reason'])


def check_stop():
    if STOP['parent'] is not None and os.getppid() != STOP['parent'] and not STOP['requested']:
        STOP.update(requested=True, reason='the supervising parent is gone')
    if STOP['requested']:
        raise Stopped(STOP['reason'])


def append_line(path, obj):
    with open(path, 'a') as fh:
        fh.write(json.dumps(obj, default=str) + '\n')
        fh.flush()
        os.fsync(fh.fileno())


def write_x(path, obj):
    """Write-once, fsync-ed JSON (not sanitized here; publication sanitizes)."""
    with open(path, 'x') as fh:
        fh.write(json.dumps(obj, indent=1, default=str) + '\n')
        fh.flush()
        os.fsync(fh.fileno())


# ------------------------------------------------------------------ transport
class Transport:
    """One POST per physical attempt to the owned llama.cpp server's OpenAI-compatible endpoint."""

    def __init__(self, url, timeout_s):
        self.url, self.timeout_s = url, timeout_s
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # never an environment proxy

    def __call__(self, body_text, timeout):
        req = urllib.request.Request(self.url, data=body_text.encode(), method='POST',
                                     headers={'Content-Type': 'application/json'})
        t0 = time.time()
        STOP['in_transport'] = True
        try:
            if STOP['requested']:
                raise Stopped(STOP['reason'])
            with self.opener.open(req, timeout=max(1.0, min(self.timeout_s, timeout))) as r:
                raw = r.read().decode()
                return OrderedDict(kind='response', http_status=r.status, body=raw, seconds=round(time.time() - t0, 3))
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors='replace')
            return OrderedDict(kind='http_error', http_status=e.code, body=raw, seconds=round(time.time() - t0, 3))
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, http.client.HTTPException,
                ValueError) as e:
            return OrderedDict(kind='transport_error', http_status=None, body='%s: %s' % (type(e).__name__, str(e)[:300]),
                               seconds=round(time.time() - t0, 3))
        finally:
            STOP['in_transport'] = False


def classify_transport(res):
    """-> ('ok', content, usage, finish) | ('retry', reason) | ('context_limit', detail) | ('http_error', detail)."""
    if res['kind'] == 'transport_error':
        return ('retry', res['body'])
    status = res['http_status']
    if res['kind'] == 'http_error':
        if status is not None and status >= 500:
            return ('retry', 'HTTP %s' % status)
        if status == 400 and ('context' in res['body'].lower()):
            return ('context_limit', res['body'][:300])
        return ('http_error', 'HTTP %s: %s' % (status, res['body'][:300]))
    try:
        data = json.loads(res['body'])
        choice = data['choices'][0]
        return ('ok', choice['message'].get('content') or '', data.get('usage') or {}, choice.get('finish_reason'))
    except (ValueError, KeyError, IndexError, TypeError) as e:
        return ('http_error', 'unparsable response: %s' % type(e).__name__)


# ------------------------------------------------------------------ one episode
def terminal_cause(task_info, info_error):
    """The outcome of a terminated episode from the verifier-only fields."""
    if info_error:
        return 'page_or_url_changed'
    if task_info.get('DONE_GLOBAL') and task_info.get('RAW_REWARD_GLOBAL') == 1:
        return 'full_success'
    if task_info.get('DONE_GLOBAL') and task_info.get('REWARD_REASON') == 'timed out':
        return 'core_timeout'
    if task_info.get('DONE_GLOBAL'):
        return 'wrong_booking'
    return 'page_or_url_changed'


def run_episode(seed, cfg, env, transport, out_dir, flatten, clock=time.time, shot=None):
    """Runs one seeded episode and returns its summary; every call/step is written durably as it happens. A supervisor
    stop propagates as Stopped carrying the partial summary."""
    partial = {}
    try:
        return _run_episode(seed, cfg, env, transport, out_dir, flatten, clock, shot, partial)
    except Stopped as e:
        e.partial = partial.get('summary')
        raise


def _run_episode(seed, cfg, env, transport, out_dir, flatten, clock, shot, partial):
    caps, settings = cfg['caps'], cfg['settings']
    out_dir.mkdir(parents=True, exist_ok=False)
    rec_dir = out_dir / 'receipts'
    rec_dir.mkdir()
    steps_path = out_dir / 'steps.jsonl'
    t_start = clock()
    summary = OrderedDict(request=REQUEST, seed=seed, started_utc=S.utc(t_start), cause=None, full_success=False,
                          logical_calls=0, physical_attempts=0, executed_actions=0, invalid_replies=0,
                          invalid_causes=OrderedDict(), action_errors=0, prompt_tokens=0, completion_tokens=0,
                          usage_unknown_calls=0, terminal=None, error=None)
    partial['summary'] = summary
    history, typed = [], []
    check_stop()
    obs, info = env.reset(seed=seed)
    view = AD.model_view(obs, flatten)
    append_line(steps_path, OrderedDict(step=0, kind='reset', utc=S.utc(clock()), model_view=view,
                                        verifier_only=OrderedDict(task_info=info.get('task_info')),
                                        screenshot=shot(obs, 0) if shot else None))
    done = False
    while not done:
        if summary['logical_calls'] >= caps['logical_per_episode']:
            summary['cause'] = 'logical_budget_exhausted'
            break
        if summary['physical_attempts'] >= caps['physical_per_episode']:
            summary['cause'] = 'physical_budget_exhausted'
            break
        if clock() >= cfg['deadline_epoch']:
            summary['cause'] = 'deadline'
            break
        check_stop()
        remaining = caps['logical_per_episode'] - summary['logical_calls']
        messages = AD.build_messages(view, history, remaining)
        body = AD.canonical_body(cfg['alias'], messages, settings)
        leaks = AD.leak_problems('\n'.join(m['content'] for m in messages), typed=typed)
        n = summary['logical_calls'] + 1
        if leaks:
            summary.update(cause='leak_guard', error='forbidden markers in the request body: %s' % leaks)
            append_line(steps_path, OrderedDict(step=n, kind='leak_guard', utc=S.utc(clock()), markers=leaks))
            break
        summary['logical_calls'] = n
        verdict = None
        attempts = []
        for k in range(1, caps['attempts_per_call'] + 1):
            if summary['physical_attempts'] >= caps['physical_per_episode'] or clock() >= cfg['deadline_epoch']:
                break
            key = 'call%02d_attempt%02d' % (n, k)
            write_x(rec_dir / (key + '.request.json'),
                    OrderedDict(request=REQUEST, seed=seed, logical_call=n, attempt=k, utc=S.utc(clock()),
                                body_sha256=S.sha_bytes(body.encode()), body=json.loads(body)))
            summary['physical_attempts'] += 1
            res = transport(body, cfg['deadline_epoch'] - clock())
            verdict = classify_transport(res)
            write_x(rec_dir / (key + '.outcome.json'),
                    OrderedDict(request=REQUEST, seed=seed, logical_call=n, attempt=k, utc=S.utc(clock()),
                                kind=res['kind'], http_status=res['http_status'], seconds=res['seconds'],
                                classification=verdict[0], response=res['body']))
            attempts.append(key)
            if verdict[0] != 'retry':
                break
        if verdict is None or verdict[0] == 'retry':
            if summary['physical_attempts'] >= caps['physical_per_episode']:
                summary['cause'] = 'physical_budget_exhausted'
            elif clock() >= cfg['deadline_epoch']:
                summary['cause'] = 'deadline'
            else:
                summary['cause'] = 'transport_failure'
            append_line(steps_path, OrderedDict(step=n, kind='no_reply', utc=S.utc(clock()), attempts=attempts,
                                                last=verdict))
            break
        if verdict[0] in ('context_limit', 'http_error'):
            summary.update(cause=verdict[0], error=verdict[1])
            append_line(steps_path, OrderedDict(step=n, kind=verdict[0], utc=S.utc(clock()), attempts=attempts,
                                                detail=verdict[1]))
            break
        _, content, usage, finish = verdict
        if isinstance(usage.get('prompt_tokens'), int) and isinstance(usage.get('completion_tokens'), int):
            summary['prompt_tokens'] += usage['prompt_tokens']
            summary['completion_tokens'] += usage['completion_tokens']
        else:
            summary['usage_unknown_calls'] += 1
        action, cause, detail = AD.parse_action(content, view['axtree'])
        row = OrderedDict(step=n, kind='call', utc=S.utc(clock()), attempts=attempts, model_view=view,
                          history_shown=list(history), remaining_shown=remaining, reply=content, finish_reason=finish,
                          usage=usage, parsed_action=action, invalid_cause=cause, invalid_detail=detail)
        if action is None:
            summary['invalid_replies'] += 1
            summary['invalid_causes'][cause] = summary['invalid_causes'].get(cause, 0) + 1
            history.append(OrderedDict(action=None, cause=cause))
            row['executed'] = False
            append_line(steps_path, row)
            continue
        check_stop()
        obs, reward, terminated, truncated, info = env.step(action)
        summary['executed_actions'] += 1
        if action.startswith('fill('):
            typed.append(AD.fill_text(action))
        err = str(obs.get('last_action_error') or '')
        if err:
            summary['action_errors'] += 1
        history.append(OrderedDict(action=action, error=AD.error_excerpt(err)))
        view = AD.model_view(obs, flatten)
        ti = info.get('task_info') or {}
        row.update(executed=True, action_error=err, screenshot=shot(obs, n) if shot else None,
                   verifier_only=OrderedDict(browsergym_reward=reward, terminated=terminated, truncated=truncated,
                                             task_info=ti, info_error=ti.get('error')))   # validate(): page/url changed
        if terminated or truncated:
            row['post_action_model_view'] = view         # the final page, never shown to the model
        append_line(steps_path, row)
        if terminated or truncated:
            done = True
            summary['cause'] = terminal_cause(ti, row['verifier_only']['info_error'])
            summary['terminal'] = OrderedDict((k, ti.get(k)) for k in ('DONE_GLOBAL', 'RAW_REWARD_GLOBAL',
                                                                       'REWARD_GLOBAL', 'REWARD_REASON'))
    summary['full_success'] = summary['cause'] == 'full_success'
    summary['wall_seconds'] = round(clock() - t_start, 3)
    summary['finished_utc'] = S.utc(clock())
    return summary


# ------------------------------------------------------------------ BrowserGym wiring (pinned venv only)
def make_env(cfg):
    import gymnasium as gym
    import browsergym.miniwob  # noqa: F401  registers browsergym/miniwob.*
    from browsergym.core.action.highlevel import HighLevelActionSet
    from browsergym.core.action.functions import click, fill
    actions = HighLevelActionSet(subsets=['custom'], custom_actions=[click, fill], multiaction=False, strict=True)
    names = sorted(actions.action_set)
    if names != ['click', 'fill', 'noop']:
        raise RuntimeError('restricted action set is %s, not click/fill/noop' % names)
    env = gym.make(cfg['task']['gym_id'], headless=True, pw_context_kwargs=dict(offline=True),
                   action_mapping=actions.to_python_code)
    return env, names


def run_batch(cfg, clock=time.time, env_factory=None, transport=None, flatten=None):
    out = Path(cfg['out_dir'])
    episodes = out / 'episodes'
    episodes.mkdir(parents=True, exist_ok=False)
    if flatten is None:
        from browsergym.utils.obs import flatten_axtree_to_str as flatten
    transport = transport or Transport(cfg['endpoint'], cfg['caps']['request_timeout_s'])
    batch = OrderedDict(request=REQUEST, status='DEVELOPMENT', seeds=cfg['seeds'], started_utc=S.utc(clock()),
                        episodes=[], stop=None)
    cap_bytes = cfg['caps']['artifact_gib'] * 2 ** 30
    for i, seed in enumerate(cfg['seeds']):
        if not batch['stop'] and STOP['requested']:
            batch['stop'] = 'stopped_by_supervisor'
        if not batch['stop'] and sum(f.stat().st_size for f in out.rglob('*') if f.is_file()) > cap_bytes:
            batch['stop'] = 'artifact_cap'
        if batch['stop']:
            batch['episodes'].append(OrderedDict(seed=seed, cause='not_started', full_success=False,
                                                 note='the batch stopped before this seed: %s' % batch['stop']))
            continue
        ep_dir = episodes / ('seed%d' % seed)
        env = None
        summary = None
        try:
            env, names = env_factory(cfg) if env_factory else make_env(cfg)

            def shot(obs, n, _d=ep_dir):
                if 'screenshot' not in obs:
                    return None
                from PIL import Image
                p = _d / 'screenshots' / ('step%02d.png' % n)
                p.parent.mkdir(exist_ok=True)
                Image.fromarray(obs['screenshot']).save(p)
                return 'screenshots/' + p.name
            summary = run_episode(seed, cfg, env, transport, ep_dir, flatten, clock,
                                  shot=None if env_factory else shot)
            summary['action_set'] = names
        except Stopped as e:
            summary = OrderedDict(getattr(e, 'partial', None) or OrderedDict(seed=seed))
            summary.update(cause='stopped_by_supervisor', full_success=False, error=str(e),
                           stopped_utc=S.utc(clock()))
            batch['stop'] = 'stopped_by_supervisor'
        except Exception as e:  # noqa: BLE001  recorded; the batch stops (no substitution, no retry)
            summary = OrderedDict(seed=seed, cause='harness_error', full_success=False,
                                  error='%s: %s' % (type(e).__name__, str(e)[:500]))
            batch['stop'] = 'harness_error'
        finally:
            if env is not None:
                try:
                    env.close()
                except BaseException as e:  # noqa: BLE001  recorded; never hides the episode's own outcome
                    if summary is not None:
                        summary['env_close_error'] = '%s: %s' % (type(e).__name__, str(e)[:300])
            if summary is not None:
                if ep_dir.exists():
                    write_x(ep_dir / 'episode.json', summary)
                append_line(out / 'episodes.jsonl', summary)     # durable per seed, before the batch summary exists
                batch['episodes'].append(summary)
        if summary and summary.get('cause') in BATCH_STOP_CAUSES and not batch['stop']:
            batch['stop'] = summary['cause']
        if STOP['requested'] and not batch['stop']:
            batch['stop'] = 'stopped_by_supervisor'
    batch['finished_utc'] = S.utc(clock())
    batch['full_success'] = sum(1 for e in batch['episodes'] if e.get('full_success'))
    batch['denominator'] = len(cfg['seeds'])
    write_x(out / 'batch_summary.json', batch)
    return batch


def admission(cfg):
    """The REQ-015 source and runtime pins, checked in this (pinned browser) process, plus the restricted action set."""
    import req015_qualify as Q
    m15 = json.loads((ROOT / cfg['req015_manifest']).read_text())
    sok, sdet = Q.check_sources(m15)
    rok, rdet = Q.check_runtime(m15)
    try:
        from browsergym.core.action.highlevel import HighLevelActionSet
        from browsergym.core.action.functions import click, fill
        names = sorted(HighLevelActionSet(subsets=['custom'], custom_actions=[click, fill], multiaction=False,
                                          strict=True).action_set)
    except Exception as e:  # noqa: BLE001  recorded
        names = ['%s: %s' % (type(e).__name__, e)]
    return OrderedDict(ok=sok and rok and names == ['click', 'fill', 'noop'], sources_ok=sok, runtime_ok=rok,
                       action_set=names, sources=sdet, runtime=rdet)


def main(argv=None):
    ap = argparse.ArgumentParser(description='DTR-REQ-016 episode child (started by req016_screen.py)')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--admission', metavar='CONFIG')
    g.add_argument('--run', metavar='CONFIG')
    args = ap.parse_args(argv)
    cfg = json.loads(Path(args.admission or args.run).read_text())
    if args.admission:
        d = admission(cfg)
        print(json.dumps(S.sanitize(d), default=str))
        return 0 if d['ok'] else 1
    STOP['parent'] = cfg.get('parent_pid')
    signal.signal(signal.SIGTERM, on_stop)
    signal.signal(signal.SIGINT, on_stop)
    batch = run_batch(cfg)
    print(json.dumps(OrderedDict(full_success=batch['full_success'], denominator=batch['denominator'],
                                 stop=batch['stop'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
