"""Deterministic checks for the fixed-benchmark concentration memo; no data analysis/MC."""
import hashlib,itertools,json,math,pathlib
root=pathlib.Path(__file__).resolve().parents[2]
doc=root/'docs/theory_branch_fixed_benchmark_bound.md'
J,R,N,m,r,D1,D0=330,8,564,200,2,570,574
alpha=.0125
cs=4*(N-m)**2/m**2*sum(1/j**2 for j in range(N-m,N));ce=4/(m*r)
bB=R*math.sqrt(2*J*math.log(2/alpha))/N
b1=4*R*math.sqrt(J/2*math.log(2/alpha))/D1
b0=4*R*math.sqrt(J/2*math.log(2/alpha))/D0
bf=math.sqrt((cs+ce)/2*math.log(2/alpha))
point=.12-(184/570-108/574)
cond=math.sqrt((cs+ce)/2*math.log(40));ind=math.sqrt((cs+2/(m*r))/2*math.log(40))
# Exhaustive finite-population identity checks at a single nondegenerate population.
pop=(-1.,-.5,0.,.25,1.);n=len(pop);errors=[];mgfs=[]
for mm in range(1,n+1):
 C=0. if mm==n else 4*(n-mm)**2/mm**2*sum(1/j**2 for j in range(n-mm,n))
 vals=[]
 for order in itertools.permutations(range(n),mm):
  chosen=[];remaining=list(range(n));old=sum(pop)/n
  for k,i in enumerate(order,1):
   remmean=sum(pop[j] for j in remaining)/len(remaining)
   chosen.append(i);remaining.remove(i)
   new=sum(pop[j] for j in chosen)/mm
   if mm>k:new+=(mm-k)/mm*sum(pop[j] for j in remaining)/len(remaining)
   formula=0. if mm==n else (n-mm)/(mm*(n-k))*(pop[i]-remmean)
   errors.append(abs(new-old-formula));old=new
  vals.append(sum(pop[j] for j in order)/mm-sum(pop)/n)
 for lam in (-5.,-1.,1.,5.):
  mgf=sum(math.exp(lam*v) for v in vals)/len(vals);bound=math.exp(lam*lam*C/8)
  assert mgf<=bound+1e-12;mgfs.append(dict(N=n,m=mm,lambda_=lam,mgf=mgf,bound=bound))
assert max(errors)<1e-14
want=[.820934,1.624585,1.613264,.241256,4.300040,.205684,.181889]
got=[bB,b1,b0,bf,bB+b1+b0+bf,cond,ind]
assert all(abs(a-b)<5.1e-7 for a,b in zip(want,got))
report=dict(memo_sha256=hashlib.sha256(doc.read_bytes()).hexdigest(),scope='Review of stated construction and deterministic constants only. Exhaustive small-population identities are checks, not substitutes for the proof. No archive outcomes, MC or models.',constants=dict(C_S=cs,C_E=ce,b_B=bB,b_1=b1,b_0=b0,b_F=bf,total_radius=sum(got[:4]),point=point,full_interval=[max(-2,point-sum(got[:4])),min(2,point+sum(got[:4]))],conditional_pair_radius=cond,conditional_mean_interval=[.12-cond,.12+cond],conditional_gap_interval=[point-cond,point+cond],conditional_arm_independent_radius=ind,conditional_arm_independent_gap_interval=[point-ind,point+ind]),deterministic_selection_check=dict(population=pop,increment_checks=len(errors),max_increment_identity_error=max(errors),mgf_checks=mgfs),conclusion='No blocking mathematical issue. Coverage follows for the stated ratio-of-expectations target under independent bounded source-task blocks, conditional SRS and selection-invariant conditionally independent fresh replicate pairs; error budgets fixed. These assumptions and the target convention require separate scientific authorization/verification before empirical inference.',clarifications=['Coverage in equation9 integrates over source frames and includes whole-range fallback for N=0 or any D=0; it is not conditional-on-positive-denominators coverage.','The conditional frame excludes branch selection/outcomes; its gap target uses a fixed noisy log comparator and need not be zero.','The ratio convention and hypothetical repetition redraw assignment/seeds/outcomes, conditional only on benchmark/specifications. Conditioning on the archived realized design would be a different target/model.','No minimum task-specific denominator is required; positivity only of population global denominators.','No independence between T, both arm weighted totals or branch/log estimators is used in the union bound.','The bound does not assume source-law and branch-law calibration. That additional contract identifies Delta=0; absent it the same concentration covers the difference of the specified statistical/causal quantities.','Archive execution independence, stationarity and recovery selection invariance remain unverified here; width calculation returns full parameter range, not a validated useful empirical interval.'])
out=root/'docs/audits/fixed_benchmark_bound_review_aac69b5.json';out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['constants'],indent=2));print('max_identity_error',max(errors));print(out)
