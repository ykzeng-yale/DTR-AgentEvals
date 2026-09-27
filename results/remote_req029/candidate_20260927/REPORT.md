# REQ-029A ordinary command feedback correction

Status: **DONE for the scoped source-only candidate and inert tests; live integration remains held.**
Source commit: `8e6e9a599dfeafbe04a93acfdd8c1c8a3cb59759`.
Only four new files under `experiments/remote_req029` and immutable results under `results/remote_req029` were added. REQ-028 sources, approvals, archives and outcomes are unchanged.

## Diagnosis and change

The investigate workflow reproduced the archived validator's `Rejected('command failure')` for an ordinary completed exit-1 command before implementation. Source inspection found the same restriction at the C6 sandbox guardian, controller and worker validator. The executed historical full-chain regression also confirms that the archived guardian terminates before publishing this feedback. This is a harness semantics defect, not a model or test failure, and was not the cause of C6B's all-zero-returncode outcome.

`feedback.py` supplies a narrowly defined completed-output validator: exact three-field schema, integer shell status 0–255 (not bool or negative signal status), output within 1 MiB, and `exception_info is None`. An ordinary nonzero status carries no inferred test-failure, submission or verified-success label. Exceptions, timeout, overflow, broken supervision, ownership/resource failures, transport errors and expired deadlines remain terminal. No exception is caught and converted into an ordinary returncode.

The candidate guardian changes only completed-action feedback and versioned phase binding. Ownership checks, independent guardian loop, durable guardian claims, output bounds and cleanup are inherited from frozen C6. Completed nonzero output is returned after a post-operation liveness/deadline check. A foreign identity is never removed; cleanup is explicitly unconfirmed in that fixture.

`engine.py` is a separately versioned copy of the frozen finite C6 engine. It uses protocol 29 and a `req029a-` namespace, the candidate chain/observation functions and completed-output validator. It retains the action claim/fsync before dispatch, finite calls/actions, deadlines, exact parent chain, terminal behavior and cleanup. The worker additionally checks the accepted observation object's full envelope SHA before appending history. No historical implementation is monkey-patched.

The envelope binds the complete raw output/status tuple through `output_sha256`, the exact response object and response SHA, sequence, source, release and run. The delivered observation still uses the unchanged hash-pinned upstream template, including declared long-output elision. Raw and delivered output remain separate. Next full history retains previous messages, exact accepted assistant response and the bound observation. Subsequent requests bind that history and prior response/observation hashes.

Submission uses the unchanged pinned upstream successful-command rule directly: the explicit first-line sentinel only submits with returncode 0. A nonzero command printing the sentinel instead becomes feedback. No limit, exception or diagnostic diff is salvaged into a submission.

## Executed verification

Final result:

```text
Ran 14 tests in 4.611s
OK
```

Executed coverage:

- Exit 1 reaches the next **full** scripted message history and passes worker validation; zero-exit template behavior is unchanged.
- Nonzero sentinel output cannot submit; a later explicit zero-exit sentinel can.
- Injected timeout, overflow, exception, broken-supervision and resource failures remain terminal with fake-owned cleanup and no second scripted reply.
- Ownership failure is terminal and never removes the substituted foreign identity; cleanup is reported unconfirmed.
- Returncode tampering fails accepted-object hash validation; output tampering fails envelope binding even if the outer object hash is recomputed. Sequence, parent-response hash, output hash and release substitutions are rejected.
- Crash after durable action claim executes no action; role reconstruction at the same root is rejected. Relay publication failure does not redispatch the completed action and terminates both roles with cleanup.
- Invalid status types, negative signal status, exception metadata, oversize output and expired deadlines fail closed.
- Long feedback preserves exact raw output/hash and the pinned delivered-output elision.
- Archived C6 validator and archived full-chain behavior reject the same ordinary exit-1 feedback. Those files were not edited.

