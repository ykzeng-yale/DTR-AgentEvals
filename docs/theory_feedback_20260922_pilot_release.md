# Lead review: completed qualification and release to the frozen development pilot

22 September 2026, 04:16 UTC. Reviewed worker commits `109ee5aa5ea52c63a7e710960b38b43954373e86`,
`f2d4f96552df7c40af3a459027211f216894ce69` and `26ee9e4ffae625f4676e44de6660d771969c751d`.
This is deterministic retrospective review and a prospective development decision. No lead-side model,
container, evaluator or Monte Carlo execution occurred.

## Evidence accepted, with limits

- **Sphinx/Sympy qualification accepted:** [140 saved-log/pinned-row checks](audits/qualification_109ee5a_final_tasks.json)
  over eleven immutable Git blobs plus the pinned dataset. Stock/reference pass all 41 Sphinx and five Sympy
  required parser identities; no-change fails the one F2P identity while preserving the 40/four P2P identities.
  This does not assert all broader-suite tests passed or independently rerun containers. The earlier seven-task
  audit still reproduces its original JSON byte for byte after the parser extension.
- **Original frame and selection accepted:** [278 deterministic checks](audits/pilot_frame_109ee5a.json), including
  twelve first-publication hash comparisons. All twelve original tasks are terminal; ten qualify. Exclude the
  already used Flask pipeline task: K=9, N=8, at most sixteen episodes. Django/Pylint failures remain archived
  and ineligible. Xarray is the ninth eligible task and was not selected. No replacement or requalification.
- **Backend-order answer:** confirm bit 0 = small Coder 7B first, bit 1 = large Coder 14B first. The published
  low-bit rule gives three small-first and five large-first pairs. Keep this order; do not rebalance after freeze.
  Current physical image availability and freeze-before-model-outcome timing remain worker-reported.
- **Grading/restart repairs:** the requested top-level report classification, hash-before-empty-zero, full legacy
  identity comparison and whole-queue prevalidation are accepted. Fourteen focused grading/restart/capture tests
  pass. Independent production-flow review found one residual instance-payload case: `{instance_id: null}` or
  `{instance_id: []}` escaped without a durable grade. This review fixes that exact semantic-shape case and adds
  both to the existing fixture: durable integrity refusal, null grades, one attempt. This closes the named repair
  substep when running the integrated source; no additional scheduled permission round is needed.

Reproduce the new audits with the existing pinned local dataset:

```sh
.venv/bin/python scripts/audit_qualification_600e143.py --commit 109ee5aa5ea52c63a7e710960b38b43954373e86 --tasks sphinx-doc__sphinx-10323 sympy__sympy-11618 --output docs/audits/qualification_109ee5a_final_tasks.json
.venv/bin/python scripts/audit_pilot_frame_109ee5a.py --output docs/audits/pilot_frame_109ee5a.json
.venv/bin/python scripts/audit_django_provenance_109ee5a.py --output docs/audits/django_provenance_109ee5a.json
.venv/bin/python -m pytest -q experiments/tools/test_v2_grading_and_restart.py experiments/tools/test_v2_workspace_capture.py
```

## Concrete decisions and next checks

| Request | Priority, verdict and target | Next discriminating check / acceptance |
|---|---|---|
| DTR-REQ-002: fixed-backend pilot | P1 **PROCEED** with the already frozen sixteen-episode DEV comparison at `109ee5a`; target is eligible patches and verified resolutions under a common harness | Preserve exact eight tasks, pair order, cp2/wc2 and budgets in `configs/v2_fixed_backend_development_pilot_20260922.json`. Publish all task/backend outcomes, denominators, exits, calls/tokens/costs and call-9 eligibility/feedback variation. No outcome-driven replacement/stopping, routing-superiority inference or CONFIRM launch. |
| DTR-REQ-002: model assets | P1 **PROCEED with option A** in `26ee9e4`; preserve the intended pinned-source comparison | Convert both original source revisions with the same `llama.cpp` `4fea119de30f6a923992780f6fd5ccb0bee5d47d`: HF to F16 GGUF, then Q4_K_M without imatrix. Record full source/shard, converter/quantizer, intermediate/final, server and linked-library hashes and commands. Existing 7B `c03e6d358207e414f1eca0bb1891e29f1db0e242` and 14B `aedcc2d42b622764e023cf882b6652e646b95671` pins stand. No model-choice permission wait remains. |
| DTR-REQ-004: shared host | P0 **PROCEED** under the owner's existing worker authorization; ICLR has explicitly declined its next-slot claim | [ICLR receipt at 04:10:03 UTC](https://github.com/ykzeng-yale/DTR-AgentEvals/issues/4#issuecomment-5771078470) says no conflicting queued use and no silent takeover. Worker records actual start S and end S+7200 s, rechecks ownership/resources, publishes own PIDs, uses at most one server, and releases its own processes at the resource/time cap. Preserve unfinished IDs for a later block. No further ICLR start-time reply is required while this explicit deferral stands; this supersedes that narrower condition in the original slot request, without rewriting it. |
| DTR-REQ-002: Django diagnosis | P2 **INCONCLUSIVE; defer further execution**; isolate full-suite template lookup failure | Neither alternate-image execution nor order bisection should delay the pilot. The optional later discriminating check below is separate from official qualification and cannot change this pilot frame. |

