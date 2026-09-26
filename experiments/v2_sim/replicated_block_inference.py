"""DTR-REQ-024 (Codex lead, docs/req024_replicated_inference_setup.md): pure analysis functions for prospective
replicated complete-block inference, following docs/theory_replicated_block_inference.md (a prospective mathematical
design, independently reviewed internally on 26 September 2026 with no blocking algebra issue; not external peer
review; the note is the authority). Exact where the arithmetic is rational; no model, sampling, Monte Carlo, archive
loading, CLI or new dependency.

Independent unit (theory note, eq. 1): one COMPLETE repetition of the fixed benchmark design, with all its logged and
fresh executions, never a task, episode, branch, seed label or cross-fit fold. Within a block every covariance is
kept. The checks here (unique block IDs, one frozen-contract ID, declared bounds) are structural only: they do not
establish physical independence, valid execution, the marginal score laws or the restoration assumption. These
functions consume externally prepared block summaries. Do not manufacture blocks by splitting the single historical
study.

Primary (note, Sec. 3): Z_b = (offline_history, offline_prompt, fresh_history, fresh_prompt), with the contrasts
fresh gain (0,0,1,-1), offline gain (1,-1,0,0) and gain-calibration discrepancy (1,-1,-1,1).
  - summarize_blocks: B, mean, unbiased sample covariance S_B (eq. 2) and the covariance of the mean S_B / B.
  - linear_estimate / wald: a'Zbar and a'S_B a / B with the FULL covariance (offline/fresh cross terms included).
    Wald output is an asymptotic approximation in the number of complete blocks, never validated coverage; it is
    refused (status 'unavailable') for B < 2 or a zero/nonfinite estimated variance.
  - hoeffding_rectangle / linear_set: the finite-sample rectangle (eq. 5) for caller-declared bounds and error budget,
    intersected with the known mean range, then propagated to a contrast by coefficient signs (eq. 10) and
    intersected with the contrast range; an empty required component returns the whole contrast range.
Secondary (note, Sec. 4): Z_b = (N_times_branch_mean, N, U1, D1, U0, D0).
  - latent_total_estimate: N * Bhat for one block (Prop. 3), 0 when N = 0.
  - branch_estimate / branch_gradient / branch_wald: pooled totals, then ratios, T/N - U1/D1 + U0/D0 (eq. 16), its
    gradient (eq. 17) and delta-method scale with the full covariance; unavailable at an observed zero denominator.
  - branch_finite_set: eqs. 18-20; the whole range [-2, 2] when a denominator lower limit is nonpositive or a
    required intersection is empty.

Numbers: inputs are int, Fraction or finite float (converted to Fraction exactly; bool refused). Means, covariances,
linear estimates, their variance estimates, the branch estimate, gradient and delta variance are exact Fractions.
Square roots, normal quantiles, Hoeffding widths and finite-sample sets are floats, not outward-rounded. The normal
quantile is taken from the lower tail, z = -Phi^{-1}(alpha / 2), so a tiny valid alpha does not cancel to 1; log(2 /
alpha_j) is evaluated from the exact numerator and denominator, so a tiny budget cannot underflow. A value that cannot
be represented as a finite float is refused (BlockInputError), and a nonfinite Wald endpoint is 'unavailable'. Every
result is in endpoint units, never dollars.

Refusals: invalid input raises BlockInputError; no record is dropped and no observation is clipped. A statistically
unavailable result is returned with status 'unavailable' and a reason, never as a zero-width success.

    import replicated_block_inference as R
    R.primary_analysis(blocks, contract_id='c1', score_bounds=bounds_proved_for_the_design, alpha=0.05)
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from fractions import Fraction
from statistics import NormalDist

VERSION = 'replicated_block_inference_v1'
UNIT = 'endpoint units (terminal-success scale); not dollars'

PRIMARY_COORDS = ('offline_history', 'offline_prompt', 'fresh_history', 'fresh_prompt')
PRIMARY_CONTRASTS = {'fresh_gain': (0, 0, 1, -1),                          # eq. 9
                     'offline_gain': (1, -1, 0, 0),
                     'gain_calibration_discrepancy': (1, -1, -1, 1)}
PRIMARY_CONTRAST_RANGES = {'fresh_gain': (-1, 1), 'offline_gain': (-1, 1), 'gain_calibration_discrepancy': (-2, 2)}
PRIMARY_MEAN_RANGE = (0, 1)          # each component mean, under the note's score and marginal assumptions (Sec. 3.2)
# eq. 7-8: valid ONLY for the proposed two-decision logger with both eligible actions at probability 1/2. A caller
# declares bounds proved for its own design; no function assumes these.
TWO_DECISION_HALF_LOGGER_SCORE_BOUNDS = ((-6, 7), (-6, 7), (0, 1), (0, 1))

BRANCH_COORDS = ('N_times_branch_mean', 'N', 'U1', 'D1', 'U0', 'D0')
BRANCH_RANGE = (-2, 2)
BRANCH_THETA_RANGE = (-1, 1)
BRANCH_NU_RANGE = (0, 1)

WALD_NOTE = ('asymptotic normal approximation as the number of complete blocks grows, under the complete-block '
             'contract (theory note Prop. 1); not validated coverage. No finite block count certifies normal '
             'calibration: a prespecified minimum block count and a validated operating-characteristic gate are '
             'required before presenting it as an empirical inference procedure, and neither is supplied here.')
DELTA_NOTE = ('delta-method plug-in scale for the pooled ratio functional (theory note eqs. 3-4, 17); the ratio '
              'estimator is not claimed unbiased and the plug-in variance is not a finite-B unbiased estimate. '
              + WALD_NOTE)
RECTANGLE_NOTE = ('finite-sample: P(mu in rectangle) >= 1 - alpha under the complete-block contract, from Hoeffding '
                  'per coordinate and a union bound (theory note Prop. 2); conservative, and its width is a design '
                  'diagnostic, not evidence of useful precision.')
STRUCTURAL_NOTE = ('block IDs, contract ID and bounds are checked structurally; this does not establish independent '
                   'complete blocks, valid execution or the score/restoration assumptions.')


class BlockInputError(ValueError):
    """invalid input; refused, never silently repaired."""


def exact(x, what='value'):
    """x as an exact Fraction; int, Fraction or finite float only."""
    if isinstance(x, bool) or not isinstance(x, (int, float, Fraction)):
        raise BlockInputError('%s must be an int, Fraction or finite float, got %r' % (what, x))
    if isinstance(x, float) and not math.isfinite(x):
        raise BlockInputError('%s is not finite: %r' % (what, x))
    return Fraction(x)


def _sequence(x, what):
    if isinstance(x, (str, bytes, Mapping)) or not isinstance(x, Sequence):
        raise BlockInputError('%s must be a sequence, got %r' % (what, type(x).__name__))
    return x


def _coords(coords):
    _sequence(coords, 'coords')
    if not coords or any(not isinstance(c, str) or not c for c in coords) or len(set(coords)) != len(coords):
        raise BlockInputError('coords must be distinct non-empty names')
    return tuple(coords)


def _contract(c, what='contract_id'):
    if not isinstance(c, str) or not c.strip():
        raise BlockInputError('%s must be a non-empty string, got %r' % (what, c))
    return c


def _block_id(b, k):
    if isinstance(b, bool) or not isinstance(b, (str, int)) or (isinstance(b, str) and not b.strip()):
        raise BlockInputError('block record %d: block_id must be a non-empty string or an int, got %r' % (k, b))
    return b


def _interval(pair, what, strict=True):
    _sequence(pair, what)
    if len(pair) != 2:
        raise BlockInputError('%s must be a (lower, upper) pair' % what)
    lo, hi = exact(pair[0], what + ' lower'), exact(pair[1], what + ' upper')
    if not (lo < hi if strict else lo <= hi):
        raise BlockInputError('%s needs lower %s upper, got (%s, %s)' % (what, '<' if strict else '<=', lo, hi))
    return lo, hi


def validate_bounds(bounds, p, what='bounds'):
    """p caller-declared deterministic (lower, upper) pairs with lower <= upper; lower == upper is a deterministic
    zero-width coordinate (c_j = 0 in Prop. 2)."""
    _sequence(bounds, what)
    if len(bounds) != p:
        raise BlockInputError('%s must give %d (lower, upper) pairs, got %d' % (what, p, len(bounds)))
    return tuple(_interval(b, '%s[%d]' % (what, j), strict=False) for j, b in enumerate(bounds))


def _finite_float(x, what):
    """float(x) for an exact x, refusing a value that overflows."""
    try:
        f = float(x)
    except OverflowError:
        f = math.inf
    if not math.isfinite(f):
        raise BlockInputError('%s = %s cannot be represented as a finite float' % (what, x))
    return f


def _log_two_over(a):
    """log(2 / a) for an exact 0 < a < 1 without converting a to float (no underflow for a tiny budget)."""
    return math.log(2) + math.log(a.denominator) - math.log(a.numerator)


def normal_upper_quantile(alpha):
    """z with P(Z > z) = alpha / 2, from the lower tail z = -Phi^{-1}(alpha / 2) (no 1 - alpha / 2 cancellation).
    Refuses an alpha whose half is not a positive normal float."""
    a = validate_alpha(alpha)[0]
    half = float(a / 2)
    if not half >= 2.2250738585072014e-308:                          # the smallest positive normal double
        raise BlockInputError('alpha = %s is too small for a float normal quantile' % a)
    z = -NormalDist().inv_cdf(half)
    if not (math.isfinite(z) and z > 0):
        raise BlockInputError('the normal quantile for alpha = %s is not a finite positive float' % a)
    return z


def validate_alpha(alpha, p=None, alpha_parts=None):
    """0 < alpha < 1; with p, also nonrandom per-coordinate budgets alpha_j > 0 summing to at most alpha (default:
    the equal split alpha / p)."""
    a = exact(alpha, 'alpha')
    if not 0 < a < 1:
        raise BlockInputError('alpha must satisfy 0 < alpha < 1, got %s' % a)
    if p is None:
        return a, None
    if alpha_parts is None:
        return a, (a / p,) * p
    _sequence(alpha_parts, 'alpha_parts')
    if len(alpha_parts) != p:
        raise BlockInputError('alpha_parts must give %d budgets, got %d' % (p, len(alpha_parts)))
    parts = tuple(exact(x, 'alpha_parts[%d]' % j) for j, x in enumerate(alpha_parts))
    if any(x <= 0 for x in parts):
        raise BlockInputError('every alpha_j must be positive')
    if sum(parts) > a:
        raise BlockInputError('alpha_parts sum to %s, more than alpha = %s' % (sum(parts), a))
    return a, parts


def _vector(z, coords, where):
    if isinstance(z, Mapping):
        if set(z) != set(coords):
            raise BlockInputError('%s: z must have exactly the coordinates %s' % (where, list(coords)))
        z = [z[c] for c in coords]
    _sequence(z, where + ': z')
    if len(z) != len(coords):
        raise BlockInputError('%s: z has %d coordinates, expected %d %s' % (where, len(z), len(coords), list(coords)))
    return tuple(exact(v, '%s coordinate %s' % (where, c)) for v, c in zip(z, coords))


def _check_bounds(rows, ids, coords, bnds):
    for bid, z in zip(ids, rows):
        for c, v, (lo, hi) in zip(coords, z, bnds):
            if not lo <= v <= hi:
                raise BlockInputError('block %r coordinate %s = %s lies outside its declared bounds [%s, %s]; '
                                      'observations are never clipped' % (bid, c, v, lo, hi))


def summarize_blocks(blocks, coords, *, contract_id=None, bounds=None):
    """block records {'block_id', 'contract_id', 'z'} -> B, mean, unbiased sample covariance (B >= 2) and covariance
    of the mean. z is a sequence ordered as coords or a mapping keyed by exactly those names. Refuses an empty list,
    duplicate block IDs, mixed or unexpected contracts, malformed or nonfinite records and, when bounds are given,
    any out-of-bound observation."""
    coords = _coords(coords)
    _sequence(blocks, 'blocks')
    if not blocks:
        raise BlockInputError('no blocks: at least one complete block is required')
    if contract_id is not None:
        _contract(contract_id)
    bnds = validate_bounds(bounds, len(coords)) if bounds is not None else None
    ids, seen, contracts, rows = [], set(), set(), []
    for k, rec in enumerate(blocks):
        if not isinstance(rec, Mapping) or set(rec) != {'block_id', 'contract_id', 'z'}:
            raise BlockInputError('block record %d must be a mapping with exactly block_id, contract_id and z' % k)
        bid = _block_id(rec['block_id'], k)
        key = str(bid)                          # 1 and '1' are treated as the same identity (refused)
        if key in seen:
            raise BlockInputError('duplicate block_id %r' % (bid,))
        seen.add(key)
        contracts.add(_contract(rec['contract_id'], 'block %r contract_id' % (bid,)))
        ids.append(bid)
        rows.append(_vector(rec['z'], coords, 'block %r' % (bid,)))
    if len(contracts) > 1:
        raise BlockInputError('mixed frozen contracts %s; blocks must share one contract' % sorted(contracts))
    contract = contracts.pop()
    if contract_id is not None and contract != contract_id:
        raise BlockInputError('blocks carry contract %r, expected %r' % (contract, contract_id))
    if bnds is not None:
        _check_bounds(rows, ids, coords, bnds)
    B, p = len(rows), len(coords)
    mean = tuple(sum(r[j] for r in rows) / B for j in range(p))
    if B >= 2:
        cov = tuple(tuple(sum((r[i] - mean[i]) * (r[j] - mean[j]) for r in rows) / (B - 1) for j in range(p))
                    for i in range(p))
        cov_mean = tuple(tuple(x / B for x in row) for row in cov)
        status = 'available'
    else:
        cov = cov_mean = None
        status = 'unavailable: fewer than two complete blocks'
    return dict(version=VERSION, coords=coords, contract_id=contract, block_ids=tuple(ids), B=B, rows=tuple(rows),
                mean=mean, covariance=cov, covariance_of_mean=cov_mean, covariance_status=status, bounds=bnds,
                unit=UNIT, note=STRUCTURAL_NOTE)


def _coefficients(a, p):
    _sequence(a, 'contrast coefficients')
    if len(a) != p:
        raise BlockInputError('contrast needs %d coefficients, got %d' % (p, len(a)))
    return tuple(exact(x, 'coefficient %d' % j) for j, x in enumerate(a))


def _quad(a, cov):
    return sum(a[i] * a[j] * cov[i][j] for i in range(len(a)) for j in range(len(a)))


def linear_estimate(summary, a):
    """a'Zbar (unbiased for a'mu) and its unbiased variance estimate a'S_B a / B using the full covariance."""
    a = _coefficients(a, len(summary['coords']))
    est = sum(x * m for x, m in zip(a, summary['mean']))
    out = dict(coefficients=a, estimate=est, B=summary['B'], unit=summary['unit'])
    if summary['covariance'] is None:
        return dict(out, variance_of_estimate=None, status=summary['covariance_status'])
    return dict(out, variance_of_estimate=_quad(a, summary['covariance']) / summary['B'], status='available')