The fake transport, thread-driven guardian and Docker-shaped backend are explicit test-only injections. Scripted reply data uses no model, serving process or tokenizer. Commands are string data and are never executed by the fake sandbox. Timeout/overflow/resource faults are **injected exceptions**, not new real Docker timeout/resource qualification. The inherited real lifecycle's prior evidence remains separate; these fixtures do not requalify a production backend.

## Preserved preparation history and limits

| Run | Result | Wrapper seconds |
| --- | --- | ---: |
| Archived validator reproduction | Expected exit-1 rejection | 0.001087 |
| Initial new fixture suite | 11 methods; 11 failure assertions including subtests, 1 error | 1.547267 |
| Corrected fake ready-object path | 12/12 pass | 4.677860 |
| Final source, relay-failure and long-output tests | **14/14 pass** | 4.670208 |

The first new fixture used an invalid ready-object path and correctly failed before action dispatch. It was corrected to the exact run-relative path; the failed receipts/logs are retained. No passing outcome replaces that failure. There are 14 unique final methods, not 37 unique tests; the three suites contain 37 method executions plus nested fault cases. Every suite has unchanged before/after source fingerprints.

Recorded cumulative test/reproduction execution: **10.896422 seconds**, under 300 seconds. Peak sampled descendant RSS: **31,621,120 bytes**, under 2 GiB. One serial unittest driver and one math-library thread were configured; the deterministic pair uses worker/guardian threads. macOS CPU affinity is not enforced and sampled RSS is not a hard limit. Retained artifacts before this report: **4,659,493 bytes**, under 100 MiB.

No real model invocation/load, generated shell action, actual Docker, evaluator, download, live Git relay/poller, peer change or same-task retry occurred. Git synchronization/publication is not a live experimental relay. No routing assignment, competence claim or scientific comparison follows from these fixtures.

## Dependencies, commands and activation boundary

Runtime tested with Python 3.9.6 and Jinja2 3.1.6. Candidate code imports the frozen C6 chain/template/native binding, submission checker and guardian, plus their pinned transitive REQ-028 dependencies. The package fingerprints all REQ-028 Python/JSON source, upstream mini source/license, original prompt/native/template inputs, current design documents and four candidate files. The inherited C6 prompt appears only in fixed inert histories, not a new model request. No package was installed.

Executed candidate command:

```text
python3 experiments/remote_req029/test_suite.py results/remote_req029/feedback_final_20260927
```

The output directory is now immutable. A separately authorized reproduction must choose a new directory. For a focused inert test, from `experiments/remote_req029`, the candidate command is `python3 -m unittest -v tests.Tests.test_exit1_reaches_next_full_history_and_worker`.

The reusable interfaces are `engine.Controller`, `engine.Worker`, `feedback.Chain`, `feedback.Guardian`, `observation_envelope` and `check_observation`. This assignment does **not** supply a production launcher or manufacture a new model/sandbox/relay approval. Existing C6 launchers/approvals do not authorize protocol 29. A future source-qualified harness must explicitly wire these candidates under a new lead-approved design and executable release; model choice, routing, opportunities and evaluator qualification remain lead decisions.

## Immutable evidence

The archive contains **1,860 members**, all verified against the full member mapping: original reproduction, failed initial suite, corrected/final suites, raw fixture histories/claims/outputs/cleanup, and final source/dependency snapshot. There are **154 source/input pins**.

- Archive `inert_evidence.tar.gz`, 645,163 bytes, SHA-256 `32e4e3289e2aeaf9a30bb1b7cda1a156fae0a663588a06b988596b988460da0c`.
- Member mapping SHA-256 `fef53080d5d1bbd7c232c06418c60a3ec5ff2b7db9013465f25756f103123c04`.
- Source mapping SHA-256 `d894714a4e8d2bb32457443f59f67f09d4960a8818ac75ca72db8ebee3966ade`.

STOP after publication for lead review. Readiness **55%, Δ0, range 45–65%**. Remaining: competent fixed-target comparison/valid inference, empirical/manuscript synthesis, independent reproducibility and author-approved package.
