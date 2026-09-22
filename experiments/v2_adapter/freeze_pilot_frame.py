"""DTR-REQ-002: freeze the initial qualification frame and the fixed-backend DEV pilot task list (lead e360831 spec
configs/v2_fixed_backend_development_pilot_20260922.json) BEFORE any pilot model outcome. No model, no evaluator.

  * binds the 11 new pre-identity qualification records by immutable SHA-256 (legacy_hash_manifest.json, not rewritten)
    and admits each only through qualification_batch.task_state (terminal + evaluator + hash checks)
  * frame = the fixed 12-task manifest with ORIGINAL terminal outcomes; eligible = qualified, excluding the
    outcome-diagnosed pallets__flask-5014; K and N=min(8,K) recorded; order by SHA256(seed_label\\ninstance_id), ties
    by instance_id; no substitution
  * first backend per task: low bit of SHA256(seed_label\\ninstance_id\\norder); 0 -> small (7B) first, 1 -> large (14B)
  * pins each selected task's instance-image digest from its qualification record and checks the local image still
    has that ID (a missing/changed image is recorded, not silently rebuilt)
Output: results/v2_agent/pilot_frame_20260922.json (write-once).
"""
import hashlib, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import qualification_batch as QB  # noqa: E402

SPEC = ROOT / 'configs/v2_fixed_backend_development_pilot_20260922.json'
FLASK = 'pallets__flask-5014'
FLASK_REC = ROOT / 'results/v2_adapter/smoke_flask_20260922/summary.json'
FRAME = ROOT / 'results/v2_agent/pilot_frame_20260922.json'


def h(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def rank_key(seed, iid):
    return (h(seed + '\n' + iid), iid)


def first_backend(seed, iid):
    return 'small' if int(h(seed + '\n' + iid + '\n' + 'order'), 16) & 1 == 0 else 'large'


def select(seed, eligible, target_n):
    ranked = sorted(eligible, key=lambda i: rank_key(seed, i))
    n = min(target_n, len(ranked))
    return ranked, n, ranked[:n]


def local_image_id(iid):
    tag = 'sweb.eval.x86_64.%s:latest' % iid.lower()
    p = subprocess.run(['docker', 'image', 'inspect', '--format', '{{.Id}}', tag], capture_output=True, text=True)
    return tag, (p.stdout.strip() if p.returncode == 0 else None)


def main():
    spec = json.loads(SPEC.read_text())
    man = json.loads(QB.MANIFEST.read_text())
    expected = QB.expected_identity()
    legacy = json.loads(QB.LEGACY_MANIFEST.read_text()) if QB.LEGACY_MANIFEST.exists() else QB.build_legacy_manifest(QB.OUT, expected)
    tasks = []
    for t in man['tasks']:
        iid = t['instance_id']
        if iid == FLASK:
            raw = FLASK_REC.read_bytes(); rec = json.loads(raw)
            qualified = all(rec['acceptance'].values()) and bool(rec.get('smoke_check_passed'))
            path, digest = FLASK_REC.relative_to(ROOT), hashlib.sha256(raw).hexdigest()
        else:
            state, s, digest = QB.task_state(QB.OUT, iid, expected=expected, legacy=legacy)
            if state != 'completed':
                raise SystemExit('frame not complete: %s is %s' % (iid, state))
            rec = json.loads(Path(s).read_bytes()); path = Path(s).relative_to(ROOT); qualified = rec['qualified']
        tasks.append(dict(instance_id=iid, repo=t['repo'], record=str(path), record_sha256=digest, qualified=qualified,
                          failed_acceptance=[k for k, v in rec['acceptance'].items() if not v],
                          eval_script_sha256=t['eval_script_sha256'], instance_image=rec['image_digests']['instance']))
    sel = spec['selection']
    eligible = [t['instance_id'] for t in tasks if t['qualified'] and t['instance_id'] != FLASK]
    ranked, n, chosen = select(sel['seed_label'], eligible, sel['target_n'])
    by = {t['instance_id']: t for t in tasks}
    pilot = []
    for i, iid in enumerate(chosen, 1):
        tag, local = local_image_id(iid)
        fb = first_backend(sel['seed_label'], iid)
        pilot.append(dict(position=i, instance_id=iid, rank_sha256=rank_key(sel['seed_label'], iid)[0], first_backend=fb,
                          backend_order=[fb, 'large' if fb == 'small' else 'small'], record_sha256=by[iid]['record_sha256'],
                          instance_image=by[iid]['instance_image'], local_image_tag=tag, local_image_id=local,
                          local_image_matches_record=local == by[iid]['instance_image']))
    frame = dict(
        request='DTR-REQ-002', spec=str(SPEC.relative_to(ROOT)), spec_sha256=hashlib.sha256(SPEC.read_bytes()).hexdigest(),
        qualification_manifest=str(QB.MANIFEST.relative_to(ROOT)), expected_identity=expected,
        legacy_hash_manifest=str(QB.LEGACY_MANIFEST.relative_to(ROOT)),
        legacy_hash_manifest_sha256=hashlib.sha256(QB.LEGACY_MANIFEST.read_bytes()).hexdigest(),
        frozen_before_any_pilot_model_outcome=True,
        frame=dict(selected=len(tasks), qualified=sum(bool(t['qualified']) for t in tasks),
                   diagnosed_unqualified=[t['instance_id'] for t in tasks if not t['qualified']], tasks=tasks),
        pilot=dict(excluded=[FLASK], excluded_reason='already used for outcome-guided diagnosis (spec)', K=len(eligible), N=n,
                   seed_label=sel['seed_label'], ordering=sel['ordering'],
                   ranked_eligible=[dict(instance_id=i, rank_sha256=rank_key(sel['seed_label'], i)[0], selected=i in chosen) for i in ranked],
                   first_backend_rule='low bit of SHA256(seed_label\\ninstance_id\\norder) with the literal word "order"; 0 -> small (Qwen2.5-Coder-7B), 1 -> large (Qwen2.5-Coder-14B). Worker binding of the unspecified bit->backend map, recorded before launch.',
                   tasks=pilot, episodes_max=2 * n),
        scope='frame freeze and task selection only: no model call, no evaluator run, no pilot outcome exists at freeze time')
    FRAME.parent.mkdir(parents=True, exist_ok=True)
    with open(FRAME, 'x') as fh:
        fh.write(json.dumps(frame, indent=1) + '\n')
    print(json.dumps(dict(K=len(eligible), N=n, chosen=[(p['instance_id'], p['first_backend'], p['local_image_matches_record']) for p in pilot],
                          unselected=[i for i in ranked if i not in chosen]), indent=1))


if __name__ == '__main__':
    main()
