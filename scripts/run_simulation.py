#!/usr/bin/env python3
"""Run prespecified Monte Carlo experiment; every replicate is saved."""
import argparse,csv,json,platform,sys,time
from pathlib import Path
import numpy as np
from dtr_agent_evals.simulator import Environment,POLICIES,simulate,exact_value
from dtr_agent_evals.estimators import evaluate


def main():
    p=argparse.ArgumentParser();p.add_argument("--config",default="configs/simulation.json")
    p.add_argument("--output",default="results/simulation")
    args=p.parse_args(); cfg=json.loads(Path(args.config).read_text());out=Path(args.output)
    if out.exists() and any(out.iterdir()):raise FileExistsError(f"Refusing to overwrite nonempty result directory: {out}")
    out.mkdir(parents=True,exist_ok=True)
    env=Environment(**cfg["environment"]);records=[];diagnostics=[];start=time.time()
    truths={k:exact_value(env,k) for k in cfg["policies"]}
    mc={}
    for j,policy in enumerate(cfg["policies"]):
        truth_data=simulate(cfg["truth_mc_n"],np.random.default_rng(cfg["seed"]+100000+j),env,policy)
        rewards=truth_data.r.sum(1)
        mc[policy]={"exact":truths[policy],"on_policy_mc":float(rewards.mean()),"mc_se":float(rewards.std(ddof=1)/np.sqrt(len(rewards)))}
    for rep in range(cfg["replicates"]):
        data=simulate(cfg["n"],np.random.default_rng(cfg["seed"]+rep),env)
        for policy in cfg["policies"]:
            for qspec,behavior in cfg["specifications"]:
                ans=evaluate(data,policy,seed=cfg["seed"]+rep,folds=cfg["folds"],q_spec=qspec,behavior=behavior)
                for method in ("ipw","gcomp","dr"):
                    r=ans[method];records.append({"replicate":rep,"policy":policy,"q_spec":qspec,"behavior":behavior,"method":method,**r,"truth":truths[policy]})
                diagnostics.append({"replicate":rep,"policy":policy,"q_spec":qspec,"behavior":behavior,**ans["diagnostics"]})
        if (rep+1)%50==0:print(f"completed {rep+1}/{cfg['replicates']}",flush=True)
    with (out/"replicates.csv").open("w") as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    summary=[]
    for policy in cfg["policies"]:
        for qs,b in cfg["specifications"]:
            for method in ("ipw","gcomp","dr"):
                rows=[r for r in records if (r["policy"],r["q_spec"],r["behavior"],r["method"])==(policy,qs,b,method)]
                error=np.array([r["estimate"]-r["truth"] for r in rows]);cover=None
                if rows[0]["lower"] is not None:cover=float(np.mean([r["lower"]<=r["truth"]<=r["upper"] for r in rows]))
                summary.append({"policy":policy,"q_spec":qs,"behavior":b,"method":method,"bias":float(error.mean()),"bias_mc_se":float(error.std(ddof=1)/np.sqrt(len(error))),"rmse":float(np.sqrt(np.mean(error**2))),"coverage_95":cover,"coverage_mc_se":None if cover is None else float(np.sqrt(cover*(1-cover)/len(error)))})
    (out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    (out/"truth.json").write_text(json.dumps(mc,indent=2)+"\n")
    (out/"diagnostics.json").write_text(json.dumps(diagnostics,indent=2)+"\n")
    (out/"run_manifest.json").write_text(json.dumps({"config":cfg,"python":sys.version,"numpy":np.__version__,"platform":platform.platform(),"elapsed_seconds":time.time()-start,"seed_rule":"simulation seed + replicate; truth seed + 100000 + policy index"},indent=2)+"\n")
    print(json.dumps({"output":str(out),"elapsed_seconds":time.time()-start}))
if __name__=="__main__":main()