def _normal_interval(est, var, alpha, note, base):
    """shared Wald logic: refuses a zero, negative or nonfinite variance; no interval when alpha is None."""
    if var is None:
        return dict(base, status='unavailable: fewer than two complete blocks', interpretation=note)
    if not var > 0:
        return dict(base, status='unavailable: estimated variance is %s; a degenerate estimate is not reported as a '
                                 'zero-width interval' % var, interpretation=note)
    try:
        se = math.sqrt(float(var))
        centre = float(est)
    except OverflowError:
        se = centre = math.inf
    if not (math.isfinite(se) and math.isfinite(centre) and se > 0):
        return dict(base, status='unavailable: the variance or estimate is not a finite positive float',
                    interpretation=note)
    out = dict(base, status='available', se=se, interpretation=note, validated_coverage=False)
    if alpha is not None:
        z = normal_upper_quantile(alpha)
        lower, upper = centre - z * se, centre + z * se
        if not (math.isfinite(lower) and math.isfinite(upper)):
            return dict(base, status='unavailable: nonfinite Wald endpoint', se=se, alpha=alpha, z=z,
                        interpretation=note)
        out.update(alpha=alpha, z=z, lower=lower, upper=upper)
    return out


def wald(summary, a, alpha=None):
    """the Wald scale (and, with alpha, a two-sided interval) for a'mu. Asymptotic only; see WALD_NOTE."""
    if alpha is not None:
        alpha = validate_alpha(alpha)[0]
        normal_upper_quantile(alpha)                                  # refuse an unrepresentable alpha up front
    lin = linear_estimate(summary, a)
    base = dict(coefficients=lin['coefficients'], estimate=lin['estimate'], variance_of_estimate=
                lin['variance_of_estimate'], B=lin['B'], unit=lin['unit'])
    return _normal_interval(lin['estimate'], lin['variance_of_estimate'], alpha, WALD_NOTE, base)


