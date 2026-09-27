# Next development image metadata, no acquisition or execution

Lead queried only Docker registry index/AMD64 manifest/config metadata for the first three remaining REQ-009 queue entries. Task IDs were fixed before querying availability; no model/test outcomes were read. Source naming follows the locally pinned SWE-bench test_spec.py rule; exact file hash and raw manifests/configs are in results/local_req029/image_metadata_20260927. Each index, child manifest and config digest was independently checked against its bytes. Anonymous registry tokens were not saved. No layers were pulled, images built, containers started or models invoked.

| Candidate | Compressed layer bytes | AMD64 manifest digest |
|---|---:|---|
| django__django-16560 | 1,240,896,221 | sha256:0bafff953ce186aa261162d4091549fb4ad49df938900474b5f070d511bb1604 |
| matplotlib__matplotlib-20826 | 2,258,509,781 | sha256:7ae350b0a6b3fe3cc4165ac10b81dbdcace7a65b8a608988043611a05473e3ef |
| mwaskom__seaborn-3187 | 1,295,121,476 | sha256:6c0cd3296b90a84889796531ab87a0ed8779015b2bbd2e8d99adbdef95397b03 |

These are per-image compressed layer sums, not unique transfer requirements or extracted disk sizes. Availability is not image/environment qualification. A future exact acquisition must use the resolved digest, bound transfer/storage/time and preserve peer images/containers. It must precede no-change/reference controls in the actual proposed sandbox. The old exposed Astropy image/control cannot substitute. Full host/project exposure reconciliation remains required; registry availability does not certify untouchedness or pretraining status. Metadata queries transfer55,373bytes including unsaved anonymous authorization responses; all retained content is public image metadata.

No task/model/CONFIRM or image-acquisition authorization is created by this note. The next lead action is a bounded exact first-candidate image qualification design, preserving the fixed queue and reporting infrastructure failure rather than choosing on model success. REQ-029E remains remote source/inert integration only. Readiness55%,change0points,range45–65%;competent fixed-target comparison/valid inference,synthesis,reproducibility/author-approved package remain.
