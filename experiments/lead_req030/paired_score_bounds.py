"""Prospective descriptive bounds for realized complete assigned schedule scores.

Not confidence intervals, policy-value expectations, or H/P causal inference.
Unknown binary outcomes are unrestricted; no task/family is dropped.
"""
from itertools import product

SCHEDULES = ('SS', 'SL', 'LS', 'LL')


def paired_bounds(rows, task_ids, left='LL', right='SS'):
    ids = tuple(task_ids)
    if not ids or len(set(ids)) != len(ids) or left not in SCHEDULES or right not in SCHEDULES or left == right:
        raise ValueError('unique fixed task IDs and distinct schedules required')
    expected = {(t, s) for t in ids for s in SCHEDULES}
    if len(rows) != len(expected):
        raise ValueError('all assigned slots required')
    scores = {}
    for row in rows:
        key = (row['task_id'], row['schedule'])
        if key not in expected or key in scores:
            raise ValueError('foreign or duplicate assigned slot')
        value = row['correctness']
        if value not in ('resolved', 'unresolved', 'unknown'):
            raise ValueError('verified correctness or explicit unknown required')
        scores[key] = (1,) if value == 'resolved' else (0,) if value == 'unresolved' else (0, 1)
    families = []
    for task in ids:
        pairs = tuple(product(scores[task, left], scores[task, right]))
        contrasts = [a-b for a,b in pairs]
        gains = [int(a == 1 and b == 0) for a,b in pairs]
        losses = [int(a == 0 and b == 1) for a,b in pairs]
        families.append({'task_id': task, 'difference': [min(contrasts), max(contrasts)],
                         'gain': [min(gains), max(gains)], 'loss': [min(losses), max(losses)]})
    n = len(ids)
    return {'assigned_families': n, 'assigned_slots': len(expected), 'left': left, 'right': right,
            'difference_bounds': [sum(f['difference'][i] for f in families)/n for i in (0,1)],
            'gain_count_bounds': [sum(f['gain'][i] for f in families) for i in (0,1)],
            'loss_count_bounds': [sum(f['loss'][i] for f in families) for i in (0,1)],
            'families': families,
            'interpretation': 'Sharp missing-score bounds for realized assigned schedule scores; not CIs, policy expected values, population inference, or H/P effects.'}