def hoeffding_rectangle(summary, bounds, alpha, *, alpha_parts=None, mean_ranges=None):
    """eq. 5: I_j = [Zbar_j - eps_j, Zbar_j + eps_j] cap [l_j, u_j], eps_j = c_j sqrt(log(2 / alpha_j) / (2B)),
    then (optionally) cap the known range of mu_j (lower <= upper; a deterministic singleton is allowed). A
    component whose restricted interval is empty is reported with
    interval None; callers return a whole parameter range for it. Every observation must lie within the bounds."""
    coords, p, B = summary['coords'], len(summary['coords']), summary['B']
    bnds = validate_bounds(bounds, p)
    a, parts = validate_alpha(alpha, p, alpha_parts)
    ranges = validate_bounds(mean_ranges, p, 'mean_ranges') if mean_ranges is not None else None
    _check_bounds(summary['rows'], summary['block_ids'], coords, bnds)
    comps = []
    for j in range(p):
        lo, hi = bnds[j]
        eps = _finite_float(hi - lo, 'bound width c_j') * math.sqrt(_log_two_over(parts[j]) / (2 * B))
        m = _finite_float(summary['mean'][j], 'mean')
        raw = (m - eps, m + eps)
        if not (math.isfinite(eps) and math.isfinite(raw[0]) and math.isfinite(raw[1])):
            raise BlockInputError('coordinate %s: the Hoeffding interval is not finite' % coords[j])
        sup = (max(raw[0], _finite_float(lo, 'bound')), min(raw[1], _finite_float(hi, 'bound')))
        rest = sup if ranges is None else (max(sup[0], _finite_float(ranges[j][0], 'mean range')),
                                           min(sup[1], _finite_float(ranges[j][1], 'mean range')))
        empty = rest[0] > rest[1]
        comps.append(dict(coord=coords[j], alpha_j=parts[j], eps=eps, raw=raw, support_capped=sup,
                          interval=None if empty else rest, status='empty after the known range' if empty else 'ok'))
    return dict(B=B, alpha=a, alpha_parts=parts, bounds=bnds, mean_ranges=ranges, components=comps,
                coverage=RECTANGLE_NOTE, unit=summary['unit'])


