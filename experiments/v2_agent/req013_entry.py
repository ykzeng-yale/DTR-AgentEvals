"""DTR-REQ-013 (lead 702e58a, docs/theory_feedback_20260924_req012_decision.md): the REQ-012 entry, unchanged, bound to
the REQ-013 manifest for its one 14B assignment. req013_pair.py launches it in the pinned mini-swe-agent venv:

    work/venvs/minisweagent_04d809c/bin/python experiments/v2_agent/req013_entry.py <control>/entry.json

req012_entry.main runs unedited, with the same yaml-v1-repair1 overrides (the prompt addition, --network none, the
RepeatedFailureGuardAgent stall guard), the same refusals and the same records. In this process only, bind() does two
things. It rebinds the two module constants the REQ-012 entry uses to find its manifest and label its records
(MANIFEST_REL, REQUEST). It also adds this file's own sha256 to the admitted-source check. No source file is edited.
"""
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import req012_entry as R  # noqa: E402  FIRST: it imports cue_episode before minisweagent loads

REQUEST = 'DTR-REQ-013'
MANIFEST_REL = 'configs/v2_req013_14b_discriminator_20260924.json'
SOURCE_REL = R.REL + 'req013_entry.py'
SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def bind(module=R):
    """Rebind req012_entry (in this process) to the REQ-013 manifest and add this file to its source check."""
    base_refusals, base_digests = module.refusals, module.running_digests

    def running_digests():
        return dict(base_digests(), **{'req013_entry.py': SOURCE_SHA256})

    def refusals(control, environ=None, proxies=None):
        reasons = base_refusals(control, environ, proxies)
        if (control.get('admitted_sources') or {}).get(SOURCE_REL) != SOURCE_SHA256:
            reasons.append('running req013_entry.py is not the admitted source')
        return reasons
    module.MANIFEST_REL, module.REQUEST = MANIFEST_REL, REQUEST
    module.running_digests, module.refusals = running_digests, refusals
    return module


def main(argv=None):
    return bind().main(argv)


if __name__ == '__main__':
    sys.exit(main())
