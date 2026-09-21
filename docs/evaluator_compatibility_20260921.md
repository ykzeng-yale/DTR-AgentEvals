# Evaluator compatibility candidate (DTR-REQ-002 repair)

**Lead update, 04:48 UTC:** candidate f7bbbb2 is selected for development qualification in the
[decision](theory_feedback_20260921_evaluator_selection.md); #492/#489 have now been checked as documentation-only.
The original proposal below is retained. Existing source pins are unchanged; no runtime acceptance follows.

**Status, 21 September 2026 (worker): a proposal, pending lead review.** No pin has been changed. Nothing is installed or executed. The lead's [decision](theory_feedback_20260921_adapter.md) was option (b): keep `princeton-nlp/SWE-bench_Verified@c104f84` and audit a compatible upstream evaluator. All line references below were read from raw source at the named commits. Commit ancestry comes from the GitHub compare API.

## Candidate

**`SWE-bench/SWE-bench@f7bbbb2ccdf479001d6467c9e34af59e44a840f9`** (2026-03-19). This is the pre-v5 maintenance line: tag `v4.1.0` (`726c546`) plus 11 commits.

| Ancestry fact (compare API) | Result |
|---|---|
| Schema change `31a85bf` ("embed eval_script/metadata in datasets", 2026-02-16) contained in candidate? | **No.** Candidate and `31a85bf` have diverged (40 and 20 commits). |
| Git-log leakage fix `c7a956c` ("Fix git log leakage in environment images (#471)") contained? | **Yes.** `v4.1.0` is `c7a956c` plus one version-bump commit. |
| Test-patch checkout fix (#518/#539) contained? | **Yes.** It is the candidate commit itself. |
| Other 10 commits after `v4.1.0` | Seven docs/blog changes, plus #492, #489, a multilingual image rebuild fix (#507) and a flaky Java eval fix (#506). **#492 and #489 are not yet audited.** |

The tagged alternative is `v4.1.0`, which the candidate contains. It lacks the #518 checkout fix. The lead chooses between the two. I have not verified that no later commit exists on this maintenance line; the candidate is the latest one visible in the pinned `02e7a74` history.

## Compatibility delta (pinned `02e7a74` → candidate `f7bbbb2`)

| Aspect | Pinned `02e7a74` | Candidate `f7bbbb2` |
|---|---|---|
| **Required instance fields** | `image`, `eval_script`, `log_parser`, `eval_type`, plus repo, version, FAIL_TO_PASS, PASS_TO_PASS (`utils.py` L255–270). Absent from the original schema. | `instance_id`, `repo`, `version`, `base_commit`, `test_patch` (`test_spec.py` L187–193); `environment_setup_commit` (`python.py` L128). `problem_statement` and `hints_text` are read with `.get` and unused for evaluation. `FAIL_TO_PASS`/`PASS_TO_PASS` go through `_from_json_or_obj`. **All present in the original 13-field schema.** |
| **Test-spec construction** | Parses the dataset's `eval_script`. | `MAP_REPO_VERSION_TO_SPECS[repo][version]` (L209) plus `make_repo/env/eval_script_list`. A missing (repo, version) pair raises `KeyError`, so fixture M01 must cover all 500 instances. |
| **Silent-default hazard** | none observed | `_from_json_or_obj` returns `[]` when FAIL_TO_PASS or PASS_TO_PASS is absent (L195–202, "validation instance"). Combined with the empty-set rule below, that would **grade vacuously**. The adapter must assert both keys are present and FAIL_TO_PASS is non-empty (fixture M02). |
| **Resolution rule** | FULL iff `f2p == 1 and p2p == 1`; empty set scores 1 | Same: `grading.py` L227 and L199–200/L209–211 |
| **Log parsing** | Dataset `log_parser` field | Repo-mapped parsers in code. **Differences not audited** (fixture M03 compares on recorded logs). |
| **Image resolution** | Dataset `image`, pulled if missing | Key `sweb.eval.{arch}.{instance_id}:{instance_image_tag}`. Namespace defaults to `"swebench"` (L654), which pulls mutable `latest` tags. Namespace `none` builds base/env/instance images locally. `arch` is `x86_64` or `arm64` (platform `linux/arm64/v8`). Neither version pins digests; the adapter must resolve and record them. An arm64 local build path exists in code; **whether Verified environments build or pass on arm64 is untested.** |
| **Timeout** | Default 1,800 s → `EvaluationError` | Same default (L626) and behaviour. Still unfrozen per the lead. |
| **Report cache** | `run_id/model/instance/report.json`, returned if present | Same (L97, L118); evaluation identity rules unchanged. Adds image cache options `--cache_level` (default `env`), `--clean` and `--force_rebuild`. |
| **Packaging** | MIT; Python ≥3.10; core deps include `huggingface_hub>=1.20`, `ghapi<2`, PyYAML, typer | MIT (`license = {file = "LICENSE"}`); Python ≥3.10. Core deps: beautifulsoup4, chardet, datasets, docker, ghapi, GitPython, modal, pre-commit, python-dotenv, requests, rich, tenacity, tqdm, unidiff. Optional groups add inference packages. No lock produced. |

## Acceptance items still open

These follow the lead's acceptance list.
- **Covered in source:** field accounting on the original schema, and unchanged task/test identities (no field is rewritten).
- **Grading:** the resolution arithmetic is audited. Log-parser equivalence is not (fixture M03).
- **Metadata fixture:** specified as M01–M02 in [`fixtures_planned.json`](../experiments/v2_adapter/fixtures_planned.json).
- **Runtime:** later no-change and reference-patch execution controls remain required. The arm64/no-container host is still a feasibility blocker.