def linear_set(rectangle, a, parameter_range):
    """eq. 10 in general form: [sum_j a_j (L_j if a_j > 0 else U_j), sum_j a_j (U_j if a_j > 0 else L_j)] cap the
    parameter range (lower <= upper; a singleton is allowed); the whole range when a required (a_j != 0) component
    is empty or the cap is empty."""
    comps = rectangle['components']
    a = _coefficients(a, len(comps))
    pr = _interval(parameter_range, 'parameter_range', strict=False)       # a singleton range is legitimate
    whole = (float(pr[0]), float(pr[1]))
    need = [j for j in range(len(comps)) if a[j] != 0]
    empty = [comps[j]['coord'] for j in need if comps[j]['interval'] is None]
    if empty:
        return dict(coefficients=a, interval=whole, status='whole range: empty restricted component %s' % empty)
    lo = sum(float(a[j]) * comps[j]['interval'][0 if a[j] > 0 else 1] for j in need)
    hi = sum(float(a[j]) * comps[j]['interval'][1 if a[j] > 0 else 0] for j in need)
    iv = (max(lo, whole[0]), min(hi, whole[1]))
    if iv[0] > iv[1]:
        return dict(coefficients=a, interval=whole, propagated=(lo, hi),
                    status='whole range: the propagated set misses the parameter range')
    return dict(coefficients=a, interval=iv, propagated=(lo, hi), status='finite-sample set')