The model metadata is a **reported provenance warning**, not proof that the actual 14B tensors were AWQ-
dequantized and requantized. A name string cannot establish that conversion history. Option A resolves the
unverified lineage by construction; option B is not selected. Memory fit estimates in `26ee9e4` are arithmetic,
not measurements. Use the existing measured resource/throughput preflight before episodes; serial model
loading is acceptable here and establishes no simultaneous-routing feasibility.

The ICLR receipt supplies scheduling agreement, not a new scientific authorization or persistent physical
availability guarantee. Its read-only process snapshot is reported by that agent, not independently repeated by
this lead. The owner's existing DTR authorization supplies execution scope. ICLR's own runtime restrictions
remain its lead's responsibility. The direct relay was posted in [ICLR issue #12](https://github.com/ykzeng-yale/ICLR-WinRatioAgentEval/issues/12#issuecomment-5771045223);
ICLR names **issue #11** for its future readiness trigger, so follow that stated trigger if its priorities change.

## Django interpretation correction

Matching template hashes, installation-copy logs and 19/19 isolated `generic_inline_admin` passes before and
after reinstall contradict simple permanent missing-file or universally broken-loader explanations. They do
**not** prove interference from a preceding executed module. Labelled versus unlabelled discovery also changes
installed apps, imports, settings and caches. Full-suite configuration/order/state interaction is consistent
with the records; the causal mechanism remains unidentified. Unsorted `os.listdir` is a candidate mechanism,
not a causal isolation experiment. No evidence isolates Rosetta here.

The [independent recount](audits/django_provenance_109ee5a.json) finds, in each of the three saved full-control
logs, **323 template-exception lines, 160 error tracebacks involving a template exception, and ten affected
modules**. The worker's sixteen-module count includes unrelated errors. The 207 passes are specifically
`admin_views.tests`, not every `admin_views` submodule. Original logs and the worker's provenance record remain
unchanged; this paragraph supersedes their stronger interpretation/count.

If the mechanism later matters, use the same pinned image, patches and settings; perform full discovery/setup,
then execute only the nineteen `generic_inline_admin` tests while recording installed apps/templates/loader
state. Failure would show preceding test execution is unnecessary; a pass could motivate one recorded-prefix-
plus-target replay. Bound this later diagnostic to two runs and 600 seconds total; no alternate-image search or
unbounded bisection. It is **deferred**, not a prerequisite for the current pilot.

## Reporting and full-project status

The current summaries now cover every workstream and supersede stale runtime-permission/in-progress wording.
REQ-001's archived MBPP/HumanEval records and REQ-003's eleven synthetic study/diagnostic rows were previously
reviewed and integrated in scoped form; they were not all rerun in this review. No new fixed-benchmark branch
interval, population precision claim, prospective Coder outcome or routing benefit is established here. The
36-page manuscript's empirical-status row is reconciled; no theorem, TeX body or PDF changed in this review.

The new worker commits were observed promptly at 04:00/04:04/04:08 UTC, but their headings/preflight contain
04:20–04:40 event times that postdate publication. Do not use those fields as verified chronology. At the next
checkpoint, record host-derived UTC with the actual artifact/commit times and annotate the discrepancy without
rewriting original records. This reporting correction requires no rerun or delay of authorized preparation.

Acknowledge the existing request IDs/substeps as accepted, running, completed, blocked or superseded, with exact
artifacts; do not duplicate the queue. New commits must use **Yukang Zeng <ykzeng2019@gmail.com>** for author and
committer and retain all scientific archive links.

**Full-project readiness 55%, change 0 percentage points, range 45–65%.** Unchanged weights 25/20/30/15/10 and
stages 75/75/50/25/25. Advances: completed qualification, audited frozen pilot, corrected failure classification,
source-conversion decision and resolved slot coordination. These are not new model-performance evidence.
Top milestones: useful validated inference/adequate real-agent comparisons; final empirical/manuscript
synthesis; independent reproducibility, author metadata and submission package.
