# REQ030V lead prompt-binding review — 29 September 2026

## Scientific question

Does the source-only Seaborn runner preparation construct the first two
mini-swe-agent messages from exactly the approved public task projection and
the exact pinned upstream system/instance templates? This is the next
implementation gate after the independently accepted REQ030R evaluator
controls. It is not a model result.

## Frozen inputs and implementation

The public projection remains
`docs/source_snapshots/req030p_seaborn_public/public_task.json`, SHA-256
`b3fb8c08d74d92279a7caf77bf714c77ac3eee2dbafc996596b786c5484954e9`, with
exact keys `instance_id`, `base_commit`, and `problem_statement` for
`mwaskom__seaborn-3187` at base `22cdfb0c93f8ec78492d87edb810f10cb7f57a31`.
The new upstream snapshot at
`docs/source_snapshots/req030t_miniswe_agent/default.yaml` is byte-identical
to mini-swe-agent revision
`04d809ceab9df28f9adaed044884180159172930`'s
`src/minisweagent/config/default.yaml`; its SHA-256 is
`112aa58328f478a41cc2630702a4b89ef459e912870e05065157ed221f56701f`. Its
MIT license and source URLs are recorded beside it. The extracted literal
`system_template` and `instance_template` SHA-256 values are respectively
`5c9bba45e018c7fbf379c8c1a91cce06deecc26670764ce86810e37523c59d2d` and
`cdf5e8dc1972686b90e3e84a0a4b200874ad5aaf1e3d26c26ed1872c1ba2e9b0`.
The pinned observation/format-error template hashes are
`4cd54626f03be2dd572eeffbe31d9421d73c167d4feb79dc3c1b4336d0568e31` and
`04fce5694c2695cc0cc4672cd6d7678f398402a99b0b3379fb397f06c00baca8`.
The text-action regex is a lead-declared fixed parser candidate, not an
upstream YAML field; its exact pattern and hash are recorded in the manifest.

`experiments/lead_req030/seaborn_public_input.py` now fails closed on any
change to either pinned byte source. It accepts raw public-projection bytes,
revalidates their digest/schema/task/base, allows only four non-task metadata
keys (`system`, `release`, `version`, `machine`), and returns the pinned
system/instance templates with finite agent step, wall-time, and format-error
limits. It also supplies the pinned observation/format-error templates to the
native HF adapter and the fixed lead-declared action regex. The metadata keys
mirror the pinned upstream Docker environment's `platform.uname()` values on
the agent host; this helper restricts their shape but does not attest their
provenance. A production receipt must bind those values to the actual Slurm
host process (not claim they came from inside Apptainer). The returned values
are designed for the pinned upstream call shape
`DefaultAgent(model, env, **agent_config).run(task=problem_statement)`.
An independent helper reproduces the two initial messages using the same
Jinja `StrictUndefined` rendering semantics as the upstream agent.

## Evidence and interpretation

The source-only suite now has 17 passing tests (the prior focused set had
15). The integration fixture executes the pinned upstream `DefaultAgent`
source with the candidate config prepared from the frozen projection, a fake
model, and an inert fake environment. It verifies the initial messages match
the independently rendered expected messages byte-for-byte, checks fixed
message hashes for the test environment, exercises the pinned observation and
format-error templates through the native adapter, and observes one fake
action ending in the expected `Submitted` sentinel. Tampered projection/config
bytes, extra environment keys, and an unbounded step limit are rejected. No weights
were loaded, no real tool command ran, and no evaluator/reference input was
available to the fixture.

This resolves the narrow prompt-fixture gap: the earlier test-authored
templates are no longer the only evidence for the initial task messages. It
does **not** qualify the production runner. In particular, the runner-host
`platform.uname()` values used by the pinned upstream Docker environment and
the exact prompt must still be bound in a single run receipt; no durable event writer, production guardian integration,
or real controller-to-container run has been exercised here. The test's fake
environment cannot prove production provenance or isolation.

## Decision and next gate

Accept REQ030V as source/test evidence for exact public-input parsing and
initial-prompt construction against the pinned `DefaultAgent`. Do not call it
agent/environment qualification, model competence, or a model release. Next,
consolidate the native HF adapter, all pinned model-facing templates/parser,
bounded supervisor/guardian, prompt/token/event receipts, and Apptainer
workspace into one inert end-to-end qualification harness. That harness must
exercise startup failure, normal submission, timeout/output cap, owner death
with escaped descendants, and cleanup, with all prompt provenance saved before
any task generation. Then freeze a competent comparator and task/family-level
development estimand before considering a separate, exact model-run release.
The one Seaborn issue cannot estimate task-population success or a routing
effect, and the 250 nested test statuses remain one task.

Readiness remains **55%**, change **0 points**, judgment range **45–65%**.
The major remaining milestones are a competent fixed-target comparison with
valid task/family-level inference, empirical/manuscript synthesis,
independent reproducibility, and the author-approved submission package.
