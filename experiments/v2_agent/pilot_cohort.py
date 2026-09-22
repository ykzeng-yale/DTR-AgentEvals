"""Explicit, disjoint development cohorts; legacy artifacts remain read-only."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COHORTS = {'legacy': 'pilot_20260922', 'yaml-v1': 'pilot_20260922_yaml_v1'}
AMENDMENT = ROOT / 'configs/v2_fixed_backend_development_pilot_yaml_v1_20260922.json'


def cohort_output(name):
    return ROOT / 'results/v2_agent' / COHORTS[name]


def validate_amendment(frame_path, conversion_path):
    spec = json.loads(AMENDMENT.read_text())
    for key, path in (('frame_sha256', frame_path), ('conversion_record_sha256', conversion_path),
                      ('base_spec_sha256', ROOT / spec['base_spec'])):
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != spec[key]:
            raise ValueError('yaml-v1 frozen input differs: ' + key)
    return spec


def validate_effective_receipt(directory, episode, binding, expected_source=None):
    """A declared YAML hash alone cannot establish which configuration was applied."""
    directory = Path(directory)
    if episode.get('configuration_binding') != binding or episode.get('effective_config_file') != 'effective_config.json':
        raise ValueError('missing/conflicting effective configuration identity; reconcile before reuse')
    try:
        receipt = json.loads((directory / 'effective_config.json').read_text())
    except (OSError, ValueError) as exc:
        raise ValueError('effective configuration receipt unavailable; reconcile before reuse') from exc
    digest = receipt.pop('effective_config_sha256', None)
    computed = hashlib.sha256(json.dumps(receipt, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    pins = episode.get('pins', {})
    if not re.fullmatch(r'[0-9a-f]{64}', receipt.get('episode_source_sha256', '')):
        raise ValueError('effective configuration source identity unavailable')
    for section in ('agent', 'model', 'environment'):
        arguments = receipt.get('constructor_arguments', {}).get(section)
        resolved = receipt.get('resolved', {}).get(section)
        if not isinstance(arguments, dict) or not isinstance(resolved, dict) or any(
                resolved.get(k) != v for k, v in arguments.items()):
            raise ValueError('constructor/resolved configuration mismatch: ' + section)
    if (digest != computed or episode.get('effective_config_sha256') != computed or
            receipt.get('configuration_binding') != binding or
            receipt.get('mini_swe_agent') != pins.get('mini_swe_agent') or
            receipt.get('default_yaml_sha256') != pins.get('default_yaml_sha256') or
            receipt.get('episode_source_sha256') != episode.get('episode_source_sha256')):
        raise ValueError('effective configuration receipt digest/provenance mismatch')
    if expected_source is not None and receipt['episode_source_sha256'] != expected_source:
        raise ValueError('episode source differs from frozen cohort source')
    return receipt


def freeze_source_binding(out):
    """Before first execution, freeze the corrected sources; every resume must match."""
    out = Path(out)
    sources = {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
               for name in ('pilot_episode.py', 'pilot_runner.py', 'pilot_cohort.py')}
    payload = dict(cohort='yaml-v1', sources=sources,
                   amendment_sha256=hashlib.sha256(AMENDMENT.read_bytes()).hexdigest())
    path = out / 'cohort_binding.json'
    if path.exists():
        if json.loads(path.read_text()) != payload:
            raise ValueError('corrected cohort source/amendment changed; do not mix bindings')
    else:
        # Read-only all-unstarted reports may precede execution; they are not runtime state.
        existing = list(out.iterdir())
        reports_only = all(p.is_file() and p.name.startswith('report_') and p.suffix == '.json' for p in existing)
        if not reports_only:
            raise ValueError('nonempty corrected cohort lacks source freeze; reconcile before execution')
        for report in existing:
            data = json.loads(report.read_text())
            if data.get('cohort') != 'yaml-v1' or data.get('terminal') != 0 or any(
                    row.get('state') != 'unstarted' for row in data.get('episodes', [])):
                raise ValueError('pre-freeze report indicates existing execution; reconcile before execution')
        with path.open('x') as fh:
            fh.write(json.dumps(payload, indent=1) + '\n')
    return payload
