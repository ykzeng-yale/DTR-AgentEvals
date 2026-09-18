#!/usr/bin/env python3
"""Honest finite-candidate policy selection with independent OPE evaluation."""
import argparse,json,platform,time
from pathlib import Path
import numpy as np
from dtr_agent_evals.simulator import Environment,simulate,exact_value
from dtr_agent_evals.estimators import evaluate
p=argparse.ArgumentParser();p.add_argument('--config',default='configs/policy_learning.json');p.add_argument('--output',default='results/policy_learning');a=p.parse_args()
cfg=json.loads(Path(a.config).read_text());out=Path(a.output)
if out.exists() and any(out.iterdir()):raise FileExistsError(out)
out.mkdir(parents=True,exist_ok=True);env=Environment(**cfg['environment']);truth={p:exact_value(env,p) for p in cfg['policies']};oracle=max(truth.values());rows=[];start=time.time()
for rep in range(cfg['replicates']):
    train=simulate(cfg['train_n'],np.random.default_rng(cfg['seed']+rep),env)
    estimates={policy:evaluate(train,policy,seed=cfg['seed']+rep,folds=cfg['folds'])['dr']['estimate'] for policy in cfg['policies']}
    selected=max(cfg['policies'],key=estimates.get)
    heldout=simulate(cfg['evaluation_n'],np.random.default_rng(cfg['seed']+100000+rep),env)
    result=evaluate(heldout,selected,seed=cfg['seed']+200000+rep,folds=cfg['folds'])['dr']
    rows.append({'replicate':rep,'selected_policy':selected,'training_estimate':estimates[selected],'selected_truth':truth[selected],'evaluation_estimate':result['estimate'],'evaluation_lower':result['lower'],'evaluation_upper':result['upper'],'finite_class_regret':oracle-truth[selected],'gain_over_always_small':truth[selected]-truth['always_small']})
summary={'replicates':len(rows),'selection_counts':{p:sum(r['selected_policy']==p for r in rows) for p in cfg['policies']},'exact_candidate_values':truth,'mean_training_optimism':float(np.mean([r['training_estimate']-r['selected_truth'] for r in rows])),'mean_independent_evaluation_bias':float(np.mean([r['evaluation_estimate']-r['selected_truth'] for r in rows])),'independent_evaluation_rmse':float(np.sqrt(np.mean([(r['evaluation_estimate']-r['selected_truth'])**2 for r in rows]))),'independent_evaluation_coverage_95':float(np.mean([r['evaluation_lower']<=r['selected_truth']<=r['evaluation_upper'] for r in rows])),'mean_finite_class_regret':float(np.mean([r['finite_class_regret'] for r in rows])),'mean_true_gain_over_always_small':float(np.mean([r['gain_over_always_small'] for r in rows]))}
(out/'replicates.json').write_text(json.dumps(rows,indent=2)+'\n');(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(out/'run_manifest.json').write_text(json.dumps({'config':cfg,'elapsed_seconds':time.time()-start,'platform':platform.platform(),'numpy':np.__version__,'interpretation':'Simulation only; finite prespecified policy menu, independent training/evaluation trajectories, no learned LLM router claim.'},indent=2)+'\n');print(json.dumps(summary))
