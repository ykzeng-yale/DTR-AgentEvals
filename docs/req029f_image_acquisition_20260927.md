# REQ-029F — one pinned task-image layer acquisition, data only

Lead release: acquire the first remaining fixed REQ-009 queue candidate, django__django-16560, once. Selection precedes task/model outcomes. This releases no model, image import, extraction, container, evaluator, new weights or task trajectory. Exposure reconciliation and actual environment/negative/reference controls remain prerequisites to later inference.

Use repository `swebench/sweb.eval.x86_64.django_1776_django-16560`, exact AMD64 manifest `sha256:0bafff953ce186aa261162d4091549fb4ad49df938900474b5f070d511bb1604`. Its ten compressed layers total1,240,896,221bytes. The exact retained manifest and image config were hash-verified in the metadata stage. Compression size does not bound expanded disk use; no expansion is authorized here.

Publish the source below before launching once with `.venv/bin/python experiments/lead_req029/image_acquire.py work/local_req029/django_image_layers_20260927`. Exclusive output-directory creation prevents resume/relaunch. Read-only preflight observed normal pressure1/free64%,59.6GiB disk available,zero containers in colima-dtr. Recheck before dispatch. No VM/peer/cache changes.

One serial streaming downloader, one connection at a time,64KiB buffers,10MiB/s application body rate with at most one buffer burst,900second alarm/deadline,10second HTTP timeout,300CPU-second hard rlimit,nice10. Cap received response-body bytes at1.5GiB; headers/TLS/redirect overhead are not included and this is not a wire-byte claim. Require12GiB disk reserve and normal pressure/free>=40% every5seconds. CPU execution is serial; no CPU-affinity or hard RSS enforcement is claimed. Streaming buffers are bounded. No retries/renewals/fallback; first error terminates and retains partial data and receipt. A forced OS termination may leave only partial data, not a terminal receipt.

Anonymous read tokens remain in memory and are omitted from receipts; HTTPS redirect strips Authorization. Verify every layer length and SHA before rename. No archive member is extracted or executed. Huge layers remain under ignored work/; publish small terminal/source/hash receipts only. Lead independently hashes retained layers after terminal completion. Success means artifact acquisition only, not Docker import, reproducibility or task competence.

Six executed local deterministic tests passed in0.003seconds: immutable manifest, redirect credential removal, deadline/body cap, auth failure/no repeat, streamed success/corrupt digest retention, and cumulative rate limiting. Test bodies are inert; no network was used by tests.

Source pins:
- `experiments/lead_req029/image_acquire.py`: `5603b34bbf4e4a16344a77ab4cb89b206935b9a30ecd911b05b89efbe84778ff`
- `experiments/lead_req029/test_image_acquire.py`: `6e55aa1aa38a19250bb5a38a9943a9fb486c30dd9dece79d9f5ef747b4d5cf21`

Readiness55%,change0points,range45–65%; competent fixed-target comparison/valid inference, empirical/manuscript synthesis, independent reproducibility and author-approved package remain. REQ-029E source review continues separately; no duplicate remote assignment.
