#!/usr/bin/env python3
import csv, hashlib, itertools, json, math, os, random, resource, statistics, subprocess, sys, time
from collections import defaultdict
from datetime import datetime, timezone
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / 'config.json').read_text())
def now(): return datetime.now(timezone.utc).isoformat()
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(name, obj):
    with (ROOT/name).open('x') as f: json.dump(obj, f, indent=2, sort_keys=True)
def seed(eta):
    return int.from_bytes(hashlib.sha256(f"{CFG['root_seed']}|DTR-REQ-027|eta={eta}".encode()).digest(), 'big')
def score(a, feedback, y):
    return 2 * (int(a == feedback) - int(a == 0)) * (y-F(1,2))
def exact(eta, p):
    dist = defaultdict(F)
    q = F(CFG['q'])
    for u,e,a,y,i in itertools.product((0,1), repeat=5):
        py = F(1,2)+eta*(2*a-1)*(2*u-1)
        prob = (p if u else 1-p)*(q if e else 1-q)*F(1,2)*(py if y else 1-py)*F(1,2)
        d = score(a,u^e,y)
        dist[(d,2*i*d)] += prob
    assert sum(dist.values()) == 1
    target = 2*eta*(p-q)
    result = {'target':str(target), 'disagreement':str(q+p*(1-2*q))}
    for k,label in enumerate(('fixed','half')):
        mean = sum(x[k]*prob for x,prob in dist.items())
        second = sum(x[k]**2*prob for x,prob in dist.items())
        assert mean == target
        assert second == (k+1)*(q+p*(1-2*q))
        marginal=defaultdict(F)
        for x,prob in dist.items(): marginal[x[k]] += prob
        expected_s2=F(0)
        for vals in itertools.product(marginal,repeat=4):
            prob=math.prod(marginal[x] for x in vals)
            mean4=sum(vals)/4
            s2=sum((x-mean4)**2 for x in vals)/3
            expected_s2 += prob*s2
        assert expected_s2 == second-mean**2
        result[label]={'mean':str(mean),'second_moment':str(second),'variance':str(second-mean**2), 'enumerated_expected_sample_variance_R4':str(expected_s2)}
    return result
def gate():
    output=subprocess.check_output(['/usr/bin/memory_pressure'],text=True,timeout=10)
    percent=int(output.split('System-wide memory free percentage: ')[1].split('%')[0])
    load=os.getloadavg()[0]
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    size=sum(p.stat().st_size for p in ROOT.iterdir() if p.is_file())
    record={'time':now(),'memory_free_percent':percent,'load1':load,'own_peak_rss_bytes':rss,'output_bytes':size}
    record['passed']=percent>=30 and load<=8 and rss<CFG['memory_cap_bytes'] and size<CFG['output_cap_bytes']
    return record
def prepare():
    truths={}
    for eta_s in CFG['cells']:
        eta=F(eta_s)
        tasks=[exact(eta,F(p)) for p in ('1/4','3/4')]
        truth=sum(F(t['target']) for t in tasks)/2
        predictions={label:sum(F(t[label]['variance']) for t in tasks)/2/160 for label in ('fixed','half')}
        assert truth == (0 if eta==0 else F(1,10))
        assert predictions['fixed']==(F(1,320) if eta==0 else F(3,1000))
        assert predictions['half']==(F(1,160) if eta==0 else F(49,8000))
        truths[eta_s]={'tasks':tasks,'target':str(truth),'estimator_variance':{k:str(v) for k,v in predictions.items()}}
    # Independent check of cancellation and sample variance identity for nonbinary data.
    assert score(1,1,1)==1 and score(0,1,1)==-1 and score(1,0,0)==0
    initial=gate()
    assert initial['passed'], initial
    write('exact_truths.json', truths)
    write('deterministic_tests.json', {'status':'PASS','time':now(),'tests':['enumerated joint probability mass','both score means per task and cell','both second moments per task and cell','exact four-replicate expected sample variances','fixed-task target and estimator variance identities','score signs and agreement zero'],'resource_admission':initial})
    write('manifest.json', {'frozen_at':now(),'request':CFG['request'],'python':sys.version,'sources':{n:digest(ROOT/n) for n in ('config.json','run.py','exact_truths.json','deterministic_tests.json')},'cell_seeds':{s:str(seed(s)) for s in CFG['cells']},'command':'python3 run.py simulate','raw_unit':'one complete study; equal mean of 40 task means with 4 score draws each','paired_comparison':'common U,E,A2,Y across loggers and independent I for half logger; studies independent; per-cell independent SHA256-derived streams','variance_comparison_mcse':'delete-one-study paired jackknife of unbiased sample variance(half)-sample variance(fixed)','failure_rule':'zero/nonfinite estimated variance => Wald noncoverage; preserve all completed rows; partial studies not inferred; no extensions'})
    print('PREPARED: exact tests passed; manifest frozen before sampling')
