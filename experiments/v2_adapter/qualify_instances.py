"""DTR-REQ-002 fixture M02: pre-sampling test-list qualification (lead decisions 91c8bcc and 8ecdfde).

The selected evaluator (SWE-bench f7bbbb2) silently turns a MISSING FAIL_TO_PASS/PASS_TO_PASS key into [] and grades an
empty list as 1, i.e. vacuously resolved. Qualification therefore happens BEFORE sampling, on the original dataset rows,
and never rewrites their content:
  refused   FAIL_TO_PASS or PASS_TO_PASS key missing; either list malformed (not a list of strings, or a string that
            does not parse to one); FAIL_TO_PASS empty; a required identity field missing or empty.
  eligible  otherwise. An explicitly EMPTY PASS_TO_PASS is allowed and recorded as a regression-coverage limitation.
Dataset rows store the lists as JSON strings; native lists are accepted too. Nothing here downloads, installs or runs
anything: it is a pure function over one instance dict. Running it on the 500 real rows is part of M01 and needs the
dataset file, which has not been downloaded.
"""
from __future__ import annotations
import hashlib, json

REQUIRED_FIELDS = ('instance_id', 'repo', 'version', 'base_commit', 'test_patch', 'environment_setup_commit')
TEST_LISTS = ('FAIL_TO_PASS', 'PASS_TO_PASS')


def parse_test_list(instance, key):
    """Return (list_of_str, None) or (None, reason). Never coerces a missing key to []."""
    if key not in instance:
        return None, '%s missing' % key
    value = instance[key]
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None, '%s is a string that is not valid JSON' % key
    if not isinstance(value, list):
        return None, '%s is %s, not a list' % (key, type(value).__name__)
    if not all(isinstance(x, str) and x for x in value):
        return None, '%s contains a non-string or empty test id' % key
    return value, None


def content_sha256(instance):
    return hashlib.sha256(json.dumps(instance, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def qualify(instance):
    reasons, limitations, lists = [], [], {}
    for f in REQUIRED_FIELDS:
        if not isinstance(instance.get(f), str) or not instance.get(f):
            reasons.append('%s missing or empty' % f)
    for key in TEST_LISTS:
        parsed, why = parse_test_list(instance, key)
        if why:
            reasons.append(why)
        else:
            lists[key] = parsed
    if 'FAIL_TO_PASS' in lists and not lists['FAIL_TO_PASS']:
        reasons.append('FAIL_TO_PASS empty: the evaluator would grade it as resolved vacuously')
    if 'PASS_TO_PASS' in lists and not lists['PASS_TO_PASS'] and not reasons:
        limitations.append('PASS_TO_PASS empty: regression preservation is untested for this instance')
    return dict(instance_id=instance.get('instance_id'), status='refused' if reasons else 'eligible',
                reasons=reasons, limitations=limitations,
                n_fail_to_pass=len(lists.get('FAIL_TO_PASS', [])) if 'FAIL_TO_PASS' in lists else None,
                n_pass_to_pass=len(lists.get('PASS_TO_PASS', [])) if 'PASS_TO_PASS' in lists else None,
                content_sha256=content_sha256(instance))
