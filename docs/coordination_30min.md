# Thirty-minute experiment and theory coordination

**Author instruction, 21 September 2026 UTC:** the experiment agent has been asked to accelerate its authorized work, publish results/progress every half hour and retrieve new scientific feedback. The theory lead's existing recurring job is now active every 30 minutes, at minute 18 and 48. The worker reported its job at minute 13 and 43 in `1c9025d`, leaving a five-minute publication lag before review. The worker's scheduler is reported, not independently inspected on its host; actual publication freshness will be checked.

## Shared channel and ownership

Use [issue #4](https://github.com/ykzeng-yale/DTR-AgentEvals/issues/4), [experiment handoff](experiment_handoff.md) and [worker progress](../experiments/PROGRESS.md). If the worker cannot access issues, committed handoff/progress files are the authoritative exchange, and the lead relays their contents to #4. Read new commits and the latest request acknowledgements before doing work. Preserve concurrent changes and publish directly to main; no PRs, force pushes or rewritten archives. Author and committer: Yukang Zeng <ykzeng2019@gmail.com>.

The experiment worker executes and reports its authorized work. The lead owns target, design, metric, comparator, inference and interpretation decisions. The theory task's compute deferral must not block the separately authorized experiment workstream or trigger duplicate jobs. Existing scientific gates still apply: the v2 design is not frozen for confirmation until its specified task, resource, precision and analysis choices are recorded. Do not purchase compute or change budgets implicitly.

## Worker checkpoint every 30 minutes

Publish completed, immutable result batches as available; a long job need not finish before a progress update. Include:

- UTC timestamp, exact code/config commit, run/batch ID, stage (development or CONFIRM), immutable artifact paths and current counts, failures and measured resource use.
- New completed results with denominators and uncertainty status; distinguish observed, provisional and independently validated findings. Preserve adverse outcomes.
- Current question or unexpected result, with the smallest records needed to diagnose it. State the declared estimand, comparator, metric and relevant support/decision-opportunity counts.
- Last lead checkpoint read and request IDs: accepted, running, completed, blocked or superseded, each with an artifact or reason. Report existing work that satisfies a request rather than rerunning it.

For ongoing CONFIRM collection, publish counts, execution health and protocol deviations. Do not expose interim outcomes for policy/metric tuning or change stopping based on them; any inferential interim analysis must already be part of the frozen protocol. Completed CONFIRM outcomes remain immutable and may motivate a separately labeled development study.

## Lead response every 30 minutes

Review new batches and unanswered questions first. Give a reasoned verdict: **proceed**, **repair**, **hold a new stage**, or **inconclusive**. Specify which evidence supports it and which assumption remains unverified. A hold applies to the named next stage, not a blanket interruption of separately authorized jobs. Inspect unfavorable and unexpectedly favorable findings for target mismatch, weak feedback/power, unsuitable comparators/metrics, restricted learners, implementation/inference defects and theory limitations.

For each actionable request provide a stable ID, priority, hypothesis/target, source commit, discriminating next check and acceptance criterion. Carry unchanged IDs forward instead of duplicating the backlog. Publish a material correction during the current review rather than waiting for another cycle. If there is no new evidence, post a short unchanged checkpoint; continue useful bounded theory/manuscript work. A scheduling interval is not a guarantee of an exact completion time.

## Existing requests, now assigned stable IDs

These refer to the [v2 protocol, section 6](experiment_protocol_v2.md#6-immediate-worker-deliverables-without-new-execution) and [lead review at 112dc06](https://github.com/ykzeng-yale/DTR-AgentEvals/commit/112dc06bea498ee62691350d0e6412260d867bf6). They are reporting/design work that can accompany the worker's separately authorized experiments, not a new global compute prohibition.

| ID | Priority and request | Acceptance |
|---|---|---|
| DTR-REQ-001 | P0: source-bound A6 correction and source-block/fresh-pair/recovery evidence | Match pinned lead audits; retain original cohorts/metrics; label unknown execution assumptions; no primary-target substitution or unsupported coverage/power claims |
| DTR-REQ-002 | P1: pinned mini-swe-agent/SWE-bench and local RouteLLM adapter contract | Exact routing hooks, pre-action fields, retries, affordability, submissions/evaluator failures, evaluation IDs and dependency/license records; distinguish planned from implemented/tested |
| DTR-REQ-003 | P1: finite simulation tables, policies, truth and block design | Positive/negative analytic controls, independently checkable truth paths, target invariant to logger-only changes and complete fixed-task repetitions; state unresolved inference conditions |

The reply at `1c9025d` reports no active runner, a half-hour schedule and adoption of the three design deliverables. The next reply should acknowledge the stable IDs and include current authorized runs and next checkpoint with a host-derived UTC timestamp; its current progress heading has an inconsistent date/time. No scheduler or live process state is independently verified from a committed statement alone. New result-specific questions may take priority over this queue by an explicit lead decision.

Every completed checkpoint reports full-project readiness using [the unchanged rubric](readiness.md). Current estimate **55%, change 0 percentage points, judgment range 45–65%**. Faster reporting adds no scientific evidence by itself. Remaining milestones: useful validated inference/adequate comparisons; remaining statistical validation and final empirical synthesis; independent reproducibility, author metadata and submission packaging.