def primary_analysis(blocks, *, contract_id, score_bounds, alpha, alpha_parts=None, wald_alpha=None):
    """the three primary contrasts: estimate and full-covariance variance, Wald scale (interval only with
    wald_alpha; marginal, not simultaneous) and the eq. 10 finite-sample sets from one rectangle (simultaneous)."""
    s = summarize_blocks(blocks, PRIMARY_COORDS, contract_id=contract_id, bounds=score_bounds)
    rect = hoeffding_rectangle(s, score_bounds, alpha, alpha_parts=alpha_parts,
                               mean_ranges=(PRIMARY_MEAN_RANGE,) * len(PRIMARY_COORDS))
    contrasts = {name: dict(linear=linear_estimate(s, a), wald=wald(s, a, wald_alpha),
                            finite_sample=linear_set(rect, a, PRIMARY_CONTRAST_RANGES[name]))
                 for name, a in PRIMARY_CONTRASTS.items()}
    return dict(version=VERSION, summary=s, rectangle=rect, contrasts=contrasts, unit=UNIT,
                multiplicity=('the finite-sample sets share one rectangle event and cover simultaneously; marginal '
                              'Wald intervals do not, and joint Wald inference needs a prespecified multiplicity '
                              'procedure'))


# ---------------------------------------------------------------- secondary: six-total branch/log illustration

