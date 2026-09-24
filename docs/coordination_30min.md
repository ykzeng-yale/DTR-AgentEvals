# Experiment and theory coordination

**Current author instruction, 24 September 2026 UTC:** the experiment agent may continue its separately authorized half-hour publication cadence. The theory lead's recurring check is now every **three hours at minute 18**. The worker reported slots at minutes 13 and 43 in `1c9025d`, leaving a nominal five-minute lag after the minute-13 slot; the worker's scheduler is reported, not independently inspected on its host. Actual publication freshness will be checked. Material scientific corrections should be published when found, without waiting for the next scheduled check.

## Shared channel and ownership

Use [issue #4](https://github.com/ykzeng-yale/DTR-AgentEvals/issues/4), [experiment handoff](experiment_handoff.md) and [worker progress](../experiments/PROGRESS.md). If the worker cannot access issues, committed handoff/progress files are the authoritative exchange, and the lead relays their contents to #4. Read new commits and the latest request acknowledgements before doing work. Preserve concurrent changes and publish directly to main; no PRs, force pushes or rewritten archives. Author and committer: Yukang Zeng <ykzeng2019@gmail.com>.

The experiment worker executes and reports its authorized work. The lead owns target, design, metric, comparator, inference and interpretation decisions. The lead may now run bounded local development diagnostics when validated code, available disk/compute, isolation, a resource cap and non-overlap with worker jobs are established; prefer deterministic CPU checks. This is not authorization for duplicate jobs, paid services, outcome-driven CONFIRM tuning or a held live/CONFIRM stage. Existing scientific gates still apply: the v2 design is not frozen for confirmation until its specified task, resource, precision and analysis choices are recorded.

## Worker checkpoint every 30 minutes

Publish completed, immutable result batches as available; a long job need not finish before a progress update. Include:

- UTC timestamp, exact code/config commit, run/batch ID, stage (development or CONFIRM), immutable artifact paths and current counts, failures and measured resource use.
- New completed results with denominators and uncertainty status; distinguish observed, provisional and independently validated findings. Preserve adverse outcomes.
- Current question or unexpected result, with the smallest records needed to diagnose it. State the declared estimand, comparator, metric and relevant support/decision-opportunity counts.
- Last lead checkpoint read and request IDs: accepted, running, completed, blocked or superseded, each with an artifact or reason. Report existing work that satisfies a request rather than rerunning it.

For ongoing CONFIRM collection, publish counts, execution health and protocol deviations. Do not expose interim outcomes for policy/metric tuning or change stopping based on them; any inferential interim analysis must already be part of the frozen protocol. Completed CONFIRM outcomes remain immutable and may motivate a separately labeled development study.

## Lead response every three hours

Review new batches and unanswered questions first. Give a reasoned verdict: **proceed**, **repair**, **hold a new stage**, or **inconclusive**. Specify which evidence supports it and which assumption remains unverified. A hold applies to the named next stage, not a blanket interruption of separately authorized jobs. Inspect unfavorable and unexpectedly favorable findings for target mismatch, weak feedback/power, unsuitable comparators/metrics, restricted learners, implementation/inference defects and theory limitations.

For each actionable request provide a stable ID, priority, hypothesis/target, source commit, discriminating next check and acceptance criterion. Carry unchanged IDs forward instead of duplicating the backlog. Publish a material correction during the current review rather than waiting for another cycle. If there is no new evidence, post a short unchanged checkpoint and make one bounded, verifiable contribution where feasible: a theory/manuscript correction, independent evidence audit or eligible local development diagnostic. Do not invent progress. A scheduling interval is not a guarantee of an exact completion time.

## Existing requests, now assigned stable IDs

These refer to the [v2 protocol, section 6](experiment_protocol_v2.md#6-immediate-worker-deliverables-without-new-execution) and [lead review at 112dc06](https://github.com/ykzeng-yale/DTR-AgentEvals/commit/112dc06bea498ee62691350d0e6412260d867bf6). They are reporting/design work that can accompany the worker's separately authorized experiments, not a new global compute prohibition.

| ID | Priority and request | Acceptance |
|---|---|---|
| DTR-REQ-001 | P0: source-bound A6 correction and source-block/fresh-pair/recovery evidence | Match pinned lead audits; retain original cohorts/metrics; label unknown execution assumptions; no primary-target substitution or unsupported coverage/power claims |
| DTR-REQ-002 | P1: pinned mini-swe-agent/SWE-bench and local RouteLLM adapter contract | Exact routing hooks, pre-action fields, retries, affordability, submissions/evaluator failures, evaluation IDs and dependency/license records; distinguish planned from implemented/tested |
| DTR-REQ-003 | P1: finite simulation tables, policies, truth and block design | Positive/negative analytic controls, independently checkable truth paths, target invariant to logger-only changes and complete fixed-task repetitions; state unresolved inference conditions |

The reply at `1c9025d` reports no active runner, a half-hour schedule and adoption of the three design deliverables. The next reply should acknowledge the stable IDs and include current authorized runs and next checkpoint with a host-derived UTC timestamp; its current progress heading has an inconsistent date/time. No scheduler or live process state is independently verified from a committed statement alone. New result-specific questions may take priority over this queue by an explicit lead decision.

Every completed checkpoint reports full-project readiness using [the unchanged rubric](readiness.md). Current estimate **55%, change 0 percentage points, judgment range 45–65%**. Faster reporting adds no scientific evidence by itself. Remaining milestones: useful validated inference/adequate comparisons; remaining statistical validation and final empirical synthesis; independent reproducibility, author metadata and submission packaging.
