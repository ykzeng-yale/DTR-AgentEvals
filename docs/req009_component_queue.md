# DTR-REQ-009: near-duplicate component screen and 24-ID design queue (metadata only)

Lead decision: `docs/theory_feedback_20260924_req008_decision.md` (`0fe40b8`). Record: `results/v2_adapter/req009_component_queue.json`; script `experiments/v2_adapter/req009_component_queue.py` (sha256 `ac1b5d826422c0c43c37f4daa909d61ba5b67b87c8840e46262f91093c53992e`), HEAD `eba48b596324423e8e46f6faed6214e4e77ff49f`, script tracked and unchanged: True, worktree clean: True. Written once; do not edit.

**Scope.** Metadata-only design screen. No model, evaluator, container, GPU, Monte Carlo or download; no test outcome or model output read; PASS_TO_PASS not decoded; the patch column is decoded in memory and each line tested only for the "diff --git " prefix, retaining header paths only (no other patch text stored, printed, emitted or inspected). The queue is for later competence/qualification planning; it is not an evaluation sample, a power target or a release of any stage.

**Result.** 412 candidates remain after the lead's exclusions; the queue has **24 IDs** (full: True). Edges: 29 (29 shared FAIL_TO_PASS, 0 same base commit + shared patch path); 14 multi-member components, of which 4 contain an exposed or qualification/inspection-only ID and are excluded; largest component 7.

Exclusion reasons over the 500-ID frame: candidate 412, component_touches_exposed_or_qualification_only 11, empty_pass_to_pass 8, model_outcome_exposed 64, qualification_or_inspection_only 5. Empty-P2P exclusion is individual and does not spread to a component; only exposed or qualification/inspection-only IDs taint a component.

Field audit: 500 rows, 0 missing fields, 0 unparsed headers; 71 tasks with more than one patch path (max 21). Within-repository same-base-commit pairs: 1 (`django__django-15268`/`django__django-15278`, 0 shared paths); none shares a patch path, so the base-commit edge kind is empty in this frame.

| Repository | total | exposed | qualification/inspection only | empty P2P | component-excluded | candidates | queued |
|---|---:|---:|---:|---:|---:|---:|---:|
| astropy/astropy | 22 | 4 | 0 | 0 | 0 | 18 | 3 |
| django/django | 231 | 30 | 3 | 5 | 8 | 185 | 3 |
| matplotlib/matplotlib | 34 | 2 | 0 | 0 | 0 | 32 | 3 |
| mwaskom/seaborn | 2 | 1 | 0 | 0 | 0 | 1 | 1 |
| pallets/flask | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| psf/requests | 8 | 2 | 0 | 0 | 3 | 3 | 2 |
| pydata/xarray | 22 | 2 | 1 | 0 | 0 | 19 | 2 |
| pylint-dev/pylint | 10 | 2 | 0 | 2 | 0 | 6 | 2 |
| pytest-dev/pytest | 19 | 4 | 0 | 0 | 0 | 15 | 2 |
| scikit-learn/scikit-learn | 32 | 2 | 0 | 0 | 0 | 30 | 2 |
| sphinx-doc/sphinx | 44 | 9 | 1 | 1 | 0 | 33 | 2 |
| sympy/sympy | 75 | 5 | 0 | 0 | 0 | 70 | 2 |

## Queue (design input only; not a frozen evaluation sample)

Order: SHA-256 of `DTR-REQ-009|c104f840|<instance_id>` within repository, lexicographic round-robin over repositories. Queue sha256 `d19efbc4b14eb249f7cbe69429b4a6e53e962bee77ff6736d05bb20eb000d4cc`; complete ordered list (412 IDs) sha256 `c79a3d1df53f58344a0d7f7f946063ea17ef8b2aa9524ca9e6fad45979d44d64`.

1. `astropy__astropy-14598`
2. `django__django-16560`
3. `matplotlib__matplotlib-20826`
4. `mwaskom__seaborn-3187`
5. `psf__requests-2931`
6. `pydata__xarray-3151`
7. `pylint-dev__pylint-8898`
8. `pytest-dev__pytest-6202`
9. `scikit-learn__scikit-learn-13328`
10. `sphinx-doc__sphinx-8269`
11. `sympy__sympy-19954`
12. `astropy__astropy-14365`
13. `django__django-12039`
14. `matplotlib__matplotlib-26208`
15. `psf__requests-6028`
16. `pydata__xarray-6461` (component of 3; candidate mates: `pydata__xarray-4687`, `pydata__xarray-7229`)
17. `pylint-dev__pylint-6386`
18. `pytest-dev__pytest-10081`
19. `scikit-learn__scikit-learn-25102`
20. `sphinx-doc__sphinx-8593` (component of 2; candidate mates: `sphinx-doc__sphinx-8035`)
21. `sympy__sympy-13551`
22. `astropy__astropy-14539`
23. `django__django-17087`
24. `matplotlib__matplotlib-25960`

Any later split or freeze must keep whole components on one side.

## Multi-member components

| component | repository | size | contains exposed/QI | excluded |
|---|---|---:|---|---|
| `django__django-10097` | django/django | 7 | `django__django-10097`, `django__django-11163` | True |
| `django__django-10973` | django/django | 4 | - | False |
| `django__django-11820` | django/django | 4 | `django__django-14672` | True |
| `django__django-12308` | django/django | 2 | `django__django-12308`, `django__django-13512` | True |
| `django__django-14017` | django/django | 2 | - | False |
| `matplotlib__matplotlib-25311` | matplotlib/matplotlib | 2 | - | False |
| `psf__requests-1724` | psf/requests | 4 | `psf__requests-1921` | True |
| `pydata__xarray-4687` | pydata/xarray | 3 | - | False |
| `sphinx-doc__sphinx-7454` | sphinx-doc/sphinx | 2 | - | False |
| `sphinx-doc__sphinx-8035` | sphinx-doc/sphinx | 2 | - | False |
| `sphinx-doc__sphinx-8551` | sphinx-doc/sphinx | 2 | - | False |
| `sphinx-doc__sphinx-9461` | sphinx-doc/sphinx | 2 | - | False |
| `sympy__sympy-15599` | sympy/sympy | 2 | - | False |
| `sympy__sympy-16766` | sympy/sympy | 3 | - | False |

Edge witnesses (shared FAIL_TO_PASS identifiers or base commit + paths) are in the JSON record.

## Checks

- instances_sha256_equals_req008_pin: True
- parquet_sha256_equals_req008_pin: True
- frame_is_500_unique: True
- req008_rows_equal_frame: True
- req008_id_set_sha256: True
- req008_zero_unknown: True
- req008_pins_reconciled: True
- dataset_revision_is_c104f840: True
- conservative_counts_64_5_431: True
- not_yet_assessed_list_equals_lead_hash: True
- fail_to_pass_counts_equal_req008: True

## Limits

- Edges use only the two lead-specified relations on pinned metadata; other forms of near-duplication (similar issue text, overlapping but non-identical tests) are not screened.
- Exposure is from this repository's committed records (REQ-008); public or pretraining exposure is not measured.
- The parquet is git-ignored; reproduction needs the pinned file (sha256 in inputs).
- FAIL_TO_PASS identifiers are compared as declared strings; their qualification varies by repository (some repositories, e.g. sympy, declare bare function names), so the identical-identifier edge is only as specific as the declared names. The base-commit + path edge is nearly vacuous here (one same-commit pair, no shared path).
- No queued ID is runtime-qualified; qualification, competence and precision are for the lead's next plan.