def _nonneg_int(x, what, positive=False):
    if isinstance(x, bool) or not isinstance(x, int) or x < (1 if positive else 0):
        raise BlockInputError('%s must be a %s int, got %r' % (what, 'positive' if positive else 'nonnegative', x))
    return x


def latent_total_estimate(n_prefixes, selected, *, m0, r):
    """Prop. 3 for one block: That = N * Bhat, Bhat the mean of the m r observed pair contrasts over the
    m = min(m0, N) selected prefixes; That = 0 when N = 0 (selected must then be empty). selected holds one sequence
    of r contrasts in [-1, 1] per selected prefix. Whether the prefixes were drawn by simple random sampling, and
    whether (11) holds, is not checkable here."""
    N = _nonneg_int(n_prefixes, 'n_prefixes')
    m0, r = _nonneg_int(m0, 'm0', True), _nonneg_int(r, 'r', True)
    _sequence(selected, 'selected')
    m = min(m0, N)
    if len(selected) != m:
        raise BlockInputError('N = %d and m0 = %d need %d selected prefixes, got %d' % (N, m0, m, len(selected)))
    if N == 0:
        return Fraction(0)
    total = Fraction(0)
    for i, pairs in enumerate(selected):
        _sequence(pairs, 'selected[%d]' % i)
        if len(pairs) != r:
            raise BlockInputError('selected prefix %d has %d pair contrasts, expected r = %d' % (i, len(pairs), r))
        for j, d in enumerate(pairs):
            d = exact(d, 'pair contrast [%d][%d]' % (i, j))
            if not -1 <= d <= 1:
                raise BlockInputError('pair contrast [%d][%d] = %s lies outside [-1, 1]' % (i, j, d))
            total += d
    return N * total / (m * r)


