# What a replay comparator can test

**20 September 2026; response to `560135e`.** This note clarifies the target of the newly implemented replay controls. It is a bounded theoretical check, not an empirical performance result or a new general replay theorem. An independent mathematical reviewer checked the constructions below. The existing manuscript's frozen-state counterexample remains valid and already states that not every replay method is invalid.

## Retaining an outcome differs from recomputing it with a frozen state

In `docs/theory.md` Section 7.1, the environment has $L_2=A_1$ and $Y=1\{A_2=L_2\}$. A recorded $(A_1,A_2)=(0,0)$ trajectory has $L_2=0,Y=1$. The target $(1,1)$ generates $L_2=1$ and hence $Y=1$. Recomputing the reward with target $A_2=1$ but frozen $L_2=0$ instead gives zero.

The new Rule A retains the recorded **outcome** without recomputing that reward. It returns one in this example, just as the live target does. It is policy-independent and generally cannot distinguish policies, but it is not the particular erroneous transformation in the counterexample. Label the implemented operations literally. A mathematical counterexample disproves universal validity; it does not predict failure of every differently specified method on every benchmark.

## An exact adaptive-policy failure with full donor availability

Consider a two-decision system. The first action is fixed at zero. Its state $U$ is a fair Bernoulli variable, and visible validation always fails at this first decision. At the second decision, the randomized logger draws $A$ independently of $U$, with $P(A=1)=1/2$. Hidden-test success is $Y=1\{A=U\}$; visible validation always stops the episode at this second decision, even when hidden-test success is zero. Thus every donor contains both decisions, and the logging probabilities support the target.

The adaptive target chooses $A=U$, so its true success probability is one. Represent $U=0$ by the failure class `exception` and $U=1$ by `assertion`; the target is then the class-dependent rule used by the code-study comparator. Suppose an unlimited ordered bank contains independent donors from this same task and execution law. No later-prefix fallback is needed: either second action has a matching donor almost surely.

Rule B first picks the earliest donor, reads its $U$, and requests action $U$. If this donor's logged $A$ already equals $U$, it keeps the donor and returns success one. This event has probability $1/2$. Otherwise it picks the earliest later donor with action equal to the **old** $U$. The selected donor's own state $U'$ is an independent fair bit: selection uses its action, which is independent of its state. Its stored success is $1\{U'=U\}$, of mean $1/2$. Therefore

$$
E(\widehat Y_{\mathrm{stitch}})
=\tfrac12\cdot1+\tfrac12\cdot\tfrac12
=\tfrac34,
\qquad V(\pi)=1.
$$

The replacement discards the state that determined the target's action. The discrepancy is present at a horizon of two, with correct randomization, stable kernels, independent donors and unlimited action-prefix availability. A longer horizon or a missing donor is not necessary. This construction does not assert that the actual finite benchmark has bias $-1/4$; it isolates a possible failure mechanism.

For contrast, in this same system a constant target action $c$ has value $P(U=c)=1/2$. Rule B simply uses the first donor with $A=c$, whose state remains a fair bit, so its mean is also $1/2$. This is a deliberately narrow positive control. It demonstrates why an invalidity label should attach to a specified transformation and assumptions, rather than to every procedure called replay. It is not a validity theorem for adaptive policies, arbitrary logging propensities, finite-bank fallback or general state substitution.

## Exact checks and implications for the new analysis

[`tests/test_replay_boundaries.py`](../tests/test_replay_boundaries.py) checks the original frozen-state example and exhaustively enumerates the three fair bits $(U,A,U')$ in the donor construction. The expected success is exactly $3/4$ for the adaptive replay rule and $1/2$ for either constant-action positive control, compared with the corresponding true values one and $1/2$. Rational arithmetic is used; no Monte Carlo or model call is involved. The $U'$ representation is justified by the independent-action donor selection above, not assumed for an arbitrary donor-selection algorithm.

The new real-record comparison should be labeled post-hoc and descriptive. Distinguish the finite-bank fallback rule, state-dependent targets and thresholded stochastic targets; measure actual donor changes and misses. Discrepancies from finite live estimates are not repeated-sampling bias, and an observed ordering of mean absolute discrepancies does not establish a statistical null, equal accuracy, or superiority. The planned validation should check each specified control against finite known truth without requiring a predetermined result on the real benchmark.
