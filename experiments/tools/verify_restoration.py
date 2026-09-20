"""Independently recompute the branch stage's restoration evidence from immutable inputs.

Every branch episode carries `restoration.transcript_hash_matches`, a boolean the RUNNER wrote. A reviewer is
entitled to ask whether that boolean is true. This recomputes it from the frozen inputs alone:

  * rebuild the transcript that preceded the parent's t=1 decision, exactly as the runner's
    `restore_first_failure_prefix` does, from the frozen task file, the frozen visible tests and the parent's own
    recorded stage-0 reply and trace;
  * hash it and compare with `transcript_sha256` that the parent logged BEFORE its own t=1 model call;
  * compare the recomputed verdict with the boolean the branch episode stored.

It does not re-execute any model or candidate code. A mismatch would mean either that restoration was not faithful
or that a record has changed since it was written.

  python experiments/tools/verify_restoration.py
"""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for sub in ('code_routing', 'common'):
    sys.path.insert(0, str(ROOT / 'experiments' / sub))
import common, agent as AG, analysis as A  # noqa: E402


def main() -> int:
    cfg = common.load_config()
    tasks = {t['uid']: t for t in common.load_tasks(cfg)}
    vt = json.loads((common.RESULTS / 'visible_tests.json').read_bytes())['tests']
    vtests = {u: r['certified'] for u, r in vt.items()}
    tasks_sha = hashlib.sha256(Path(common.resolve(cfg['tasks_path'] if cfg['tasks_path'].startswith(('/', '~'))
                                                   else str(common.ROOT / cfg['tasks_path']))).read_bytes()).hexdigest()
    # the exact prompt/helper text that determines a transcript's bytes
    prompt_rev = hashlib.sha256(''.join([AG.SYS_CODE, AG.ASK_REPAIR, AG.SYS_TEST, AG.ASK_TESTS]).encode()).hexdigest()
    log, _ = A.read(common.RESULTS / 'log' / 'episodes.jsonl', cfg)
    parents = {e['episode_id']: e for e in log if not e.get('error')}
    br, _ = A.read(common.RESULTS / 'branch' / 'episodes.jsonl', cfg)

    n = recomputed_true = agreed = 0
    missing_parent = mismatch = tool_recheck_ok = branch_hash_ok = 0
    examples = []; covered = []
    for e in br:
        pid = e.get('parent_episode_id')
        par = parents.get(pid)
        if par is None:
            missing_parent += 1; continue
        n += 1
        d0, d1 = par['decisions'][0], par['decisions'][1]
        convo = [dict(role='system', content=AG.SYS_CODE),
                 dict(role='user', content=AG.task_prompt(tasks[par['task_uid']])),
                 dict(role='assistant', content=d0['reply']),
                 dict(role='user', content=AG.repair_message(vtests[par['task_uid']], d0['trace']))]
        h = hashlib.sha256(json.dumps(convo, sort_keys=True).encode()).hexdigest()
        ok = (h == d1['transcript_sha256'])
        recomputed_true += ok
        stored = bool((e.get('restoration') or {}).get('transcript_hash_matches'))
        agreed += (ok == stored)
        covered.append(e['episode_id'])
        # the branch episode logged its OWN t=1 transcript hash before its first call; it must equal the
        # recomputation too, so altering the branch-side hashes while leaving the parent's intact cannot pass
        own = next((d.get('transcript_sha256') for d in e.get('decisions', []) if d.get('t') == e.get('fork_t')), None)
        branch_hash_ok += (own == h)
        if own != h and len(examples) < 3:
            examples.append(dict(episode_id=e['episode_id'], reason='branch-side transcript hash differs from recomputation'))
        if ok != stored:
            mismatch += 1
            if len(examples) < 3:
                examples.append(dict(episode_id=e['episode_id'], parent=pid, recomputed=ok, stored=stored))
        if (e.get('restoration') or {}).get('tool_result_reproduced'):
            tool_recheck_ok += 1

    def fsha(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    out = dict(branch_episodes_checked=n, missing_parent=missing_parent,
               branch_side_transcript_hash_matches=branch_hash_ok,
               # bind the report to the exact files and episode set it was computed from
               source_binding=dict(branch_episodes_sha256=fsha(common.RESULTS / 'branch' / 'episodes.jsonl'),
                                   log_episodes_sha256=fsha(common.RESULTS / 'log' / 'episodes.jsonl'),
                                   visible_tests_sha256=fsha(common.RESULTS / 'visible_tests.json'),
                                   # the task file is not redistributed; it is regenerable from public sources by
                                   # experiments/tools/regenerate_tasks.py, which verifies this same hash
                                   tasks_sha256=tasks_sha,
                                   branch_decisions_sha256=fsha(common.RESULTS / 'branch' / 'decisions.jsonl'),
                                   log_decisions_sha256=fsha(common.RESULTS / 'log' / 'decisions.jsonl'),
                                   prompt_helper_revision=prompt_rev,
                                   covered_episode_ids_sha256=hashlib.sha256('\n'.join(sorted(covered)).encode()).hexdigest(),
                                   n_covered=len(covered)),
               recomputed_transcript_hash_matches=recomputed_true,
               stored_flag_agrees_with_recomputation=agreed, disagreements=mismatch, examples=examples,
               stored_tool_result_reproduced=tool_recheck_ok,
               method='transcript rebuilt from the frozen task file, frozen certified visible tests and the parent\'s '
                      'recorded stage-0 reply and trace; hashed and compared with the hash the parent logged before '
                      'its own t=1 model call. No model or candidate code was executed.',
               caveat='this verifies the recorded transcript hash and the stored flag. It does not re-execute the '
                      'tool, so `tool_result_reproduced` is reported as stored, not independently recomputed.')
    (common.RESULTS / 'analysis' / 'restoration_recheck.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return 0 if (mismatch == 0 and missing_parent == 0 and recomputed_true == n and branch_hash_ok == n and n > 0) else 1


if __name__ == '__main__':
    raise SystemExit(main())