def branch_bounds(n_max):
    """eq. 18 supports for (That, N, U1, D1, U0, D0) with L = n_max."""
    L = _nonneg_int(n_max, 'n_max', True)
    return ((-L, L), (0, L), (0, 4 * L), (0, 4 * L), (0, 4 * L), (0, 4 * L))


def validate_branch_vector(z, n_max, where='branch vector'):
    """|That| <= N, 0 <= Ua <= Da <= 4N, N an integer count in [0, n_max]; a zero-prefix vector is all zeros."""
    L = _nonneg_int(n_max, 'n_max', True)
    T, N, U1, D1, U0, D0 = _vector(z, BRANCH_COORDS, where)
    if N.denominator != 1 or not 0 <= N <= L:
        raise BlockInputError('%s: N = %s must be an integer prefix count in [0, %d]' % (where, N, L))
    if not abs(T) <= N:
        raise BlockInputError('%s: |N_times_branch_mean| = %s exceeds N = %s' % (where, abs(T), N))
    for U, D, arm in ((U1, D1, 1), (U0, D0, 0)):
        if not 0 <= U <= D <= 4 * N:
            raise BlockInputError('%s: arm %d needs 0 <= U <= D <= 4N, got U = %s, D = %s, N = %s'
                                  % (where, arm, U, D, N))
    return T, N, U1, D1, U0, D0


def summarize_branch_blocks(blocks, n_max, *, contract_id=None):
    """summarize_blocks over BRANCH_COORDS with eq. 18 bounds and the joint constraints of every block, which are
    all kept, including zero-prefix blocks."""
    s = summarize_blocks(blocks, BRANCH_COORDS, contract_id=contract_id, bounds=branch_bounds(n_max))
    for bid, z in zip(s['block_ids'], s['rows']):
        validate_branch_vector(z, n_max, 'block %r' % (bid,))
    return dict(s, n_max=n_max)


def _branch_summary(summary):
    if tuple(summary['coords']) != BRANCH_COORDS or 'n_max' not in summary:
        raise BlockInputError('a branch summary from summarize_branch_blocks is required')
    return summary


def branch_functional(mu):
    """eq. 15: mu1/mu2 - mu3/mu4 + mu5/mu6 with its three ratios; mu2, mu4, mu6 must be positive."""
    mu = tuple(exact(x, 'mu') for x in _sequence(mu, 'mu'))
    if len(mu) != 6:
        raise BlockInputError('mu must have 6 coordinates')
    if not (mu[1] > 0 and mu[3] > 0 and mu[5] > 0):
        raise BlockInputError('branch denominators mu2, mu4, mu6 must be positive, got %s' % [mu[1], mu[3], mu[5]])
    theta, nu1, nu0 = mu[0] / mu[1], mu[2] / mu[3], mu[4] / mu[5]
    return theta - nu1 + nu0, (theta, nu1, nu0)


def branch_gradient(mu):
    """eq. 17 at mu (positive denominators)."""
    branch_functional(mu)
    m = tuple(exact(x) for x in mu)
    return (1 / m[1], -m[0] / m[1] ** 2, -1 / m[3], m[2] / m[3] ** 2, 1 / m[5], -m[4] / m[5] ** 2)


def _zero_denominators(mean):
    return [c for c, j in (('N', 1), ('D1', 3), ('D0', 5)) if mean[j] == 0]


def branch_estimate(summary):
    """eq. 16: pooled totals, then ratios (equal to g(Zbar)); unavailable with an observed zero global denominator."""
    s = _branch_summary(summary)
    zero = _zero_denominators(s['mean'])
    if zero:
        return dict(estimate=None, status='unavailable: observed zero global denominator %s' % zero, B=s['B'],
                    unit=UNIT)
    est, (theta, nu1, nu0) = branch_functional(s['mean'])
    return dict(estimate=est, theta=theta, nu1=nu1, nu0=nu0, status='available', B=s['B'], unit=UNIT,
                note='pooled-total ratio estimator; not claimed unbiased at finite B')


