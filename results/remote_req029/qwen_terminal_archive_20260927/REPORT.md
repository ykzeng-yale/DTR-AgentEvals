# REQ-029L Qwen terminal worker archive

Run `cmp029e-django16560-qwen-a`; archival receipt timestamp 2026-09-27T19:43:00.812416Z. This is preservation of the completed attempt, not a retry, evaluator run, or scientific acceptance decision.

`worker-runtime.tar.gz` preserves the full worker runtime plus launch stdout/stderr: 2,126 regular-file members, 3,739,824 uncompressed bytes; compressed 821,321 bytes. SHA256 `bd55ccfd5ab39ab56220f056ca6199f43eb2910ed98e1eee131924b4ec040dca`. `members.json` maps every repository-relative archive member to its size and SHA256. Every archived member was read back and its hash checked. No symlinks were encountered; credential-pattern scan found no matches.

All three raw generation responses, three native bindings, HTTP inputs/outputs, admission and guard samples, traces, model ownership/cleanup and terminal records are preserved without rewriting. Only two accepted response records exist: the third raw response failed the exactly-one-nonempty-upstream-action parser. Terminal records show three physical dispatches, no call9, and no eligible submission. Lead reports two controller actions; the controller runtime is not part of this worker archive.

Recorded per-call prompt/completion tokens: 864/84, 1040/82, 1241/385. HTTP durations: 4.96957802772522, 5.891906261444092, 15.135706901550293 seconds. Full setup/admission/phase and cleanup timestamps remain in the archive and receipt; no invented cost units.

A single actual `ps -p 29568,29919,30090 -o pid=,lstart=,command=` observation at the start of this archival task returned no process rows: worker 29568, supervisor 29919 and model 30090 were absent. No subsequent process polling occurred. The terminal cleanup record separately reports model owned_absent=true and direct_child_reaped=true, with supervisor reason `Rejected('owner_parent_exited')`; preserve that exact reason, not an inferred replacement.

No experiment source edits, new model launches, retries, Klear or evaluator execution. Interpretation and the next exact release remain lead-owned. Monitoring cadence was not changed.

Readiness 55%, change 0 points, range 45–65%; competent comparison/inference, synthesis, independent reproducibility/author-approved package remain.
