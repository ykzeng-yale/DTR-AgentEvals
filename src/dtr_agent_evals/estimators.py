"""Policy-correct IPW, iterated Q g-computation, and cross-fitted DR.

The tabular Q models are intentionally simple. Correct specification uses all
four Markov states; misspecification omits the evolving failure state. DR here
uses unaugmented iterated-Q fits, so claims are the ordinary all-Q OR all-b
robustness guarantee, not arbitrary stagewise multiple robustness of fitted Qs.
"""
import numpy as np
from .simulator import policy_probability


def target_probabilities(data, policy):
    h = data.a.shape[1]
    p = np.column_stack([policy_probability(policy,data.x,data.l[:,t],t,h) for t in range(h)])
    return np.where(data.a == 1, p, 1-p)


def weights(data, policy, behavior="known"):
    if behavior not in ("known", "misspecified"):
        raise ValueError(f"Unknown behavior specification {behavior}")
    b = data.b if behavior == "known" else np.full_like(data.b,.5)
    if np.any(~np.isfinite(b) | (b <= 0) | (b > 1)):
        raise ValueError("Observed action probabilities must lie in (0,1]")
    return np.cumprod(target_probabilities(data,policy)/b,axis=1)


def fit_q(train, policy, specification="correct"):
    if specification not in ("correct", "misspecified"):
        raise ValueError(f"Unknown Q specification {specification}")
    h = train.a.shape[1]
    q = np.zeros((h,2,2,2))
    next_v = np.zeros(len(train))
    for t in reversed(range(h)):
        y = train.r[:,t] + next_v
        for x in (0,1):
            for l in (0,1):
                for a in (0,1):
                    mask = (train.x==x)&(train.a[:,t]==a)
                    if specification == "correct":
                        mask &= train.l[:,t]==l
                    # Empty-cell fallback is explicitly recorded as a finite-sample limitation.
                    q[t,x,l,a] = np.mean(y[mask]) if mask.any() else np.mean(y)
        pa = policy_probability(policy,train.x,train.l[:,t],t,h)
        next_v = (1-pa)*q[t,train.x,train.l[:,t],0]+pa*q[t,train.x,train.l[:,t],1]
    return q


def dr_scores(data, policy, q, behavior="known"):
    h = data.a.shape[1]
    v = np.zeros((len(data),h+1))
    qa = np.zeros((len(data),h))
    for t in range(h):
        pa=policy_probability(policy,data.x,data.l[:,t],t,h)
        v[:,t]=(1-pa)*q[t,data.x,data.l[:,t],0]+pa*q[t,data.x,data.l[:,t],1]
        qa[:,t]=q[t,data.x,data.l[:,t],data.a[:,t]]
    w=weights(data,policy,behavior)
    return v[:,0]+np.sum(w*(data.r+v[:,1:]-qa),axis=1),v[:,0]


def score_summary(scores):
    estimate=float(np.mean(scores))
    se=float(np.std(scores,ddof=1)/np.sqrt(len(scores)))
    return {"estimate":estimate,"se":se,"lower":estimate-1.96*se,"upper":estimate+1.96*se}


def evaluate(data,policy,seed=0,folds=3,q_spec="correct",behavior="known"):
    if len(data)<folds*8:
        raise ValueError("Insufficient independent trajectories for requested folds")
    indices=np.random.default_rng(seed).permutation(len(data))
    split=np.array_split(indices,folds)
    scores=np.zeros(len(data)); plugin=np.zeros(len(data))
    empty_cells=0
    for heldout in split:
        train_idx=np.setdiff1d(indices,heldout)
        train=data.subset(train_idx)
        q=fit_q(train,policy,q_spec)
        scores[heldout],plugin[heldout]=dr_scores(data.subset(heldout),policy,q,behavior)
        for t in range(data.a.shape[1]):
            for x in (0,1):
                for l in (0,1):
                    for a in (0,1):
                        empty_cells += int(not np.any((train.x==x)&(train.l[:,t]==l)&(train.a[:,t]==a)))
    w=weights(data,policy,behavior)
    ipw=np.sum(w*data.r,axis=1)
    sumw=np.sum(w,axis=0); sumw2=np.sum(w*w,axis=0)
    ess=np.divide(sumw**2,sumw2,out=np.zeros_like(sumw),where=sumw2>0)
    return {"ipw":score_summary(ipw),"dr":score_summary(scores),
            "gcomp":{"estimate":float(np.mean(plugin)),"se":None,"lower":None,"upper":None},
            "diagnostics":{"ess_by_stage":ess.tolist(),"mean_weight_by_stage":np.mean(w,axis=0).tolist(),
              "max_weight_by_stage":np.max(w,axis=0).tolist(),
              "zero_weight_fraction":float(np.mean(w[:,-1]==0)),
              "min_behavior_probability":float(np.min(data.b)),
              "empty_training_cells_across_folds":empty_cells}}
