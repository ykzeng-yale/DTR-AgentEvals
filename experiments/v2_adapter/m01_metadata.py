"""DTR-REQ-002 fixture M01: test-spec metadata construction for all 500 original SWE-bench Verified rows at the selected
evaluator SWE-bench f7bbbb2 (lead 91c8bcc). Authorized by the author on 21 September 2026 ("download all you need").

Runs ONLY inside the isolated venv work/venvs/swebench_f7bbbb2 (upstream installed editable from the pinned source tarball).
It constructs test specs (Python metadata and script TEXT); it never executes a generated script, starts a container or
runs the benchmark.
  inputs    work/benchmark_inputs/swebench_verified_c104f840/test-00000-of-00001.parquet (SHA-256 checked below)
  pass 1    RECORD: M02 qualification for every row, then make_test_spec for every eligible row, with requests.get
            intercepted so every external input (raw GitHub files at pinned setup commits) is saved with URL and SHA-256
  pass 2    REPLAY: rebuild every spec with the network REPLACED by the saved inputs (an unknown URL raises); scripts must
            be byte-identical, so repeatability does not depend on live downloads
  checks    500 rows; qualification counts; (repo, version) present in the constants; no FAIL_ONLY repository; every row's
            content hash unchanged by construction; per-instance eval/env/repo script hashes; image keys and architecture
Outputs: results/v2_adapter/m01_c104f840_f7bbbb2/{summary.json, instances.jsonl, external_inputs.json}; raw external files
are cached under work/benchmark_inputs/swebench_external_inputs/ (ignored by git).
"""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import qualify_instances as Q  # noqa: E402

DATA = ROOT / 'work/benchmark_inputs/swebench_verified_c104f840/test-00000-of-00001.parquet'
DATA_SHA = 'a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd'
CACHE = ROOT / 'work/benchmark_inputs/swebench_external_inputs'
OUT = ROOT / 'results/v2_adapter/m01_c104f840_f7bbbb2'


def sha(b):
    return hashlib.sha256(b).hexdigest()


class Resp:
    def __init__(self, status, text):
        self.status_code, self.text = status, text


def main():
    import requests
    import pandas as pd
    import swebench
    from swebench.harness.constants import FAIL_ONLY_REPOS, MAP_REPO_VERSION_TO_SPECS
    from swebench.harness.test_spec.test_spec import make_test_spec

    raw = DATA.read_bytes()
    if sha(raw) != DATA_SHA:
        raise SystemExit('dataset checksum mismatch')
    rows = pd.read_parquet(DATA).to_dict('records')
    CACHE.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
    fetched = {}
    real_get = requests.get

    def recording_get(url, *a, **k):
        r = real_get(url, *a, **k)
        body = r.text.encode()
        name = sha(url.encode())[:24]
        (CACHE / name).write_bytes(body)
        fetched[url] = dict(status=r.status_code, bytes=len(body), sha256=sha(body), cache_file=name)
        return Resp(r.status_code, r.text)

    def replay_get(url, *a, **k):
        if url not in fetched:
            raise RuntimeError('replay: URL was not recorded: %s' % url)
        return Resp(fetched[url]['status'], (CACHE / fetched[url]['cache_file']).read_bytes().decode())

    def spec_hashes(inst):
        ts = make_test_spec(inst)
        return dict(eval_script_sha256=sha(ts.eval_script.encode()), env_script_sha256=sha(ts.setup_env_script.encode()),
                    repo_script_sha256=sha(ts.install_repo_script.encode()), instance_image_key=ts.instance_image_key,
                    env_image_key=ts.env_image_key, base_image_key=ts.base_image_key, arch=ts.arch,
                    n_fail_to_pass=len(ts.FAIL_TO_PASS), n_pass_to_pass=len(ts.PASS_TO_PASS))

    records, first = [], {}
    requests.get = recording_get
    for row in rows:
        inst = {k: (v if not hasattr(v, 'item') else v.item()) for k, v in row.items()}
        before = Q.content_sha256(inst)
        q = Q.qualify(inst)
        rec = dict(instance_id=inst['instance_id'], repo=inst['repo'], version=inst['version'], qualification=q['status'],
                   reasons=q['reasons'], limitations=q['limitations'], content_sha256=before,
                   repo_version_in_constants=inst['version'] in MAP_REPO_VERSION_TO_SPECS.get(inst['repo'], {}),
                   fail_only_repo=inst['repo'] in FAIL_ONLY_REPOS)
        if q['status'] == 'eligible':
            try:
                first[inst['instance_id']] = spec_hashes(inst)
                rec.update(first[inst['instance_id']], construction='ok')
            except Exception as e:
                rec.update(construction='error', error='%s: %s' % (type(e).__name__, str(e)[:200]))
        rec['content_unchanged_by_construction'] = Q.content_sha256(inst) == before
        records.append(rec)
    requests.get = replay_get
    replay_equal, replay_errors = 0, []
    for row in rows:
        inst = {k: (v if not hasattr(v, 'item') else v.item()) for k, v in row.items()}
        if inst['instance_id'] in first:
            try:
                replay_equal += spec_hashes(inst) == first[inst['instance_id']]
            except Exception as e:
                replay_errors.append('%s: %s' % (inst['instance_id'], e))
    requests.get = real_get
    ok = [r for r in records if r.get('construction') == 'ok']
    summary = dict(
        request='DTR-REQ-002 M01: metadata construction for all 500 original rows at SWE-bench f7bbbb2 (no execution)',
        dataset=dict(path=str(DATA.relative_to(ROOT)), sha256=DATA_SHA, rows=len(rows)),
        evaluator=dict(commit='f7bbbb2ccdf479001d6467c9e34af59e44a840f9', package_version=swebench.__version__,
                       install='editable from the pinned source tarball in work/venvs/swebench_f7bbbb2'),
        qualification={s: sum(r['qualification'] == s for r in records) for s in ('eligible', 'refused')},
        empty_pass_to_pass_limitation=sum(bool(r['limitations']) for r in records),
        construction_ok=len(ok), construction_errors=[r for r in records if r.get('construction') == 'error'],
        repo_version_missing=[r['instance_id'] for r in records if not r['repo_version_in_constants']],
        fail_only_repositories_present=sorted({r['repo'] for r in records if r['fail_only_repo']}),
        content_changed=[r['instance_id'] for r in records if not r['content_unchanged_by_construction']],
        replay_identical=replay_equal, replay_errors=replay_errors,
        external_inputs=dict(n_urls=len(fetched), non_200=[u for u, v in fetched.items() if v['status'] != 200]),
        architectures=sorted({r['arch'] for r in ok}), repositories=sorted({r['repo'] for r in records}),
        distinct_eval_scripts=len({r['eval_script_sha256'] for r in ok}),
        not_done=['no generated script executed', 'no container or image built/pulled', 'no benchmark run',
                  'image digests not resolved (keys only)'])
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    (OUT / 'instances.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in records))
    (OUT / 'external_inputs.json').write_text(json.dumps(fetched, indent=1, sort_keys=True) + '\n')
    print(json.dumps({k: summary[k] for k in ('qualification', 'construction_ok', 'replay_identical', 'external_inputs',
                                              'fail_only_repositories_present', 'architectures', 'distinct_eval_scripts')}, indent=1))
    print('errors:', len(summary['construction_errors']), '| repo_version_missing:', len(summary['repo_version_missing']),
          '| content_changed:', len(summary['content_changed']), '| replay_errors:', len(replay_errors))


if __name__ == '__main__':
    main()
