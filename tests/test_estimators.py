import itertools
import unittest
import numpy as np
from dtr_agent_evals.simulator import Environment,Trajectories,POLICIES,simulate,exact_q,exact_value,policy_probability
from dtr_agent_evals.estimators import weights,dr_scores,evaluate


def enumerate_paths(env):
    rows=[]; probabilities=[]
    for x,l0 in itertools.product((0,1),repeat=2):
        initial=.5*(env.initial_failure_probability(x) if l0 else 1-env.initial_failure_probability(x))
        for actions in itertools.product((0,1),repeat=env.horizon):
            for following in itertools.product((0,1),repeat=env.horizon):
                ll=(l0,)+following;prob=initial;bb=[];rr=[]
                for t,a in enumerate(actions):
                    pa=env.behavior_probability(x,ll[t],t);ba=pa if a else 1-pa
                    pf=env.failure_probability(x,ll[t],a)
                    prob*=ba*(pf if ll[t+1] else 1-pf)
                    bb.append(ba);rr.append(env.reward(ll[t+1],a,t))
                rows.append((x,ll,actions,bb,rr));probabilities.append(prob)
    return Trajectories(*(np.array([r[j] for r in rows]) for j in range(5))),np.array(probabilities)


class TestEstimators(unittest.TestCase):
    def test_exact_dr_and_ipw_by_full_enumeration(self):
        env=Environment();data,prob=enumerate_paths(env)
        self.assertAlmostEqual(prob.sum(),1)
        for policy in POLICIES:
            q,_=exact_q(env,policy);truth=exact_value(env,policy)
            self.assertAlmostEqual(float(prob@np.sum(weights(data,policy)*data.r,axis=1)),truth,places=12)
            for qhat,behavior in ((q,"known"),(q,"misspecified"),(np.zeros_like(q),"known")):
                score,_=dr_scores(data,policy,qhat,behavior)
                self.assertAlmostEqual(float(prob@score),truth,places=12)

    def test_missing_target_numerator_is_wrong(self):
        env=Environment();data,prob=enumerate_paths(env)
        wrong=np.sum(np.cumprod(1/data.b,axis=1)*data.r,axis=1)
        self.assertGreater(abs(float(prob@wrong)-exact_value(env,"always_small")),.5)

    def test_behavior_and_stochastic_target_have_overlap(self):
        env=Environment();data=simulate(100,np.random.default_rng(8),env)
        self.assertTrue(np.all((data.b>0)&(data.b<1)))
        target=policy_probability("soft_escalation",data.x,data.l[:,0],0)
        self.assertTrue(np.all((target>0)&(target<1)))

    def test_truth_matches_independent_rollout(self):
        env=Environment()
        for j,policy in enumerate(POLICIES):
            data=simulate(150000,np.random.default_rng(j),env,policy)
            self.assertLess(abs(data.r.sum(1).mean()-exact_value(env,policy)),.005)

    def test_crossfit_is_reproducible(self):
        data=simulate(1000,np.random.default_rng(91))
        first=evaluate(data,"failure_escalation",seed=6)
        self.assertEqual(first,evaluate(data,"failure_escalation",seed=6))
        self.assertTrue(0<first["diagnostics"]["ess_by_stage"][-1]<=len(data))

    def test_zero_propensity_rejected(self):
        data=simulate(20,np.random.default_rng(1));data.b[0,0]=0
        with self.assertRaises(ValueError): weights(data,"always_small")

if __name__=="__main__":unittest.main()
