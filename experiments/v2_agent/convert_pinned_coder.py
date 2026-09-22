"""DTR-REQ-002 option A (worker-prepared; the served-file choice A/B is the lead's): convert BOTH Coder backends from the
spec-pinned safetensors commits with ONE llama.cpp commit, hashing every input, intermediate and output. CPU only; no
server is started and no generation happens.

  HF safetensors @ pinned commit --(verified against the Hub LFS sha256)--> convert_hf_to_gguf.py --outtype bf16
  --> llama-quantize Q4_K_M (no imatrix)

Writes results/v2_agent/coder_conversion_20260922.json (write-once). Idempotence: an existing output file is never
overwritten; a partial run fails loudly instead of reusing a file of unknown provenance.
"""
import hashlib, json, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LLAMA = ROOT / 'work/upstream/llama.cpp-4fea119'
LLAMA_COMMIT = '4fea119de30f6a923992780f6fd5ccb0bee5d47d'
PY = ROOT / 'work/venvs/llamacpp_4fea119/bin/python'
HF = ROOT / 'work/models/hf'
OUTD = ROOT / 'work/models/converted_4fea119'
REC = ROOT / 'results/v2_agent/coder_conversion_20260922.json'
PINS = [('small', 'Qwen/Qwen2.5-Coder-7B-Instruct', 'c03e6d358207e414f1eca0bb1891e29f1db0e242'),
        ('large', 'Qwen/Qwen2.5-Coder-14B-Instruct', 'aedcc2d42b622764e023cf882b6652e646b95671')]


def sha256(p, bs=1 << 24):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(bs), b''):
            h.update(b)
    return h.hexdigest()


def hub_tree(repo, rev):
    with urllib.request.urlopen('https://huggingface.co/api/models/%s/tree/%s' % (repo, rev), timeout=60) as r:
        return json.loads(r.read())


def run(cmd, log):
    t0 = time.time()
    with open(log, 'x') as fh:
        p = subprocess.run([str(c) for c in cmd], stdout=fh, stderr=subprocess.STDOUT)
    if p.returncode:
        raise SystemExit('failed (%d): %s; see %s' % (p.returncode, ' '.join(map(str, cmd)), log))
    return round(time.time() - t0, 1)


def main():
    if REC.exists():
        raise SystemExit('refusing to overwrite %s' % REC)
    OUTD.mkdir(parents=True, exist_ok=True)
    tools = {n: dict(path=str((LLAMA / 'build/bin' / n).relative_to(ROOT)), sha256=sha256(LLAMA / 'build/bin' / n))
             for n in sorted(p.name for p in (LLAMA / 'build/bin').iterdir() if p.is_file() and not p.is_symlink())}
    head = subprocess.run(['git', '-C', str(LLAMA), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', '-C', str(LLAMA), 'status', '--porcelain', '--untracked-files=no'], capture_output=True, text=True).stdout.strip()
    assert head == LLAMA_COMMIT and not dirty, (head, dirty)
    rec = dict(request='DTR-REQ-002', option='A (prepared by the worker; lead chooses A or B before any episode)',
               llama_cpp=dict(commit=head, clean=True, build='Release, GGML_METAL=ON, GGML_METAL_EMBED_LIBRARY=ON, LLAMA_CURL=OFF', tools=tools,
                              convert_script_sha256=sha256(LLAMA / 'convert_hf_to_gguf.py')),
               python=subprocess.run([str(PY), '-c', 'import sys,torch,transformers,numpy,gguf;print(sys.version.split()[0],torch.__version__,transformers.__version__,numpy.__version__)'],
                                     capture_output=True, text=True).stdout.strip(),
               imatrix=None, backends={})
    for role, repo, rev in PINS:
        src = HF / ('%s@%s' % (repo.split('/')[1], rev[:7]))
        tree = {e['path']: e for e in hub_tree(repo, rev) if e.get('type') == 'file'}
        inputs = {}
        for path, e in sorted(tree.items()):
            f = src / path
            if not f.exists():
                raise SystemExit('missing download %s' % f)
            got = sha256(f)
            want = (e.get('lfs') or {}).get('oid')
            if want and got != want:
                raise SystemExit('hash mismatch %s: %s != hub %s' % (f, got, want))
            inputs[path] = dict(bytes=f.stat().st_size, sha256=got, hub_lfs_sha256_match=bool(want) or None)
        stem = repo.split('/')[1].lower() + '-' + rev[:7]
        bf16, q4 = OUTD / (stem + '-bf16.gguf'), OUTD / (stem + '-q4_k_m.gguf')
        for p in (bf16, q4):
            if p.exists():
                raise SystemExit('refusing to reuse existing %s' % p)
        conv_cmd = [PY, LLAMA / 'convert_hf_to_gguf.py', src, '--outtype', 'bf16', '--outfile', bf16]
        t_conv = run(conv_cmd, OUTD / (stem + '-convert.log'))
        quant_cmd = [LLAMA / 'build/bin/llama-quantize', bf16, q4, 'Q4_K_M']
        t_quant = run(quant_cmd, OUTD / (stem + '-quantize.log'))
        rec['backends'][role] = dict(
            repository=repo, source_commit=rev, inputs=inputs,
            convert=dict(cmd=' '.join(str(c).replace(str(ROOT) + '/', '') for c in conv_cmd), seconds=t_conv),
            bf16=dict(file=str(bf16.relative_to(ROOT)), bytes=bf16.stat().st_size, sha256=sha256(bf16)),
            quantize=dict(cmd=' '.join(str(c).replace(str(ROOT) + '/', '') for c in quant_cmd), seconds=t_quant),
            q4_k_m=dict(file=str(q4.relative_to(ROOT)), bytes=q4.stat().st_size, sha256=sha256(q4), shards=1))
        print(role, rec['backends'][role]['q4_k_m'], flush=True)
    rec['scope'] = 'conversion only: no server started, no generation, no episode'
    with open(REC, 'x') as fh:
        fh.write(json.dumps(rec, indent=1) + '\n')


if __name__ == '__main__':
    main()
