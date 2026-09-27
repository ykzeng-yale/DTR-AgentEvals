# REQ029N — retrospective scaffold control-flow diagnosis

The lead's comparator design omitted the format-error recovery loop of the cited mini-swe-agent scaffold. Matching its action regex was insufficient to reproduce its agent. This is a scientific design limitation, not a violation by the implementer of the frozen first-error-terminal release. Qwen's archived Django failure remains a failure under that released configuration; it does not establish failure of the full upstream agent or general model incapacity. Klear remains unattempted because admission failed. No outcome is rescored.

## Pinned evidence and executed check

Upstream revision `04d809ceab9df28f9adaed044884180159172930`, six source/license files and SHA256 manifest: `docs/source_snapshots/req029n_format_flow`. Upstream `DefaultAgent.run` feeds back format errors, exits at three consecutive errors by default, and resets the count on a clean step. `query` increments calls before model dispatch. `LitellmModel.query` attaches billed cost and raw response to the error message. `parse_regex_actions` supplies a user feedback message; invalid assistant content lives in its extra metadata. The provider preparation strips extra metadata before the next request. Thus merely inserting the invalid assistant text into the next prompt would also differ from this pinned implementation.

Run `.venv/bin/python experiments/lead_req029/format_flow_audit.py`.
Four deterministic cases execute the actual pinned agent run/step/query/action methods and parser AST with inert model/environment adapters: error then clean step; three consecutive errors; clean-step reset; and call-limit exhaustion after one error. All passed. Ambiguous commands never reach the inert environment, errors consume calls and fixture cost units, and exact feedback text is retained. Results: `results/local_req029/format_flow_audit_20260927/result.json`.

Scope: this is not provider execution, model inference, Docker execution, or competence evidence. Model cost/raw-response attachment is mirrored from inspected source, rather than executing the complete LiteLLM dependency stack. Upstream provider retry behavior is not adopted or tested. No dollar or latency claim follows from fixture cost units.

## Competing explanations and decision

The observed two-fence response is genuine model behavior. A recovery opportunity could correct it or could produce another failure; neither outcome is observed. Resource admission separately prevented Klear execution. Prior Astropy candidate grading showed a substantive incorrect patch and regression, so interface recovery alone cannot be assumed to establish competence. These facts argue against treating this design correction as a positive model result.

Before new inference, specify a prospective agent contract with budgeted format feedback, durable distinct call sequence/claims, exact raw-response persistence, three-consecutive-error termination, and no ambiguous command execution. Keep transport retries prohibited and count every physical generation against the same budget. Pin the difference between upstream metadata-only invalid responses and any deliberate full-history alternative. Validate the model adapter's actual error path, not only this retrospective AST fixture. Use fresh development tasks under a frozen selection rule; do not resume or retry the exposed Django/Astropy runs, tune on held CONFIRM, or revise primary targets. This document grants no model execution or deployment release.

Preprint readiness: **55%, change 0 points, range 45–65%**. Remaining: competent fixed-target comparisons and valid inference, empirical/manuscript synthesis, independent reproducibility and author-approved package.
