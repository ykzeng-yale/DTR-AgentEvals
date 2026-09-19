"""Replace host-specific absolute paths in published experiment artifacts with a placeholder.

A candidate program that crashes deep inside the standard library produces a traceback containing the interpreter's
absolute path, which on this host sits under the researcher's home directory. That text is a genuine tool result and
was shown to the model, so it is not deleted - only the host prefix is masked.

IMPORTANT: the branch audit rebuilds a confirm episode's transcript from its stored `trace` and compares the hash with
the one logged before the model call. Masking a CONFIRM episode's trace would therefore turn a faithful restoration
into a reported mismatch. This tool refuses confirm-split episodes unless --after-branch is given.

This file lives outside experiments/code_routing and experiments/common on purpose: those directories are hashed into
every episode's `code_sha256`, and publishing housekeeping must not change the experiment's code identity.

  python experiments/tools/sanitize_artifacts.py results/code_routing/log/episodes.jsonl [...] [--after-branch] [--check]
"""
from __future__ import annotations
import argparse, hashlib, json, os, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOME = os.path.expanduser('~')
PATTERNS = [(re.escape(HOME), '<HOME>')]
RECORD = ROOT / 'results' / 'code_routing' / 'redactions.json'


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def scan(text: str) -> int:
    return sum(len(re.findall(p, text)) for p, _ in PATTERNS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', nargs='+')
    ap.add_argument('--after-branch', action='store_true', help='allow masking confirm-split episodes (only once the branch audit has run)')
    ap.add_argument('--check', action='store_true', help='report only, change nothing')
    a = ap.parse_args()
    report = []
    for sp in a.paths:
        path = Path(sp).resolve()
        raw = path.read_text()
        before = scan(raw)
        if not before:
            report.append(dict(file=rel(path), occurrences=0, action='clean'))
            continue
        lines = raw.splitlines()
        blocked, masked, out = [], 0, []
        for line in lines:
            if not line.strip():
                out.append(line); continue
            if scan(line) and not a.after_branch:
                try:
                    rec = json.loads(line)
                except ValueError:
                    rec = {}
                if rec.get('split') == 'confirm':
                    blocked.append(rec.get('episode_id', '?')); out.append(line); continue
            new = line
            for p, repl in PATTERNS:
                new = re.sub(p, repl, new)
            masked += scan(line); out.append(new)
        if blocked:
            print('REFUSED to mask %d confirm-split episode(s) in %s (would break branch-audit restoration hashes): %s'
                  % (len(blocked), path, blocked[:5]))
        if not a.check and masked:
            sha_before = hashlib.sha256(raw.encode()).hexdigest()
            path.write_text('\n'.join(out) + '\n')
            sha_after = hashlib.sha256(path.read_text().encode()).hexdigest()
            report.append(dict(file=rel(path), occurrences=before, masked=masked, refused_confirm_episodes=blocked,
                               sha256_before=sha_before, sha256_after=sha_after))
        else:
            report.append(dict(file=rel(path), occurrences=before, masked=0 if a.check else masked, refused_confirm_episodes=blocked))
        print('%s: %d host-path occurrence(s), %d masked' % (path, before, 0 if a.check else masked))
    if not a.check:
        old = json.loads(RECORD.read_text()) if RECORD.exists() else []
        RECORD.write_text(json.dumps(old + report, indent=1))


if __name__ == '__main__':
    main()
