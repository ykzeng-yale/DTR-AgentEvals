#!/usr/bin/env python3
"""Audit existing immutable raw logs and write derived pilot summaries."""
import argparse,json,math
from collections import defaultdict
from pathlib import Path
import numpy as np
from dtr_agent_evals.local_pilot import action_probability,parse_answer


def wilson(k,n):
    z=1.96;p=k/n;den=1+z*z/n
    mid=(p+z*z/(2*n))/den;rad=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [mid-rad,mid+rad]


def summarize(directory):
    out=Path(directory);manifest=json.loads((out/'manifest.json').read_text());cfg=manifest['config']
    episodes=[json.loads(l) for l in (out/'episodes.jsonl').read_text().splitlines()]
    events=[json.loads(l) for l in (out/'events.jsonl').read_text().splitlines()]
    tasks={f"arithmetic-{x['seed']}":x for x in json.loads((out/'tasks.json').read_text())}
    grouped=defaultdict(list)
    for e in events:grouped[e['episode_id']].append(e)
    problems=[]
    for ep in episodes:
        ev=grouped[ep['episode_id']];task=tasks[ep['task_id']]
        if len(ev)!=cfg['horizon']:problems.append('wrong horizon')
        for t,e in enumerate(ev):
            if e['stage']!=t:problems.append('noncontiguous stage order')
            if e['previous_correct']!=(None if t==0 else ev[t-1]['correct']):problems.append('previous correctness mismatch')
            if e['action'] not in (0,1):problems.append('invalid action')
            elif e['model']!=cfg['models'][e['action']]:problems.append('action model mismatch')
            if parse_answer(e['response'],allow_reasoning=cfg.get('allow_reasoning',False))!=e['parsed_answer']:problems.append('reparsed response mismatch')
            if e['correct']!=(e['parsed_answer']==task['answer']):problems.append('validator mismatch')
            p=action_probability(e['regime'],e['stage'],e['previous_correct'])
            if p!=e['probability_large']:problems.append('propensity mismatch')
            if e['observed_action_probability']!=(p if e['action'] else 1-p):problems.append('observed action probability mismatch')
            if e['reward']!=(float(e['correct']) if t==cfg['horizon']-1 else 0.):problems.append('reward mismatch')
            if e['resource_proxy']!=cfg['resource_cost'][e['action']]:problems.append('resource proxy mismatch')
            if abs(e['utility_increment']-(e['reward']-e['resource_proxy']))>1e-12:problems.append('event utility mismatch')
            if e['model_digest']!=manifest['model_digests'][e['model']]:problems.append('digest mismatch')
        if abs(sum(e['utility_increment'] for e in ev)-ep['utility'])>1e-12:problems.append('utility mismatch')
        if ep['final_success']!=int(ev[-1]['correct']):problems.append('terminal success mismatch')
        if ep['actions']!=[e['action'] for e in ev]:problems.append('episode action mismatch')
        if ep['correctness']!=[e['correct'] for e in ev]:problems.append('episode correctness mismatch')
    logging=[e for e in episodes if e['regime']=='logging'];holdout=[e for e in episodes if e['regime']!='logging']
    log_ids={e['task_id'] for e in logging};held_ids={e['task_id'] for e in holdout}
    if log_ids&held_ids:problems.append('evaluation task leakage')
    summaries=[];ope=[]
    for regime in ['logging']+cfg['evaluation_regimes']:
        eps=[e for e in episodes if e['regime']==regime];n=len(eps);success=sum(e['final_success'] for e in eps)
        summaries.append({'regime':regime,'n':n,'successes':success,'success_rate':success/n,
          'success_wilson_95':wilson(success,n),'mean_utility':float(np.mean([e['utility'] for e in eps])),
          'mean_resource_proxy':float(np.mean([e['resource_proxy'] for e in eps])),
          'mean_generated_tokens':float(np.mean([e['generated_tokens'] for e in eps])),
          'median_wall_seconds':float(np.median([e['wall_seconds'] for e in eps])),
          'switch_trajectories':sum(e['switched'] for e in eps)})
    for regime in cfg['evaluation_regimes']:
        scores=[];weights=[]
        for ep in logging:
            w=1.;score=0.;stage_weights=[]
            for e in grouped[ep['episode_id']]:
                p=action_probability(regime,e['stage'],e['previous_correct']);numerator=p if e['action'] else 1-p
                w*=numerator/e['observed_action_probability'];stage_weights.append(w)
                score+=w*e['utility_increment']
            scores.append(score);weights.append(stage_weights)
        weights=np.array(weights);scores=np.array(scores);sw=np.sum(weights,axis=0);sw2=np.sum(weights**2,axis=0)
        se=float(scores.std(ddof=1)/np.sqrt(len(scores)));mean=float(scores.mean())
        ope.append({'target_regime':regime,'n_logging':len(logging),'ipw_utility':mean,'nominal_score_se':se,
          'nominal_normal_interval':[mean-1.96*se,mean+1.96*se],
          'ess_by_stage':np.divide(sw*sw,sw2,out=np.zeros_like(sw),where=sw2>0).tolist(),
          'max_weight_by_stage':np.max(weights,axis=0).tolist(),'terminal_positive_weights':int(np.sum(weights[:,-1]>0)),
          'support_warning':'No target-compatible completed trajectories; normal approximation is not credible.' if not np.any(weights[:,-1]>0) else 'Small target-compatible sample; do not use this pilot for policy improvement claims.',
          'interpretation':'Tiny exploratory sample; nominal intervals may be unreliable. This is not evidence of model or policy superiority.'})
    # Pair held-out policies by the shared task, not by generated model seed.
    baseline={e['task_id']:e['utility'] for e in holdout if e['regime']=='always_small'};paired=[]
    for regime in cfg['evaluation_regimes']:
        differences=np.array([e['utility']-baseline[e['task_id']] for e in holdout if e['regime']==regime]);n=len(differences)
        rng=np.random.default_rng(cfg['seed']+5000);boot=np.mean(differences[rng.integers(0,n,size=(5000,n))],axis=1)
        paired.append({'regime':regime,'baseline':'always_small','tasks':n,'mean_utility_difference':float(differences.mean()),'paired_task_bootstrap_95':np.quantile(boot,[.025,.975]).tolist(),'bootstrap_seed':cfg['seed']+5000,'bootstrap_replicates':5000,'interpretation':'Exploratory percentile bootstrap, no multiplicity adjustment or guaranteed small-sample coverage.'})
    result={'audit':{'issues':problems,'events':len(events),'episodes':len(episodes),'all_responses_parsed':all(e['parsed_answer'] is not None for e in events),'stage_correct':sum(e['correct'] for e in events),'logging_task_ids_disjoint_from_evaluation':not bool(log_ids&held_ids),'independent_unique_heldout_tasks':len(held_ids)},'direct_rollout':summaries,'off_policy':ope,'paired_comparisons':paired}
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result['audit']))
    if problems:raise RuntimeError(problems)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');summarize(p.parse_args().directory)
