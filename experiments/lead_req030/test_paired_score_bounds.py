from itertools import product
import pytest
from experiments.lead_req030.paired_score_bounds import paired_bounds, SCHEDULES


def rows(values):
    return [{'task_id': t, 'schedule': s, 'correctness': values.get((t,s),'unresolved')}
            for t in ('a','b') for s in SCHEDULES]


@pytest.mark.parametrize('states', list(product(('resolved','unresolved','unknown'), repeat=4)))
def test_bounds_equal_exhaustive_completions(states):
    keys=[('a','LL'),('a','SS'),('b','LL'),('b','SS')]
    data=rows(dict(zip(keys,states)))
    result=paired_bounds(data,('a','b'))
    alternatives=[(1,) if s=='resolved' else (0,) if s=='unresolved' else (0,1) for s in states]
    completions=list(product(*alternatives))
    differences=[((c[0]-c[1])+(c[2]-c[3]))/2 for c in completions]
    gains=[int(c[0]>c[1])+int(c[2]>c[3]) for c in completions]
    losses=[int(c[0]<c[1])+int(c[2]<c[3]) for c in completions]
    assert result['difference_bounds']==[min(differences),max(differences)]
    assert result['gain_count_bounds']==[min(gains),max(gains)]
    assert result['loss_count_bounds']==[min(losses),max(losses)]


@pytest.mark.parametrize('mutation', ['missing','duplicate','foreign','invalid'])
def test_assignment_or_outcome_mutations_refused(mutation):
    data=rows({})
    if mutation=='missing':data.pop()
    if mutation=='duplicate':data[-1]=data[0]
    if mutation=='foreign':data[0]['task_id']='other'
    if mutation=='invalid':data[0]['correctness']='setup_pass'
    with pytest.raises(ValueError):paired_bounds(data,('a','b'))
