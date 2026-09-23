"""Read-only checks of published projections; never runtime admission evidence.

A worker-authored manifest binds the bytes available to a reader. Matching it
does not authenticate the absent raw bytes or prove the stated transformation.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical_sha256(payload):
    return sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode())


def digest(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ValueError('missing/invalid publication digest: ' + label)
    return value


class PublicationManifest:
    """Validate all listed published bytes, then links for a selected receipt."""

    def __init__(self, path, archive):
        path = Path(path)
        self.root = Path(archive).resolve()
        if path.resolve().parent != self.root:
            raise ValueError('publication manifest must be in the archive root')
        raw = path.read_bytes()
        manifest = json.loads(raw)
        if not isinstance(manifest, dict) or not isinstance(manifest.get('files'), list) or not manifest['files']:
            raise ValueError('publication manifest requires a nonempty files list')
        self.entries, self.receipts = {}, {}
        targets = set()
        for entry in manifest['files']:
            if not isinstance(entry, dict):
                raise ValueError('publication manifest entry must be an object')
            name = entry.get('file')
            if not isinstance(name, str) or not name or '\\' in name:
                raise ValueError('invalid publication manifest-relative path')
            relative = PurePosixPath(name)
            if relative.is_absolute() or '..' in relative.parts or relative.as_posix() != name or name == '.':
                raise ValueError('invalid publication manifest-relative path: ' + name)
            target = (self.root / name).resolve()
            if not target.is_relative_to(self.root) or target == self.root:
                raise ValueError('publication path escapes archive: ' + name)
            if name in self.entries or target in targets:
                raise ValueError('duplicate publication manifest path: ' + name)
            targets.add(target)
            published = target.read_bytes()
            if sha256(published) != digest(entry.get('published_sha256'), name):
                raise ValueError('published byte hash mismatch: ' + name)
            digest(entry.get('raw_sha256'), name + ' reported raw hash')
            self.entries[name] = entry
            if relative.name == 'effective_config.json':
                receipt = json.loads(published)
                if not isinstance(receipt, dict):
                    raise ValueError('published effective configuration must be an object: ' + name)
                payload = {k: v for k, v in receipt.items() if k != 'effective_config_sha256'}
                if canonical_sha256(payload) != digest(entry.get('published_payload_canonical_sha256'), name):
                    raise ValueError('published canonical payload hash mismatch: ' + name)
                if receipt.get('effective_config_sha256') != digest(entry.get('recorded_effective_config_sha256'), name):
                    raise ValueError('published receipt/manifest recorded digest mismatch: ' + name)
                self.receipts[name] = receipt
        self.metadata = dict(
            mode='publication_manifest', manifest_file=path.name, manifest_sha256=sha256(raw),
            listed_published_files_verified=len(self.entries),
            published_config_payloads_verified=len(self.receipts),
            raw_execution_binding='reported_unverified', raw_bytes_independently_verified=False,
            sanitization_transform_independently_verified=False,
            scope='Published byte and canonical-payload matches against the supplied manifest only; '
                  'manifest authenticity, raw bytes, and execution identity are not established.')

    def configuration_provenance(self, directory, episode, binding, expected_source):
        """Check published links without changing or accepting the raw receipt."""
        if not binding or expected_source is None:
            raise ValueError('publication projection requires expected cohort binding and frozen episode source')
        digest(expected_source, 'expected episode source')
        directory = Path(directory).resolve()
        if directory.parent != self.root:
            raise ValueError('published episode must be a direct child of archive root')
        name = directory.name + '/effective_config.json'
        if name not in self.receipts:
            raise ValueError('effective configuration is missing from publication manifest: ' + name)
        entry, receipt = self.entries[name], self.receipts[name]
        pins = episode.get('pins') or {}
        if (episode.get('run_id') != directory.name or episode.get('effective_config_file') != 'effective_config.json' or
                episode.get('configuration_binding') != binding or receipt.get('configuration_binding') != binding or
                episode.get('effective_config_sha256') != entry['recorded_effective_config_sha256'] or
                receipt.get('episode_source_sha256') != expected_source or
                episode.get('episode_source_sha256') != expected_source or
                not receipt.get('mini_swe_agent') or receipt.get('mini_swe_agent') != pins.get('mini_swe_agent') or
                not receipt.get('default_yaml_sha256') or receipt.get('default_yaml_sha256') != pins.get('default_yaml_sha256')):
            raise ValueError('published configuration episode digest/source/binding link mismatch')
        for section in ('agent', 'model', 'environment'):
            arguments = receipt.get('constructor_arguments', {}).get(section)
            resolved = receipt.get('resolved', {}).get(section)
            if not isinstance(arguments, dict) or not isinstance(resolved, dict) or any(
                    resolved.get(k) != v for k, v in arguments.items()):
                raise ValueError('published constructor/resolved configuration mismatch: ' + section)
        return dict(status='published_projection_verified',
                    published_file=name, published_sha256=entry['published_sha256'],
                    published_payload_canonical_sha256=entry['published_payload_canonical_sha256'],
                    reported_raw_file_sha256=entry['raw_sha256'],
                    reported_raw_payload_sha256=entry['recorded_effective_config_sha256'],
                    raw_execution_binding='reported_unverified', raw_bytes_independently_verified=False,
                    sanitization_transform_independently_verified=False,
                    reason='Published projection and recorded provenance links match; raw execution binding remains reported and unverified.')
