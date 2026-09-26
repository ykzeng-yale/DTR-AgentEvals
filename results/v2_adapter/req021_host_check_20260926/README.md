# DTR-REQ-021: one-time existing-host capacity check — BLOCKED

Lead request: [`9fae0e4`](../../../docs/theory_feedback_20260926_req020_decision.md) (section "P0 DTR-REQ-021").

The check is read-only and local. No other machine was contacted and no cloud API was called. There was no download,
server, VM change, inference, reservation or task exposure. Built by `experiments/v2_adapter/req021_host_check.py`
(tests in `tests/test_req021_host_check.py`); the record is `host_check.json`, with its host readings timestamped.

## Verdict: BLOCKED

No already accessible, no-cost host can keep both REQ-020 models (Klear-AgentForge-8B and Qwen3-4B-Instruct-2507)
resident at 32k/48 calls with f16 KV under the pinned evaluator. Per the lead, the local configuration search stops
here. The finding covers access configured on this machine only.

| Gate | Result |
|---|---|
| H1 another accessible no-cost host | **none configured for access on this machine.** The SSH config and its `Include` hold one `Host` entry, the local Colima VM; the only known SSH host is a code-hosting service; there are no remote Docker contexts; one Colima profile. A Google Cloud account and project are configured, but cloud compute is paid and provisioning is not authorized; whether the project already holds an instance is unknown, because no cloud API was called. VPN and remote-desktop clients are installed, but institutional resources reachable through them are not visible locally. No names are published. |
| H2 this host, static memory | **fails.** 32.065 GiB (both Q4 weights + both f16 KV at 32768 tokens + 16 GiB VM allowance) > 30 GiB limit, before compute buffers and prompt caches |
| H3 this host, post-load reserve | **fails.** About 9.8 % of physical memory projected free after loading both models, against the 20 % required |

This host has 32 GiB. The evaluator VM (`dtr`) is running.

**What a host would need** (for the lead). This pair at 32k with f16 KV, one 16 GiB VM allowance and at least 20 %
free after load needs:
- at least **40.1 GiB** of physical RAM before compute buffers and prompt caches;
- at least **60.1 GiB** if both of the pinned llama-server's default 8 GiB prompt caches fill.

Both are lower bounds, because compute buffers and OS use are excluded.

Compute buffers cannot be measured without starting a server. Serving and template compatibility carry over from
REQ-020 and remain unverified without a run: the jinja/autoparser path, and the ```bash fence,
`MINI_SWE_AGENT_FINAL_OUTPUT` sentinel and edit tool that Klear was trained on.
