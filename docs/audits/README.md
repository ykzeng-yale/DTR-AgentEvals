# Dated artifact audits

`code_routing_artifact_audit_035d245.json` records the independent internal artifact review of experiment commit `035d245f6fa10450f7cf89420bc1947d4c54aebc` on 19 September 2026. It preserves the reviewer's scope and limitations. It does not independently execute generated programs, rescore hidden tests or certify causal results.

Reproduce the artifact checks from any full checkout containing that commit:

```sh
python3 docs/audits/check_code_routing_035d245.py
```

The standard-library-only script reads pinned Git objects and writes its report under ignored `work/`; it does not change the archived report or experiment files. A failed consistency check causes a nonzero exit. The primary agent reran this archived script and verified byte-for-byte agreement with the saved report. The audit found zero failures across 75 check types; repeated per-record checks are not independent statistical evidence.

A separate theory reviewer independently reconstructed all 17 learned-policy entries from TRAIN records and checked the mathematical applicability of the planned analyses. That review's findings and acceptance criteria are in [the theory feedback](../theory_feedback_20260919.md); they are broader than the artifact script and should not be inferred from its pass status. The compiled paper was not rebuilt during this cycle; its PDF and all 13 files listed in `manuscript/validation.json` still match the recorded hashes.
