# DTR-REQ-023: reusable non-overlap process gate, version 1

Lead request: [`4bbf7e0`](../../../docs/theory_feedback_20260926_req022_decision.md) (section "P1 DTR-REQ-023"). Code
hygiene only: no model, peer job, simulation or new stage was started, and nothing was re-run.
- **Code:** `experiments/v2_sim/process_gate_v1.py`.
- **Tests:** `tests/test_req023_process_gate.py`.
- **Record:** `record.json`, with the source and test sha256, the focused test outcome, one read-only snapshot on this
  host, and the frozen REQ-022 check.

The frozen REQ-022 launcher `experiments/v2_sim/null_control_batch.py` (sha256 `41febb7c…`, byte-identical to
`bc4a71e`) and every file in `results/v2_sim/null_control_20260926/` are unchanged. The new gate is a separate helper
for future authorized jobs; the frozen launcher keeps its own gate and its deviation label.

## The two REQ-022 defects and how v1 handles them

- **Self-match.** The frozen gate excluded only its own PID, so it matched the parent shell whose command line named
  the script. v1 reads the process table and walks the current process's ancestor chain to pid 1. It excludes exactly
  that owned chain plus the current process's own descendants (for example its worker pool).
- **Same-module blind spot.** The frozen gate searched only for the file name, so it could not see
  `python -c "import null_control_batch ..."`. v1 flags any other interpreter process whose command line references the
  module, case-insensitively, in any of these forms:
  - `<module>.py`, `import <module>`, `from <module>`, `-m <module>` or `-m<module>`, or a bare token;
  - a python reading stdin or starting a REPL (`python -`, `/dev/stdin`, a heredoc) when any ancestor's command line
    names the module (bash keeps a `-c` heredoc's text in its own arguments).

  The executable name comes from ps `comm`, so paths with spaces and suffixed builds (`python3.13t`,
  `python3.12-intel64`) are covered. An editor or `tee <module>.log` is not an interpreter, so it is not a peer.
- **Other peers:** stage runners (`run.py` with `--stage` anywhere after it), `dev_batch*` and `coverage_batch*`
  successors, and model servers.
- **Unknown identity refuses (passed = false):**
  - the table cannot be read;
  - the current process is missing from it;
  - its ancestor chain is broken or cyclic;
  - a non-owned process with a hidden command line (`(name)` on macOS) has a name that could be an interpreter or a
    server.

## Verification

**Fixtures:** 17 deterministic tests in `tests/test_req023_process_gate.py`, all passing (the record gives the
command and the sha256 of the source and the tests). All but one use injected process tables or raw ps text; that
one calls the live read-only gate and checks the version and the real source hash. They cover:
- **No self-match:** the REQ-022 attempt-1 case (the parent shell names the script); a grandparent wrapper and the
  process's own worker pool; the process's own heredoc launch.
- **No missed same-module peer:** `python -c`, the file name, `-m` with and without a space, a case-variant path,
  `uv run`, an interpreter under a path with spaces, suffixed builds (`python3.13t`, `python3.12-intel64`,
  `python3.12d`), stdin, heredoc and REPL launches (`-`, `-i`, `/dev/stdin`, clustered `-uX dev`), and a second
  heredoc copy under a shared wrapper.
- **Not peers:** unrelated python, a similarly named module, an editor, the process's own `tee`, a stdin python whose
  launcher names nothing, and a name that only looks like an interpreter (`pythonfoo`).
- **Other peers:** stage runners in any flag order, `dev_batch`/`coverage_batch` successors, and model servers.
- **Unknown identity refuses:** an unreadable table, a missing self, a broken or cyclic chain, a hidden `(python3.12)`,
  `(Python)` or `(uv)`. Hidden `(mlhostd)`, `(UVFSService)` and `(UVCAssistant)` do not refuse.
- **ps parsing:** names with spaces are kept whole, and full command lines are kept.

**Review.** An independent review of the first version found a blocker: on real macOS ps output, an interpreter whose
command line is hidden appears as `(python3.12)` and its name is truncated or parenthesized, so the unknown-identity
refusal never fired. It also found minor misses: `-m` without a space, a pipeline `tee` flagged, and `--stage`
before other flags.
- These were fixed by reading `comm` in its own ps call, matching suspect names by prefix, matching module names only
  on interpreters, and making the stage pattern order-free.
- A second review found six minor issues. Four let a peer through: an interpreter path with a space, a heredoc or stdin
  python, suffixed interpreter names, and the narrower `coverage_batch` pattern. The fifth was the `uv` prefix
  refusing on the macOS daemons UVFSService and UVCAssistant. The sixth was a set of undocumented conservative false
  positives.
  - All were fixed or documented, with a fixture each.
  - Real 2-second dummy probes (scratch scripts named like the module that only sleep) confirmed detection of the
    space-path, `python3.13t` and heredoc peers on real ps text.
- A third, focused review found no self-match regression. It found minor misses in the stdin rule:
  - a spaced interpreter path in the stdin parser;
  - clustered `-uX`/`-uW` values;
  - `/dev/stdin` and `/dev/fd/0`;
  - two heredoc copies under one shared wrapper.

  These were fixed, with fixtures. A heredoc launched by `zsh -c` is a documented limit: zsh execs its last command,
  so the heredoc text is in no process's arguments.

**Live read-only snapshot.** Recorded in `record.json`. It depends on the host at that moment and is not an
acceptance fixture. During review, a sibling project's test process whose arguments contained a `llama-server` path
was reported as a peer. That is the intended conservative behavior (the frozen gate would match it too); it means a
foreign job naming a model server blocks a run.

## Limits (documented in the module)

A command-line scan cannot see a peer in any of these cases:
- its module name is built at run time;
- it runs a copied or symlinked script under another name;
- it imports the module indirectly;
- it is typed into an interactive shell or REPL whose command lines never name the module;
- it is a heredoc launched by `zsh -c` or `zsh -lc` (zsh 5.9 execs its last command, so the text is in no process's
  arguments);
- its argv[0] was renamed (`exec -a`; on macOS `comm` follows argv[0]).

Such peers need an ownership lease, not a process scan.

It also blocks conservatively in these cases, where the operator inspects and retries:
- a concurrent read-only `process_gate('<module>')` check;
- a `pgrep`/`tail` monitor naming a model server;
- any foreign process whose arguments name a model server;
- an editor, `tail` or test run whose arguments contain `dev_batch` or `coverage_batch`;
- an unrelated stdin python under a wrapper whose text names the module.

It never kills, signals or starts a process.
