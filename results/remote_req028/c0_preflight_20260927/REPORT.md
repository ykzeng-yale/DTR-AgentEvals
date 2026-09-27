# REQ-028C0 pre-supervisor implementation acceptance

Release6397da7 and C0 plan/frozen prompt/latest handoff entry read. Scope: two serial interface-only initial calls, Klear q4 then Qwen q8, identical frozen first-two messages, max_tokens1536. No generated command execution, benchmark, competence claim, transport, VM or CONFIRM.

Focused command: python3 -m unittest test_guard test_followup test_admission test_a4 test_a5 test_a6 test_a6r test_b2 test_b2r test_b3_stop test_b3_contract test_b4 test_c0. Observed75 tests passed in2.454seconds. This includes11 new C0 tests and all64 B4-era tests, including real-inert-child cleanup cases. Launcher repeats and archives tests before supervisor creation.

Verified B4 supervisor64074/model65440/watchdog65443 absent before source publication; launcher rechecks before dispatch. Frozen document1d99595667cee6fbab3af480eba0ca7ed4c9976abc5530b396c2cf78903d5d8a, source478b321f86a9591ff9488e69a90614ba7159ba29eb1176701d155353da7aba06, compact-JSON message hashf8178479369ca97aed5c7f836b04da2c679225ddf10807033799c3a2f441b106 all verified. Only first system/user role-content messages enter requests.

Each arm retains300-second setup, one900-second/31read admission,600-second model phase,180-second load/request, unchanged resource/ownership guards and B3 coordinated cleanup. Total program deadline3600seconds; no renewal/retry. Each arm must reach infrastructure COMPLETE and confirmed model/watchdog absence before continuation. Terminal interface failure permits the predefined second arm, but any infrastructure/release failure marks it unattempted. At most two model loads/two generation requests.

Pinned parser acceptance is separate from nonempty command, thinking-boundary and combined stopped-response interface gate. Literal printf scoring is not used. Commands are never executed or assessed for correctness. Native template checks are exact pinned Klear one-LF relation and Qwen byte equality. No assumption of equal rendered token counts; each requires1536-token headroom and usage binding.

No supervisor was started for this preflight. Product goal remains blocked; readiness55%,change0,range45–65%. After published source/tests, launch exactly once and return actual handles/deadlines without polling unchanged admission or inference.