def summarize(rows,eta,truths):
    n=len(rows); truth=float(F(truths[eta]['target']))
    out={'completed_studies':n,'target':truth,'loggers':{}}
    if n<2:return out
    for label,width in (('fixed',4),('half',8)):
        xs=[r[label+'_estimate'] for r in rows]; vs=[r[label+'_variance_estimate'] for r in rows]
        empirical=statistics.variance(xs); bias=statistics.mean(xs)-truth
        cover=[r[label+'_wald_cover'] for r in rows]; hc=[r[label+'_hoeffding_cover'] for r in rows]
        c=statistics.mean(cover)
        out['loggers'][label]={'bias':bias,'bias_mcse':math.sqrt(empirical/n),'empirical_variance':empirical,'exact_predicted_variance':float(F(truths[eta]['estimator_variance'][label])),'rmse':math.sqrt(statistics.mean((x-truth)**2 for x in xs)),'mean_estimated_variance':statistics.mean(vs),'estimated_variance_mean_mcse':statistics.stdev(vs)/math.sqrt(n),'wald_coverage':c,'wald_coverage_mcse':math.sqrt(c*(1-c)/n),'mean_wald_length':statistics.mean(r[label+'_wald_length'] for r in rows),'zero_nonfinite_variance_failures':sum(r[label+'_variance_failure'] for r in rows),'hoeffding_coverage':statistics.mean(hc),'hoeffding_width':2*width*math.sqrt(math.log(40)/(2*160))}
    x=[r['fixed_estimate'] for r in rows]; y=[r['half_estimate'] for r in rows]
    sx,sy=sum(x),sum(y); qx,qy=sum(a*a for a in x),sum(a*a for a in y)
    loo=[((qy-b*b)-(sy-b)**2/(n-1))/(n-2)-((qx-a*a)-(sx-a)**2/(n-1))/(n-2) for a,b in zip(x,y)]
    jackmean=statistics.mean(loo)
    se=math.sqrt((n-1)/n*sum((v-jackmean)**2 for v in loo))
    diff=statistics.variance(y)-statistics.variance(x)
    out['paired_variance_comparison']={'half_minus_fixed':diff,'paired_jackknife_mcse':se,'descriptive_mc_95_interval':[diff-1.959963984540054*se,diff+1.959963984540054*se],'exact_half_minus_fixed':float(F(truths[eta]['estimator_variance']['half'])-F(truths[eta]['estimator_variance']['fixed'])),'empirical_half_over_fixed':statistics.variance(y)/statistics.variance(x),'paired_mean_difference':statistics.mean(b-a for a,b in zip(x,y)),'paired_mean_difference_mcse':statistics.stdev(b-a for a,b in zip(x,y))/math.sqrt(n)}
    return out
def simulate():
    manifest=json.loads((ROOT/'manifest.json').read_text())
    for name,sha in manifest['sources'].items(): assert digest(ROOT/name)==sha, name
    assert not (ROOT/'status.json').exists() and not (ROOT/'studies.csv').exists()
    resource.setrlimit(resource.RLIMIT_CPU,(300,301))
    resource.setrlimit(resource.RLIMIT_AS,(CFG['memory_cap_bytes'],CFG['memory_cap_bytes']))
    os.nice(15)
    start=time.monotonic(); status={'started_at':now(),'status':'RUNNING'}; monitors=[]; allrows={s:[] for s in CFG['cells']}
    truths=json.loads((ROOT/'exact_truths.json').read_text())
    try:
        with (ROOT/'studies.csv').open('x',newline='') as fp:
            writer=None
            for eta_s in CFG['cells']:
                rng=random.Random(seed(eta_s)); eta=float(F(eta_s)); truth=float(F(truths[eta_s]['target']))
                for study in range(CFG['studies_per_cell']):
                    if study%100==0:
                        obs=gate();monitors.append(obs)
                        if not obs['passed']:raise RuntimeError('resource contention gate: '+str(obs))
                    if time.monotonic()-start>300:raise TimeoutError('simulation wall cap')
                    totals=[0.,0.]; sum_s2=[0.,0.]
                    for g in range(40):
                        p=.25 if g<20 else .75; sums=[0.,0.]; squares=[0.,0.]
                        for rep in range(4):
                            u=int(rng.random()<p);e=int(rng.random()<.25);a=int(rng.random()<.5)
                            y=int(rng.random()<.5+eta*(2*a-1)*(2*u-1));i=int(rng.random()<.5)
                            fixed=(int(a==(u^e))-int(a==0))*(2*y-1)
                            for k,d in enumerate((fixed,2*i*fixed)):
                                sums[k]+=d;squares[k]+=d*d
                        for k in (0,1):
                            totals[k]+=sums[k]/4
                            sum_s2[k]+=(squares[k]-sums[k]**2/4)/3
                    row={'cell_eta':eta_s,'study':study}
                    for k,(label,width) in enumerate((('fixed',4),('half',8))):
                        estimate=totals[k]/40;v=sum_s2[k]/(40**2*4)
                        failure=not math.isfinite(v) or v<=0
                        half=CFG['wald_z']*math.sqrt(v) if not failure else 0
                        h=width*math.sqrt(math.log(40)/(2*160))
                        row.update({label+'_estimate':estimate,label+'_variance_estimate':v,label+'_variance_failure':int(failure),label+'_wald_cover':int(not failure and abs(estimate-truth)<=half),label+'_wald_length':2*half,label+'_hoeffding_cover':int(abs(estimate-truth)<=h)})
                    if writer is None:writer=csv.DictWriter(fp,fieldnames=list(row));writer.writeheader()
                    writer.writerow(row);fp.flush();allrows[eta_s].append(row)
        status['status']='COMPLETE'
    except BaseException as exc:
        status.update(status='PARTIAL_OR_FAILED',error=repr(exc))
    finally:
        status.update(finished_at=now(),simulation_wall_seconds=time.monotonic()-start,counts={k:len(v) for k,v in allrows.items()},peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        write('resource_observations.json',monitors)
        write('summary.json',{s:summarize(rows,s,truths) for s,rows in allrows.items()})
        write('status.json',status)
        write('sha256.json',{p.name:digest(p) for p in sorted(ROOT.iterdir()) if p.is_file()})
        print(json.dumps(status,indent=2))
    if status['status']!='COMPLETE':sys.exit(1)
if __name__=='__main__':
    {'prepare':prepare,'simulate':simulate}[sys.argv[1]]()
