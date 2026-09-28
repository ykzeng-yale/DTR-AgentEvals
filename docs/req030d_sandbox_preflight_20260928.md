# REQ030D: compute-node container capability gate

Coder32 REQ030C finished twoEOS responses (37/35 and8844/4tokens),8.818/1.686sec,peak69,689,973,760bytes; no taskcompetence. Exactsource/rendered-message/output-count review passed. NumPybridgepassed. Native token replay remains pending. Modelconfig explicitly use_sliding_window=false although Transformers warns about populated sliding_window; retain warning, investigate source before taskrelease.

Next frozen REQ009 development queue task is mwaskom__seaborn-3187, not any priorfailedtask. No task generation/evaluator released here. Before porting its tool execution, qualify Bouchet container isolation. /usr/bin/apptainer exists but execution onlogin returned Permissiondenied; compute-node capability is unmeasured. Do not bypass policy or run generatedcode onhost.

Authorize ONE exact CPU-only preflight: source experiments/lead_req030/sandbox_preflight.sbatch, day/pi_gt3532CPU8GiB10min, pull300sec+15kill, fixedscript60sec+15kill, oneApptainerinvocation. Alpine3.21.3 linuxamd64 manifestsha256:1c4eef651f65e2f7daee7ee785882ac164b02b78fb74503052a26dc061c90474 fromofficialDockerregistry. Up to1GiB newfiles (smallimage expectation), ownprivatecache/temp; no benchmarkdata/newLLMweights. Slurmboundsprocesses. Test private namespaces/networknone/nohome/nohostbinds; assert onlyloopback and common hostpathsabsent. Rootfsread-only bydefault. RecordbuiltSIFhash/version/rawlog/exit. No services or generatedcommands.

A pass establishes only this fixed Alpine invocation, not production sandbox. Need taskimage/base/source/environment/evaluator/control and guardian/outputcap/timeouts qualification before actualtask. A fail closes this route until boundeddiagnosis; consider alreadyqualified localisolatedexecution plusGPU inference via authenticatedtransport. No unisolatedhostexecutionfallback.

Readiness55%,Δ0,range45–65%; competentcomparison/validinference,synthesis,reproducibility/authorpackage remain.
