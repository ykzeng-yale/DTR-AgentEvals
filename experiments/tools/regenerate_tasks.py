"""Rebuild the frozen task file from its public sources and verify it against the design hash.

The 591-task file is NOT redistributed in this repository: MBPP-sanitized and HumanEval carry their own licences
(CC-BY-4.0 and MIT respectively) and the repository policy is to commit manifests and scripts, not third-party data.
That left an independent reviewer unable to reconstruct agent transcripts. This script closes that gap: it downloads
the two public sources, applies the exact canonicalisation the study used, and checks the result byte-for-byte
against `tasks_sha256` recorded in the frozen design.

  python experiments/tools/regenerate_tasks.py --out work/code_routing_data/tasks.json

Exit status is non-zero unless the rebuilt file matches the frozen hash, so this doubles as a provenance test.
Canonicalisation (must not change): MBPP records sorted by numeric task_id ascending, then HumanEval by numeric
index ascending; per-record fields exactly as below; serialised with sort_keys=True,
(',', ':') separators and **ensure_ascii=False** (the last of these is load-bearing: ensure_ascii=True yields a
different byte stream and a different hash).
Sources and licences are recorded in the emitted manifest.
"""
from __future__ import annotations
import argparse, gzip, hashlib, io, json, re, sys
from pathlib import Path

MBPP_URL = 'https://raw.githubusercontent.com/google-research/google-research/master/mbpp/sanitized-mbpp.json'
HUMANEVAL_URL = 'https://github.com/openai/human-eval/raw/master/data/HumanEval.jsonl.gz'
LICENCES = dict(mbpp='CC-BY-4.0 (dataset card google-research-datasets/mbpp); repo google-research/google-research is Apache-2.0',
                humaneval='MIT (openai/human-eval LICENSE)')
_ASSERT_NAME = re.compile(r'assert\s+(?:[A-Za-z_][\w.]*\()*\s*([A-Za-z_]\w*)\s*\(')
_DEF_NAME = re.compile(r'^def\s+([A-Za-z_]\w*)\s*\(', re.M)


def mbpp_entry_point(rec) -> str:
    for t in rec.get('test_list', []):
        m = _ASSERT_NAME.search(t)
        if m and re.search(r'def\s+%s\s*\(' % re.escape(m.group(1)), rec['code']):
            return m.group(1)
    defs = _DEF_NAME.findall(rec['code'])
    return defs[-1] if defs else ''


def build_tasks(mbpp_raw: list, humaneval_raw: list) -> list:
    tasks = []
    for rec in sorted(mbpp_raw, key=lambda r: int(r['task_id'])):
        tasks.append(dict(uid='mbpp/%d' % int(rec['task_id']), benchmark='mbpp', source_task_id=int(rec['task_id']),
                          prompt=rec['prompt'].strip(), entry_point=mbpp_entry_point(rec),
                          signature_example=rec['test_list'][0] if rec['test_list'] else '',
                          reference=rec['code'], test_imports=list(rec.get('test_imports') or []),
                          test_list=list(rec['test_list']), challenge_test_list=list(rec.get('challenge_test_list') or [])))
    for rec in sorted(humaneval_raw, key=lambda r: int(r['task_id'].split('/')[-1])):
        tasks.append(dict(uid='humaneval/%d' % int(rec['task_id'].split('/')[-1]), benchmark='humaneval',
                          source_task_id=rec['task_id'], prompt=rec['prompt'], entry_point=rec['entry_point'],
                          signature_example='', reference=rec['prompt'] + rec['canonical_solution'], test=rec['test']))
    return tasks


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='work/code_routing_data/tasks.json')
    ap.add_argument('--design', default='results/code_routing/design.json')
    ap.add_argument('--offline-from', help='verify an existing file instead of downloading')
    a = ap.parse_args()
    want = json.loads(Path(a.design).read_text())['tasks_sha256']

    if a.offline_from:
        text = Path(a.offline_from).read_text()
        dl = dict(mode='offline verification of %s' % a.offline_from)
    else:
        import requests
        m = requests.get(MBPP_URL, timeout=120); m.raise_for_status()
        h = requests.get(HUMANEVAL_URL, timeout=120); h.raise_for_status()
        mbpp_raw = json.loads(m.content.decode())
        humaneval_raw = [json.loads(l) for l in gzip.GzipFile(fileobj=io.BytesIO(h.content)).read().decode().splitlines() if l.strip()]
        if len(mbpp_raw) != 427 or len(humaneval_raw) != 164:
            print('unexpected counts: mbpp=%d humaneval=%d' % (len(mbpp_raw), len(humaneval_raw))); return 1
        text = canonical_json(build_tasks(mbpp_raw, humaneval_raw))
        dl = dict(mbpp=dict(url=MBPP_URL, bytes=len(m.content), sha256=hashlib.sha256(m.content).hexdigest()),
                  humaneval=dict(url=HUMANEVAL_URL, bytes=len(h.content), sha256=hashlib.sha256(h.content).hexdigest()))
    got = hashlib.sha256(text.encode()).hexdigest()
    ok = got == want
    if ok and not a.offline_from:
        out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(text)
    report = dict(matches_frozen_design=ok, rebuilt_sha256=got, frozen_tasks_sha256=want, n_tasks=text.count('"uid":'),
                  downloads=dl, licences=LICENCES,
                  canonicalisation='MBPP by numeric task_id then HumanEval by numeric index; json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=False)',
                  note='third-party task data is not redistributed here; this procedure regenerates it from the public sources')
    Path('results/code_routing/analysis/task_regeneration.json').write_text(json.dumps(report, indent=1))
    print(json.dumps({k: report[k] for k in ('matches_frozen_design', 'rebuilt_sha256', 'frozen_tasks_sha256', 'n_tasks')}, indent=1))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
