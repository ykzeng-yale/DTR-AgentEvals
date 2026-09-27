"""DTR-REQ-026B (lead decision 3fd6f33, docs/req026_on_demand_residency_20260927.md): a pure lifecycle and admission
controller for the versioned single-resident DEVELOPMENT configuration candidate32k. Every process, port, clock and
memory action goes through injected hooks; this module starts no server, model, VM, download or agent by itself and
has no command-line entry point. It does not edit or wrap the frozen harness.

candidate32k is a NEW execution configuration, not the old cached kernel. At most one owned backend is resident; a
backend may be unloaded and another loaded only at a prespecified routing opportunity. The explicit cache convention
(one prompt-cache setting, one slot, f16 KV, 32,768-token context) is applied identically to every backend and must be
the same for the logger and every target policy (require_common_convention). Its effect on outputs is disclosed, not
assumed away; token equality with any cached execution is not claimed.

Rules implemented:
  - ownership: only the PID this controller started, on its own port, with the identity recorded at start. A listener
    or identity mismatch refuses every signal (OwnershipError) and blocks further loads.
  - release before reload: SIGTERM, a bounded wait, a re-verified SIGKILL and a bounded wait; if exit is still not
    confirmed, ownership is retained and every later load is refused (TerminationUnconfirmed).
  - foreign presence: a listener on the target port or any foreign model job refuses the load; peers are never
    signalled, stopped or reconfigured.
  - admission: explicit caller-supplied bounds for the active weights, KV, compute buffers, cache, VM allocation, VM
    headroom and reserve; any missing term refuses admission. Static: VM + weights + KV + compute + cache + reserve <=
    host limit. Dynamic, on a fresh reading taken after the previous backend's release is confirmed: pressure in the
    allowed set and free >= weights + KV + compute + cache + VM headroom + reserve. Adverse pressure between calls
    stops only the owned server (check_pressure).
  - calls: a CallAction (backend, routing draw, opportunity flag) is immutable across retries; a completed call is
    never regenerated; the full message list and the repository handle are passed through unchanged.
  - budgets: the ORIGINAL episode deadline (fixed at 1,800 s for candidate32k) includes stopping, admission, loading
    and health waits. Infrastructure load/health failures (including a raising start hook) return explicit lifecycle
    statuses and never consume a generation attempt; at most 2 generation attempts per call (fixed).
  - records: every event carries the clock time, durations, the config digest and the cache convention.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass

VERSION = 'candidate32k-v1'
CONTEXT_TOKENS = 32768
KV_TYPE = 'f16'
EPISODE_DEADLINE_SECONDS = 1800
MAX_GENERATION_ATTEMPTS = 2
MIB = 1 << 20
SIGTERM, SIGKILL = 15, 9
ALLOWED_PRESSURE = ('normal',)
BOUND_TERMS = ('weights_bytes', 'kv_bytes', 'compute_bytes', 'cache_bytes')
CONFIG_TERMS = ('vm_bytes', 'vm_headroom_bytes', 'reserve_bytes', 'host_limit_bytes')


class ResidencyError(RuntimeError):
    pass


class ConfigError(ResidencyError):
    """invalid configuration; refused."""


class OwnershipError(ResidencyError):
    """a PID, identity or listener mismatch: no signal is sent."""


class TerminationUnconfirmed(ResidencyError):
    """the owned server's exit is not confirmed; ownership is retained and loads are refused."""


class CallIdentityError(ResidencyError):
    """a changed call action, a regeneration or an unplanned switch."""


class HookContractError(ResidencyError):
    """a hook raised or returned a value outside its contract; the owned server is cleaned up."""


class GenerationError(Exception):
    """raised by the generate hook for a failed generation attempt (counted as an attempt)."""


def _int(x, what, minimum=0):
    if isinstance(x, bool) or not isinstance(x, int) or x < minimum:
        raise ConfigError('%s must be an int >= %d, got %r' % (what, minimum, x))
    return x


def _optional_bytes(x, what):
    return None if x is None else _int(x, what)