def branch_wald(summary, alpha=None):
    """delta-method scale grad' S_B grad / B at Zbar with the full six-by-six covariance (and, with alpha, an
    interval). Asymptotic only; see DELTA_NOTE."""
    if alpha is not None:
        alpha = validate_alpha(alpha)[0]
        normal_upper_quantile(alpha)
    s = _branch_summary(summary)
    point = branch_estimate(s)
    base = dict(estimate=point['estimate'], B=s['B'], unit=UNIT)
    if point['estimate'] is None:
        return dict(base, status=point['status'], interpretation=DELTA_NOTE)
    if s['covariance'] is None:
        return dict(base, status=s['covariance_status'], interpretation=DELTA_NOTE)
    grad = branch_gradient(s['mean'])
    var = _quad(grad, s['covariance']) / s['B']
    return _normal_interval(point['estimate'], var, alpha, DELTA_NOTE, dict(base, gradient=grad,
                                                                             variance_of_estimate=var))


def ratio_interval(num, den):
    """eq. 19: the range of x / y over x in [l, u], y in [v, w] with v > 0, from the four corners (either numerator
    sign)."""
    l, u = _interval(num, 'numerator interval', strict=False)
    v, w = _interval(den, 'denominator interval', strict=False)
    if not v > 0:
        raise BlockInputError('ratio_interval needs a positive denominator interval, got [%s, %s]' % (v, w))
    corners = [l / v, l / w, u / v, u / w]
    return min(corners), max(corners)


def _ratio_float(num, den):
    corners = [num[0] / den[0], num[0] / den[1], num[1] / den[0], num[1] / den[1]]
    return min(corners), max(corners)


def _cap(iv, rng):
    out = (max(iv[0], float(rng[0])), min(iv[1], float(rng[1])))
    return out if out[0] <= out[1] else None


def branch_finite_set(summary, alpha, *, alpha_parts=None):
    """eqs. 18-20 finite-sample set for the branch/log contrast, with the whole range [-2, 2] when any denominator
    lower limit is nonpositive (including an observed zero denominator) or a required intersection is empty."""
    s = _branch_summary(summary)
    rect = hoeffding_rectangle(s, branch_bounds(s['n_max']), alpha, alpha_parts=alpha_parts)
    iv = [c['interval'] for c in rect['components']]
    whole = (float(BRANCH_RANGE[0]), float(BRANCH_RANGE[1]))
    low = [c for c, j in (('N', 1), ('D1', 3), ('D0', 5)) if not iv[j][0] > 0]
    if low:
        return dict(interval=whole, rectangle=rect, unit=UNIT,
                    status='whole range: nonpositive denominator lower limit %s' % low)
    theta = _cap(_ratio_float(iv[0], iv[1]), BRANCH_THETA_RANGE)
    nu1 = _cap(_ratio_float(iv[2], iv[3]), BRANCH_NU_RANGE)
    nu0 = _cap(_ratio_float(iv[4], iv[5]), BRANCH_NU_RANGE)
    empty = [n for n, x in (('theta', theta), ('nu1', nu1), ('nu0', nu0)) if x is None]
    if empty:
        return dict(interval=whole, rectangle=rect, unit=UNIT,
                    status='whole range: empty ratio intersection %s' % empty)
    out = _cap((theta[0] - nu1[1] + nu0[0], theta[1] - nu1[0] + nu0[1]), BRANCH_RANGE)
    if out is None:
        return dict(interval=whole, rectangle=rect, unit=UNIT, status='whole range: empty final intersection')
    return dict(interval=out, theta=theta, nu1=nu1, nu0=nu0, rectangle=rect, unit=UNIT, status='finite-sample set')
