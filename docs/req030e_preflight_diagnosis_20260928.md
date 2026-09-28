# REQ030E: diagnose exact failed isolation assertion, replay native bindings

REQ030D27724883 FAILED1:0 after14sec. Image build succeeded, isolationstdoutempty, logonlycwdmissingwarning. Originalscriptset-e checks homeabsence first; syntheticemptyhome vs hostmount is a plausible explanation, not yet measured. Preserve archive results/local_req030/sandbox_preflight_20260928. No production sandbox qualified; no model/benchmark run follows failure.

Release one CPU-only diagnostic10min2CPU8GiB/day/pi_gt353. Newrun req030-sandbox-diagnosis-20260928-a; exactsources sandbox_diagnosis.sbatch and deployment_replay.py. Reuse originalSIF afterSHAcheck; no newdownload. Retain containall/cleanenv/no-home/nohostbinds/networknone, setcwd/ explicitly. Fixedread-onlyscript prints presence/count for3paths, networkinterfaces andmounttable into privateartifact; sanitize hostpathinventory before publicarchive. Does not execute modeloutput or relaxisolation.60sec subprocess+15kill, Slurm10min. Originalprobeunchanged; diagnostic notautomaticallyacceptance.

SameCPUjob independently replays both savedcoder32 native templates/tokenIDs/outputdecodes with frozenlocaltokenizer; no load/generation. Capture exactTransformersQwen2sourcesha and relevantSWAconditionexcerpts; configuse_sliding_windowfalse.120sec+15kill. Isolatedrun uses priorNumPy1.26.4 packages, no sharedmutation. Shellsyntax/Pythoncompilepass. Sourcepublishbeforedispatch.

Afterterminalreview decide based on actualmounts andnamespace evidence whether strictsandbox can bequalified or use an alreadyisolatedlocaltoolhost+HPCinference. Never execute agentcode unsandboxed. Nextqueue taskseaborn3187 unchanged. Readiness55%,Δ0,range45–65%; competentcomparison/validinference,synthesis,reproducibility/authorpackage remain.