@dataclass(frozen=True)
class CacheConvention:
    prompt_cache_ram_mib: int          # the server prompt-cache allowance, identical for every backend (0 disables)
    cache_prompt: bool                 # the per-request prompt-cache flag, identical for every call
    slots: int = 1
    kv_type: str = KV_TYPE
    context_tokens: int = CONTEXT_TOKENS

    def __post_init__(self):
        _int(self.prompt_cache_ram_mib, 'prompt_cache_ram_mib')      # -1 (unbounded) is refused
        if not isinstance(self.cache_prompt, bool):
            raise ConfigError('cache_prompt must be a bool')
        if self.slots != 1 or isinstance(self.slots, bool):
            raise ConfigError('candidate32k serves exactly one slot')
        if self.kv_type != KV_TYPE:
            raise ConfigError('candidate32k uses %s KV, got %r' % (KV_TYPE, self.kv_type))
        if self.context_tokens != CONTEXT_TOKENS or isinstance(self.context_tokens, bool):
            raise ConfigError('candidate32k is %d tokens; %r is held' % (CONTEXT_TOKENS, self.context_tokens))


@dataclass(frozen=True)
class BackendSpec:
    name: str
    alias: str
    port: int
    model_sha256: str
    weights_bytes: int = None
    kv_bytes: int = None
    compute_bytes: int = None
    cache_bytes: int = None

    def __post_init__(self):
        for f in ('name', 'alias'):
            if not isinstance(getattr(self, f), str) or not getattr(self, f):
                raise ConfigError('backend %s must be a non-empty string' % f)
        _int(self.port, 'port', 1)
        if not isinstance(self.model_sha256, str) or not re.fullmatch('[0-9a-f]{64}', self.model_sha256):
            raise ConfigError('model_sha256 must be a 64-character lowercase hex digest')
        for t in BOUND_TERMS:
            _optional_bytes(getattr(self, t), '%s %s' % (self.name, t))


@dataclass(frozen=True)
class ResidencyConfig:
    backends: tuple
    cache: CacheConvention
    vm_bytes: int = None               # VM allocation, counted in full by the static bound
    vm_headroom_bytes: int = None      # growth the VM may still claim beyond the current reading
    reserve_bytes: int = None          # free memory that must remain for peers and the system after the load
    host_limit_bytes: int = None       # static ceiling (e.g. physical memory minus a margin)
    version: str = VERSION
    episode_deadline_seconds: float = EPISODE_DEADLINE_SECONDS
    stop_grace_seconds: float = 60
    kill_wait_seconds: float = 30
    health_timeout_seconds: float = 600
    poll_seconds: float = 1
    max_generation_attempts: int = MAX_GENERATION_ATTEMPTS
    allowed_pressure: tuple = ALLOWED_PRESSURE

    def __post_init__(self):
        if self.version != VERSION:
            raise ConfigError('configuration version %r is not %s' % (self.version, VERSION))
        if not isinstance(self.cache, CacheConvention):
            raise ConfigError('cache must be a CacheConvention')
        if not isinstance(self.backends, tuple) or not self.backends or \
                not all(isinstance(b, BackendSpec) for b in self.backends):
            raise ConfigError('backends must be a non-empty tuple of BackendSpec')
        if len({b.name for b in self.backends}) != len(self.backends) or \
                len({b.port for b in self.backends}) != len(self.backends):
            raise ConfigError('backend names and ports must be unique')
        for t in CONFIG_TERMS:
            _optional_bytes(getattr(self, t), t)
        for f in ('episode_deadline_seconds', 'stop_grace_seconds', 'kill_wait_seconds', 'health_timeout_seconds',
                  'poll_seconds'):
            v = getattr(self, f)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not v > 0:
                raise ConfigError('%s must be a positive finite number' % f)
        if self.allowed_pressure != ALLOWED_PRESSURE:
            raise ConfigError('allowed_pressure must be exactly %s; a weaker pressure rule is refused'
                              % (ALLOWED_PRESSURE,))
        if self.episode_deadline_seconds != EPISODE_DEADLINE_SECONDS:
            raise ConfigError('candidate32k keeps the fixed %d s episode budget, which includes switching and loading'
                              % EPISODE_DEADLINE_SECONDS)
        if _int(self.max_generation_attempts, 'max_generation_attempts', 1) != MAX_GENERATION_ATTEMPTS:
            raise ConfigError('candidate32k keeps %d generation attempts per call' % MAX_GENERATION_ATTEMPTS)
        for b in self.backends:
            if b.cache_bytes is not None and b.cache_bytes < self.cache.prompt_cache_ram_mib * MIB:
                raise ConfigError('%s cache_bytes %d does not cover the configured prompt cache of %d MiB'
                                  % (b.name, b.cache_bytes, self.cache.prompt_cache_ram_mib))

    def backend(self, name):
        for b in self.backends:
            if b.name == name:
                return b
        raise ConfigError('unknown backend %r' % name)

    def digest(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, default=str).encode()).hexdigest()


