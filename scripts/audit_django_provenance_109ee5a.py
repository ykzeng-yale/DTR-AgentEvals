#!/usr/bin/env python3
"""Recount immutable Django diagnostic logs; no runtime or causal isolation."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '109ee5aa5ea52c63a7e710960b38b43954373e86'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    records = {}
    for stem in ['stock_gold', 'adapter_reference_attempt1', 'adapter_no_change_attempt1']:
        path = 'results/v2_adapter/qualification_20260922/django__django-10097/' + stem + '_test_output.txt'
        raw = subprocess.check_output(['git', 'show', COMMIT + ':' + path], cwd=ROOT)
        text = raw.decode()
        # unittest can print the test's docstring between ERROR: and the dashed
        # traceback separator. Requiring dashes immediately after the header
        # silently omits eight template errors, including the forms_tests module.
        blocks = re.findall(r'^ERROR: ([^\n]+)\n(.*?)(?=^={5,}$|\Z)', text, re.M | re.S)
        template_headers = [header for header, body in blocks if 'TemplateDoesNotExist' in body]
        modules = sorted({re.search(r'\(([^.]+)\.', header)[1] for header in template_headers})
        line_count = sum('TemplateDoesNotExist' in line for line in text.splitlines())
        admin_ok = len(re.findall(r'^test_[^\n]+\(admin_views\.tests\.[^\n]+\) \.\.\. ok$', text, re.M))
        assert (line_count, len(template_headers), len(modules), admin_ok) == (323, 160, 10, 207)
        records[stem] = dict(path=path, log_sha256=hashlib.sha256(raw).hexdigest(),
                             TemplateDoesNotExist_lines=line_count,
                             error_tracebacks_with_template_exception=len(template_headers),
                             template_error_modules=modules, template_error_module_count=len(modules),
                             admin_views_tests_ok=admin_ok)
    result = dict(reviewed_commit=COMMIT,
                  scope='Deterministic recount of saved full-control logs only; no execution or causal isolation',
                  records=records)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(records=len(records), template_error_tracebacks_per_record=160,
                         template_error_modules_per_record=10, passed=True)))


if __name__ == '__main__':
    main()
