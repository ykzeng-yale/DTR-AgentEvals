# REQ030X job 27841116 — retrieved failure evidence

Retrieved directly from the verified auxiliary-Mac SSH route at 2026-09-29T12:22:58Z from Bouchet login `login1.bouchet.ycrc.yale.edu` as `yz2324`.

Slurm accounting: `pi_gt353/day`, `FAILED 1:0`, elapsed 86 seconds, 2 CPUs, request 8 GiB, batch MaxRSS 3,097,372 KiB. The exact log verifies all 13 payload checksums, the Seaborn task SIF SHA-256 `9da1f51cb8c01a6ad9e0db4d1969742fbec995021e78150a9623d4f4719a8a47`, model manifest SHA-256 `27d054c155e7767ca2048d66c900d75131bf9a6c263fdce5180e06ed5fe6bad6`, and seed workspace SHA-256 `3cc8a60a720e00816e2853bce4e47d58705443cf6f4e8a4531ca69ae458b8100` (also the copied workspace hash).

Failure: `ModuleNotFoundError: No module named 'minisweagent'` while importing `native_hf_text_adapter.py`. The module loader that installs the exact pinned package/parser runs later in the driver. `runner-output/` was empty and the qualification stdout file was zero bytes. Therefore no actual Apptainer preflight, workspace action, model call, benchmark test, evaluator action, or task score occurred. Preserve this as an implementation/bootstrap failure, not model failure or pass.

Files in `raw/` are direct retrievals of the remote Slurm log, exit JSON, empty qualification stdout, accounting, output-directory inventory, and a host/time/source-hash provenance record. `SHA256SUMS` binds these local raw files. The extra empty-output inventory is preserved to document that no receipts were created.