def require_common_convention(*configs):
    """the logger and every target policy must share one version and one cache convention."""
    if not configs:
        raise ConfigError('no configurations given')
    if len({(c.version, c.cache) for c in configs}) != 1:
        raise ConfigError('configurations differ in version or cache convention; one convention applies to all')
    return configs[0].cache


def admission_check(config, backend_name, reading):
    """static and dynamic admission for loading one backend; any missing term refuses."""
    b = config.backend(backend_name)
    terms = {t: getattr(b, t) for t in BOUND_TERMS}
    terms.update({t: getattr(config, t) for t in CONFIG_TERMS})
    reasons = ['missing bound: %s' % t for t, v in terms.items() if v is None]
    free, pressure = (reading or {}).get('free_bytes'), (reading or {}).get('pressure')
    if isinstance(free, bool) or not isinstance(free, int) or free < 0:
        reasons.append('missing or invalid free_bytes reading: %r' % (free,))
    if not isinstance(pressure, str):
        reasons.append('missing or invalid pressure reading: %r' % (pressure,))
    out = dict(backend=backend_name, terms=terms, reading=dict(free_bytes=free, pressure=pressure))
    if reasons:
        return dict(out, admitted=False, reasons=reasons)
    model_side = sum(terms[t] for t in BOUND_TERMS)
    static_total = terms['vm_bytes'] + model_side + terms['reserve_bytes']
    dynamic_need = model_side + terms['vm_headroom_bytes'] + terms['reserve_bytes']
    if static_total > terms['host_limit_bytes']:
        reasons.append('static bound %d exceeds host limit %d' % (static_total, terms['host_limit_bytes']))
    if pressure not in config.allowed_pressure:
        reasons.append('pressure %r is not in %s' % (pressure, list(config.allowed_pressure)))
    if free < dynamic_need:
        reasons.append('free %d is below the %d needed for the load, VM headroom and reserve' % (free, dynamic_need))
    return dict(out, admitted=not reasons, reasons=reasons, static_total=static_total, dynamic_need=dynamic_need)


@dataclass(frozen=True)
class CallAction:
    """one logical call; fixed before the first attempt and identical across retries."""
    episode_id: str
    call_index: int
    policy: str
    backend: str
    routing_draw: str                  # the recorded routing draw (or 'none'); never redrawn
    at_routing_opportunity: bool       # a backend change is allowed only here

    def __post_init__(self):
        _int(self.call_index, 'call_index', 1)
        for f in ('episode_id', 'policy', 'backend', 'routing_draw'):
            if not isinstance(getattr(self, f), str) or not getattr(self, f):
                raise ConfigError('%s must be a non-empty string' % f)
        if not isinstance(self.at_routing_opportunity, bool):
            raise ConfigError('at_routing_opportunity must be a bool')


def messages_digest(messages):
    return hashlib.sha256(json.dumps(messages, sort_keys=True, default=str).encode()).hexdigest()


TERMINAL = ('generated', 'deadline_expired', 'aborted_after_generation', 'generation_attempts_exhausted',
            'reply_received', 'refused_history_changed')          # a returned reply or a history violation ends a call


