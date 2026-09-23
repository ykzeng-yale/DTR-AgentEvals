# DTR-REQ-005 cue-v1 integration: no-model acceptance package

**23 September 2026, worker. NO live episode was run.** No model, llama-server, container, evaluator or network
call was made, and `results/v2_agent/pilot_20260923_cue_v1` was not created. Live release still needs two things:
the lead's review of this package, and a fresh host agreement. This is deterministic fixture evidence. It is not
pilot or confirmatory evidence, and it says nothing about whether the cue helps.

The machine-readable artifact is [`req005_integration_acceptance_20260923.json`](req005_integration_acceptance_20260923.json).
It holds the exact source manifest (path and sha256 of every bound and new module, fixture and document), the literal
pytest output of every integration and component test file, each lead acceptance item mapped to its tests, every
verdict repair, and every contract point not implemented exactly.

## What was built

- **`experiments/v2_agent/cue_episode.py`** is the new cue-v1 episode driver. It is derived from the frozen
  `pilot_episode.py`, which it imports read-only and does not edit. It does no work until
  `cue_admission.admit_episode` has passed. That check validates the whole frozen queue, the open runner session,
  this run's frozen assignment row, the bytes of every module the process runs, and the pinned SDK and
  mini-swe-agent files it actually imports.
  - The cue: logical ids are authoritative, including parse failures and refused queries, and each logical call
    feeds exactly one detector record. The 290-byte cue is appended once, as one user message, before the next
    permitted query after the trigger. In the baseline arm the same landmark is recorded silently.
  - Transport: the capture wraps the real `httpx.HTTPTransport` at `litellm.client_session`, so every physical send
    is receipted before it leaves.
  - Terminal phase: the Submitted-only endpoint is determined inside the inference window, as in the frozen driver.
    The supervised diagnostic and the container cleanup then always run afterwards.
- **Repairs** to `cue_transport.py`, `cue_terminal.py`, `cue_admission.py` and `cue_runner.py`, for every confirmed
  verdict item. The lead-accepted helpers are unchanged.
- **Acceptance fixtures.**
  - `test_v2_cue_integration.py` covers items (a) to (h). It runs the frozen driver's own `main()` as the pinned
    reference and the cue driver through `cue_runner` and admission, all in the pinned interpreter.
  - `test_v2_cue_episode.py` covers the intervention logic.
  - The component fixture files were extended.

## The acceptance items, in one line each

- **(a)** Baseline request bodies, headers and model-visible messages are byte-identical to the frozen driver's.
- **(b)** The cue arm differs only by the one 319-byte cue message after the third observation.
- **(c)** `A,A,FormatError,A` does not trigger. A retry re-sends the same single cue. An H24 final-call trigger stays
  undelivered, and so does a pre-dispatch storage refusal after insertion.
- **(d)** A hung diagnostic is SIGKILLed at its bound, and its processes are gone.
- **(e)** Cleanup runs after both capture errors and receipt stops.
- **(f)** A storage refusal sends nothing and stops the queue.
- **(g)** A corrupted receipt is detected and refuses the resume.
- **(h)** Every Submitted endpoint is the same hand-typed 379-byte diff.

## Points for the lead (not implemented exactly, or needing a decision)

The JSON lists all of them. The main ones:
1. The capture disables litellm's hidden second pass. Where that changes the outcome the caller observes, the
   change is reported as `frozen_path_parity: deviated`. It does not stop the queue; whether it should is your call.
2. The diagnostic deadline carries a 4-second hand-off margin, so cleanup keeps its full 90 s.
3. No repository source declares the host disk reserve. The launcher must supply it.
4. The live host/server step is not implemented: `run_assignment` refuses, because the release is held.
5. Please confirm the cue form: one user message appended at the end of the history.

Full-project readiness is unchanged at the lead's estimate of **55% (change 0 percentage points)**. This package
provides no empirical result. The largest remaining milestones are still the lead's three:
- useful validated inference and adequate real-agent comparisons;
- final empirical synthesis and statistical consistency;
- independent reproducibility, author-approved metadata and submission packaging.
