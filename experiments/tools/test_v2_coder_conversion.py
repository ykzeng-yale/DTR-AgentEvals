"""Pinned input verification only: no network, converter, quantizer, model or server execution."""
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'v2_agent/convert_pinned_coder.py'
SPEC = importlib.util.spec_from_file_location('coder_conversion', MODULE)
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)


def blob_oid(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()


class PinnedInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.raw = b'{"value":"original"}\n'
        self.file = self.root / 'config.json'
        self.file.write_bytes(self.raw)

    def entry(self, lfs=False):
        entry = dict(type='file', path='config.json', size=len(self.raw), oid=blob_oid(self.raw))
        if lfs:
            entry['lfs'] = dict(oid=hashlib.sha256(self.raw).hexdigest())
        return entry

    def test_correct_ordinary_and_lfs_inputs_pass(self):
        ordinary = C.verify_input(self.file, self.entry())
        self.assertEqual(ordinary['hub_git_blob_sha1'], blob_oid(self.raw))
        self.assertTrue(ordinary['hub_git_blob_sha1_match'])
        self.assertIsNone(ordinary['hub_lfs_sha256_match'])
        lfs = C.verify_input(self.file, self.entry(lfs=True))
        self.assertTrue(lfs['hub_lfs_sha256_match'])
        for record in (ordinary, lfs):
            self.assertTrue(record['hub_size_match'])
            self.assertEqual(record['sha256'], hashlib.sha256(self.raw).hexdigest())

    def test_missing_or_wrong_expected_oid_refuses_both_storage_types(self):
        for lfs in (False, True):
            for oid in (None, '0' * (64 if lfs else 40)):
                with self.subTest(lfs=lfs, oid=oid):
                    entry = self.entry(lfs)
                    target = entry['lfs'] if lfs else entry
                    if oid is None:
                        del target['oid']
                    else:
                        target['oid'] = oid
                    with self.assertRaises(SystemExit):
                        C.verify_input(self.file, entry)

    def test_missing_or_wrong_size_refuses_both_storage_types(self):
        for lfs in (False, True):
            for size in (None, len(self.raw) + 1):
                with self.subTest(lfs=lfs, size=size):
                    entry = self.entry(lfs)
                    if size is None:
                        del entry['size']
                    else:
                        entry['size'] = size
                    with self.assertRaisesRegex(SystemExit, 'size mismatch'):
                        C.verify_input(self.file, entry)

    def test_corrupted_same_length_config_refuses_before_conversion(self):
        llama = self.root / 'llama'
        (llama / 'build/bin').mkdir(parents=True)
        (llama / 'build/bin/llama-quantize').write_text('mock binary')
        (llama / 'convert_hf_to_gguf.py').write_text('mock converter')
        role, repo, rev = C.PINS[0]
        hf = self.root / 'hf'
        src = hf / (repo.split('/')[1] + '@' + rev[:7])
        src.mkdir(parents=True)
        altered = self.raw.replace(b'original', b'modified')
        self.assertEqual(len(altered), len(self.raw))
        (src / 'config.json').write_bytes(altered)
        changes = dict(ROOT=self.root, LLAMA=llama, HF=hf, OUTD=self.root / 'out', REC=self.root / 'record.json')
        responses = [SimpleNamespace(stdout=C.LLAMA_COMMIT), SimpleNamespace(stdout=''), SimpleNamespace(stdout='mock versions')]
        with patch.multiple(C, **changes), patch.object(C, 'hub_tree', return_value=[self.entry()]), \
                patch.object(C.subprocess, 'run', side_effect=responses), patch.object(C, 'run') as converter:
            with self.assertRaisesRegex(SystemExit, 'Git blob hash mismatch'):
                C.main()
            converter.assert_not_called()
            self.assertFalse(C.REC.exists())


if __name__ == '__main__':
    unittest.main()