class ResidencyController:
    """one episode's residency: at most one owned backend; the episode deadline covers every lifecycle step.

    Hook contracts (each checked on every call; a violation raises HookContractError after cleaning up the owned
    server, or blocks the controller when release cannot be confirmed):
      clock() -> finite number; sleep(seconds) -> None (loops are also bounded by iteration count);
      listener_pid(port) -> None | positive int | list of positive ints (several listeners are never ours alone);
      foreign_jobs() -> list of foreign model jobs, excluding the owned PID;
      memory_state() -> {'free_bytes': int, 'pressure': str} (anything else is an adverse reading);
      start_server(spec, cache) -> positive int PID, or raises leaving no process behind;
      health(spec) -> bool; pid_alive(pid) -> bool;
      pid_identity(pid) -> a PID-reuse-resistant token (None when the process is gone);
      send_signal(pid, sig) -> None, called only after ownership re-verification;
      generate(spec, messages, remaining_seconds) (passed to run_call) -> the reply, or raises GenerationError.

    Time responsibility: every hook, and generate in particular, must return within a bounded time that it enforces
    itself (generate's request timeout must not exceed the remaining_seconds it is given). The controller's checks
    run only after a hook returns; they cannot preempt a hung hook. Its own wait loops are bounded by iteration
    count as well as by the clock. A PID is recorded as owned the moment start_server returns it; if its identity
    cannot then be read, the controller blocks with that ownership retained and sends no signal."""

    HOOKS = ('clock', 'sleep', 'listener_pid', 'foreign_jobs', 'memory_state', 'start_server', 'health', 'pid_alive',
             'pid_identity', 'send_signal')

    def __init__(self, config, hooks, episode_start, episode_id):
        if not isinstance(config, ResidencyConfig):
            raise ConfigError('config must be a ResidencyConfig')
        if not isinstance(hooks, dict):
            raise ConfigError('hooks must be a dict')
        missing = [h for h in self.HOOKS if not callable(hooks.get(h))]
        if missing:
            raise ConfigError('missing hooks %s' % missing)
        if isinstance(episode_start, bool) or not isinstance(episode_start, (int, float)) or \
                not math.isfinite(episode_start):
            raise ConfigError('episode_start must be a finite clock reading')
        if not isinstance(episode_id, str) or not episode_id:
            raise ConfigError('episode_id must be a non-empty string')
        self.config, self.h, self.episode_id = config, hooks, episode_id
        self.deadline = episode_start + config.episode_deadline_seconds
        self.digest = config.digest()
        self.owned = None              # dict(backend, pid, port, identity, started, loaded)
        self.blocked = None
        self.events = []
        self.routing = []              # the routing history, one entry per registered call; kept across unloads
        self.actions, self.snapshots, self.attempts, self.status, self.replies = {}, {}, {}, {}, {}

    # ---------------------------------------------------------------- hooks with checked contracts
    def _hook(self, name, *args):
        try:
            return self.h[name](*args)
        except Exception as e:                                        # noqa: BLE001 - every hook failure is explicit
            raise HookContractError('%s hook raised %r' % (name, e)) from e

    def _now(self):
        t = self._hook('clock')
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t):
            raise HookContractError('clock returned %r, not a finite number' % (t,))
        return float(t)

    def _bool(self, name, *args):
        out = self._hook(name, *args)
        if not isinstance(out, bool):
            raise HookContractError('%s returned %r, not a bool' % (name, out))
        return out

    def _listener(self, port):
        out = self._hook('listener_pid', port)
        if out is None:
            return None
        if isinstance(out, int) and not isinstance(out, bool) and out > 0:
            return out
        if isinstance(out, (list, tuple)) and out and \
                all(isinstance(x, int) and not isinstance(x, bool) and x > 0 for x in out):
            return tuple(out)
        raise HookContractError('listener_pid returned %r' % (out,))

    def _foreign(self):
        out = self._hook('foreign_jobs')
        if not isinstance(out, (list, tuple)):
            raise HookContractError('foreign_jobs returned %r, not a list' % (out,))
        own = self.owned['pid'] if self.owned else None               # defensive: never count the owned PID
        return [j for j in out if not (isinstance(j, dict) and own is not None and j.get('pid') == own)]

    def _reading(self):
        out = self._hook('memory_state')
        return out if isinstance(out, dict) else {}

    def _sleep(self):
        if self._hook('sleep', self.config.poll_seconds) is not None:
            raise HookContractError('sleep returned a value')

    # ---------------------------------------------------------------- records
    def _event(self, kind, **kw):
        ev = dict(event=kind, t=self._now(), config_digest=self.digest, cache=asdict(self.config.cache), **kw)
        self.events.append(ev)
        return ev

    def remaining(self):
        return self.deadline - self._now()

    def _polls(self, seconds):
        return int(math.ceil(seconds / self.config.poll_seconds)) + 2

    # ---------------------------------------------------------------- ownership and release
    def _block(self, reason, **kw):
        self.blocked = reason
        try:
            self._event('blocked', reason=reason, **kw)
        except HookContractError:
            self.events.append(dict(event='blocked', t=None, reason=reason, config_digest=self.digest, **kw))

    def _owned_state(self, o):
        """'gone' when the owned process has exited, 'ours' when listener and identity match; any mismatch blocks
        the controller and raises OwnershipError without a signal."""
        if not self._bool('pid_alive', o['pid']):
            return 'gone'
        lp = self._listener(o['port'])
        ident = self._hook('pid_identity', o['pid'])
        if lp in (o['pid'], None) and ident is not None and ident == o['identity']:
            return 'ours'
        msg = ('PID %d on port %d: listener %r, identity %r (recorded %r); no signal sent'
               % (o['pid'], o['port'], lp, ident, o['identity']))
        self._block(msg, backend=o['backend'], pid=o['pid'])
        raise OwnershipError(msg)

    def _wait_exit(self, pid, seconds):
        end = self._now() + seconds
        for _ in range(self._polls(seconds)):
            if not self._bool('pid_alive', pid):
                return True
            if self._now() >= end:
                return False
            self._sleep()
        return not self._bool('pid_alive', pid)

    def stop(self, reason='release'):
        """release the owned server with confirmation; never signals anything else."""
        if self.blocked:
            raise TerminationUnconfirmed(self.blocked)
        o = self.owned
        if o is None:
            return None
        try:
            t0 = self._now()
            how = 'already exited'
            if self._owned_state(o) == 'ours':
                self._hook('send_signal', o['pid'], SIGTERM)
                self._event('sigterm_sent', backend=o['backend'], pid=o['pid'], reason=reason)
                how = 'SIGTERM'
                if not self._wait_exit(o['pid'], self.config.stop_grace_seconds):
                    if self._owned_state(o) == 'ours':
                        self._hook('send_signal', o['pid'], SIGKILL)
                        self._event('sigkill_sent', backend=o['backend'], pid=o['pid'])
                        how = 'SIGKILL'
                        if not self._wait_exit(o['pid'], self.config.kill_wait_seconds):
                            self._block('PID %d exit unconfirmed after SIGTERM and SIGKILL; ownership retained'
                                        % o['pid'], backend=o['backend'], pid=o['pid'], seconds=self._now() - t0)
                            self.events[-1]['event'] = 'termination_unconfirmed'
                            raise TerminationUnconfirmed(self.blocked)
        except HookContractError as e:
            self._block('release of PID %d unconfirmed: %s' % (o['pid'], e), backend=o['backend'], pid=o['pid'])
            raise
        self.owned = None
        return self._event('stop_confirmed', backend=o['backend'], pid=o['pid'], reason=reason, how=how,
                           seconds=self._now() - t0)

    def release(self):
        """episode end: stop the owned server with confirmation (idempotent)."""
        return self.stop('episode end')

    def _cleanup(self, reason):
        """after a hook contract failure: stop the owned server if that can still be confirmed."""
        if self.owned and not self.blocked:
            try:
                self.stop(reason)
            except ResidencyError:
                pass                                                  # the controller is now blocked

    # ---------------------------------------------------------------- pressure
    def _adverse(self, reading):
        free, pressure = reading.get('free_bytes'), reading.get('pressure')
        return pressure not in self.config.allowed_pressure or isinstance(free, bool) or not isinstance(free, int) \
            or self.config.reserve_bytes is None or free < self.config.reserve_bytes

    def _pressure_gate(self, where):
        """None when the fresh reading is acceptable; otherwise stop only the owned server and return the reading."""
        reading = self._reading()
        if not self._adverse(reading):
            return None
        self._event('pressure_abort', where=where, reading=reading,
                    owned=None if not self.owned else self.owned['backend'])
        self.stop('resource pressure at %s' % where)
        return reading

    def check_pressure(self):
        """between calls: on adverse pressure or a reading below the reserve, stop only the owned server."""
        try:
            reading = self._pressure_gate('check')
        except HookContractError:
            self._cleanup('hook contract failure')
            raise
        return dict(status='ok') if reading is None else dict(status='aborted_resource_pressure', reading=reading)

    # ---------------------------------------------------------------- load
    def ensure(self, backend):
        """make backend the owned resident server; returns a lifecycle status (never a generation attempt). The
        deadline and a fresh pressure reading are checked before reuse and before any load."""
        if self.blocked:
            raise TerminationUnconfirmed(self.blocked)
        spec = self.config.backend(backend)
        try:
            return self._ensure(spec)
        except HookContractError:
            self._cleanup('hook contract failure')
            raise

    def _ensure(self, spec):
        backend = spec.name
        t0 = self._now()
        if self.remaining() <= 0:
            return self._outcome('deadline_expired', backend, t0)
        resident = bool(self.owned and self.owned['backend'] == backend)
        if self._pressure_gate('before %s' % ('reuse' if resident else 'load')) is not None:
            return self._outcome('aborted_resource_pressure', backend, t0)
        if resident:
            foreign = self._foreign()
            if foreign:                                   # a foreign model job appeared: do not reuse, do not signal it
                return self._outcome('refused_foreign_presence', backend, t0, foreign=foreign)
        if self.owned and self.owned['backend'] == backend:
            o = self.owned
            if self._owned_state(o) == 'ours' and self._listener(o['port']) == o['pid'] and self._bool('health', spec):
                self._event('reused', backend=backend, pid=o['pid'])
                return dict(status='reused', backend=backend, switch_seconds=0)
            self._event('owned_backend_unhealthy', backend=backend, pid=o['pid'])
        stop = self.stop('switch to %s' % backend) if self.owned else None
        foreign = self._foreign()
        if foreign:
            return self._outcome('refused_foreign_presence', backend, t0, foreign=foreign)
        lp = self._listener(spec.port)
        if lp is not None:
            return self._outcome('refused_foreign_listener', backend, t0, listener=lp)
        adm = admission_check(self.config, backend, self._reading())
        self._event('admission', backend=backend, admitted=adm['admitted'], reasons=adm['reasons'])
        if not adm['admitted']:
            return self._outcome('refused_admission', backend, t0, reasons=adm['reasons'])
        if self.remaining() <= 0:
            return self._outcome('deadline_expired', backend, t0)
        t_load = self._now()
        try:
            pid = self.h['start_server'](spec, self.config.cache)      # contract: a raising hook leaves no process
        except Exception as e:                                        # noqa: BLE001 - a spawn failure is infra
            return self._outcome('infrastructure_load_failed', backend, t0, detail='start hook: %r' % e,
                                 load_seconds=self._now() - t_load)
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            self._block('start_server returned %r; an unknown process may exist' % (pid,), backend=backend)
            raise HookContractError('start_server returned %r, not a positive PID' % (pid,))
        # provisional ownership first, so a failing identity read cannot orphan a live process
        self.owned = dict(backend=backend, pid=pid, port=spec.port, identity=None, provisional=True, started=t_load)
        try:
            identity = self.h['pid_identity'](pid)
        except Exception as e:                                        # noqa: BLE001 - any failure blocks
            identity, failure = None, repr(e)
        else:
            failure = None if identity is not None else 'None'
        if failure is not None:
            self._block('identity of started PID %d on port %d is unknown (%s); ownership retained, no signal sent'
                        % (pid, spec.port, failure), backend=backend, pid=pid, port=spec.port)
            raise HookContractError('pid_identity failed for the started PID %d: %s' % (pid, failure))
        self.owned.update(identity=identity, provisional=False)
        self._event('load_started', backend=backend, pid=pid, port=spec.port, model_sha256=spec.model_sha256)
        for _ in range(self._polls(self.config.health_timeout_seconds)):
            if not self._bool('pid_alive', pid):
                self.owned = None
                return self._outcome('infrastructure_load_failed', backend, t0, pid=pid,
                                     load_seconds=self._now() - t_load)
            if self._bool('health', spec) and self._listener(spec.port) == pid:
                self.owned['loaded'] = self._now()
                ev = self._event('loaded', backend=backend, pid=pid, load_seconds=self.owned['loaded'] - t_load,
                                 switch_seconds=self.owned['loaded'] - t0,
                                 stop_seconds=None if stop is None else stop['seconds'])
                return dict(status='loaded', backend=backend, switch_seconds=ev['switch_seconds'],
                            load_seconds=ev['load_seconds'])
            now = self._now()
            if now >= self.deadline:
                self.stop('deadline during load')
                return self._outcome('deadline_expired', backend, t0, load_seconds=now - t_load)
            if now - t_load >= self.config.health_timeout_seconds:
                self.stop('health timeout')
                return self._outcome('infrastructure_health_timeout', backend, t0, load_seconds=now - t_load)
            if self._pressure_gate('during load') is not None:
                return self._outcome('aborted_resource_pressure', backend, t0, load_seconds=self._now() - t_load)
            self._sleep()
        self.stop('health wait bound')
        return self._outcome('infrastructure_health_timeout', backend, t0, load_seconds=self._now() - t_load,
                             detail='iteration bound reached')

    def _outcome(self, status, backend, t0, **kw):
        ev = self._event(status, backend=backend, switch_seconds=self._now() - t0, **kw)
        return dict(status=status, backend=backend, switch_seconds=ev['switch_seconds'],
                    **{k: v for k, v in kw.items() if k != 'foreign'})

    # ---------------------------------------------------------------- calls
    def register(self, action, messages=None):
        """record a call's routing decision once: calls in order, the previous call completed, a backend change only
        at a routing opportunity (judged against the routing history, not residency), and the same action and
        history on every retry. A terminal call is never run again."""
        if not isinstance(action, CallAction) or action.episode_id != self.episode_id:
            raise CallIdentityError('a CallAction for episode %s is required' % self.episode_id)
        self.config.backend(action.backend)
        k = action.call_index
        prior = self.actions.get(k)
        if prior is None:
            last = max(self.actions) if self.actions else 0
            if k != last + 1:
                raise CallIdentityError('call %d registered out of order; the next call is %d' % (k, last + 1))
            if last and self.status.get(last) != 'generated':
                raise CallIdentityError('call %d has not completed (status %r)' % (last, self.status.get(last)))
            routed = self.routing[-1]['backend'] if self.routing else None
            if routed is not None and action.backend != routed and not action.at_routing_opportunity:
                raise CallIdentityError('call %d would switch %s -> %s outside a routing opportunity'
                                        % (k, routed, action.backend))
            self.actions[k] = action
            self.routing.append(dict(call_index=k, policy=action.policy, backend=action.backend,
                                     routing_draw=action.routing_draw,
                                     at_routing_opportunity=action.at_routing_opportunity))
            self._event('routed', call_index=k, backend=action.backend, routing_draw=action.routing_draw)
        elif prior != action:
            raise CallIdentityError('call %d changed across retries: %r -> %r' % (k, prior, action))
        if self.status.get(k) in TERMINAL:
            raise CallIdentityError('call %d is terminal (%s); it is never regenerated' % (k, self.status[k]))
        if messages is not None and k not in self.snapshots:
            self.snapshots[k] = (messages_digest(messages), copy.deepcopy(messages))
        return action

    def _require_history(self, k, messages, where='refused before any invocation'):
        """any change to the call's history ends the call: restoring the input later cannot reopen it."""
        digest, snapshot = self.snapshots[k]
        if messages_digest(messages) != digest or messages != snapshot:
            self.status[k] = 'refused_history_changed'
            self._event('history_changed', call_index=k, where=where)
            raise CallIdentityError('the message history for call %d changed; %s' % (k, where))

    def _done(self, k, out):
        self.status[k] = out['status']
        return out

    def run_call(self, action, messages, repo_handle, generate):
        """ensure the backend, then at most max_generation_attempts generations with the unchanged full history.
        generate(spec, messages, remaining_seconds) returns the reply or raises GenerationError. The deadline and a
        fresh pressure reading gate every reuse, load, invocation and acceptance; a reply arriving after the
        deadline or under adverse pressure is discarded and the call becomes terminal (never regenerated)."""
        self.register(action, messages)
        k = action.call_index
        spec = self.config.backend(action.backend)
        base = dict(call_index=k, backend=action.backend, routing_draw=action.routing_draw, config_digest=self.digest,
                    cache=asdict(self.config.cache))
        failures = []

        def result(status, **kw):
            return dict(base, status=status, generation_attempts=self.attempts.get(k, 0),
                        generation_failures=list(failures), **kw)
        try:
            while True:
                self._require_history(k, messages)
                if self.attempts.get(k, 0) >= self.config.max_generation_attempts:
                    return self._done(k, result('generation_attempts_exhausted'))
                if self.remaining() <= 0:
                    return self._done(k, result('deadline_expired'))
                load = self.ensure(action.backend)
                if load['status'] not in ('reused', 'loaded'):
                    return self._done(k, result(load['status'], lifecycle=load))
                if self.remaining() <= 0:                  # the load itself used the rest of the budget
                    return self._done(k, result('deadline_expired', lifecycle=load))
                if self._pressure_gate('before invocation') is not None:
                    return self._done(k, result('aborted_resource_pressure', lifecycle=load))
                foreign = self._foreign()
                if foreign:
                    self._event('refused_foreign_presence', backend=action.backend, call_index=k,
                                where='before invocation')
                    return self._done(k, result('refused_foreign_presence', lifecycle=load))
                self._require_history(k, messages)
                left = self.remaining()
                t0 = self._now()
                self.attempts[k] = self.attempts.get(k, 0) + 1
                try:
                    reply = generate(spec, messages, left)
                except GenerationError as e:
                    failures.append(str(e))
                    self._event('generation_failed', backend=action.backend, call_index=k, detail=str(e),
                                seconds=self._now() - t0)
                    continue                               # the loop re-checks history, deadline and pressure
                # a reply exists: record it and end the call BEFORE any fallible validation, so no failure below
                # (history, clock, pressure or a hook) can lead to a regeneration of this call
                self.status[k] = 'reply_received'
                reply_digest = hashlib.sha256(repr(reply).encode()).hexdigest()
                self.replies[k] = dict(reply=reply, reply_sha256=reply_digest, attempt=self.attempts[k])
                self._require_history(k, messages, 'detected after the reply; the reply is not accepted')
                if self.remaining() <= 0:
                    self._event('reply_discarded', reason='after the deadline', call_index=k, reply_sha256=reply_digest)
                    return self._done(k, result('deadline_expired', lifecycle=load, reply_discarded=True))
                if self._pressure_gate('acceptance') is not None:
                    self._event('reply_discarded', reason='adverse pressure', call_index=k, reply_sha256=reply_digest)
                    return self._done(k, result('aborted_after_generation', lifecycle=load, reply_discarded=True))
                self._event('generated', backend=action.backend, call_index=k, seconds=self._now() - t0)
                return self._done(k, result('generated', reply=reply, lifecycle=load, repo_handle=repo_handle))
        except HookContractError:
            self._cleanup('hook contract failure')
            raise
