"""Offline tests for the generic experiment and token helpers."""
import base64
import json
import subprocess
import sys
import tempfile
import time
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'scripts/experiment-ledger.py'
INSPECT = ROOT / 'scripts/opaque-token-inspect.py'
BASELINE = ROOT / 'scripts/project-baseline.py'


def run(script, *args):
    result = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True,
                            encoding='utf-8')
    return result.returncode, result.stdout, result.stderr


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.ledger = self.root / 'runs/ledger.jsonl'

    def tearDown(self):
        self.folder.cleanup()

    def record(self, outcome, batch='b1', variant='A', *extra):
        code, _, error = run(LEDGER, 'record', '--ledger', self.ledger, '--batch', batch,
                             '--variant', variant, '--outcome', outcome, *extra)
        self.assertEqual(code, 0, error)

    def gate(self, batch='b1', budget=3, *extra):
        code, out, _ = run(LEDGER, 'gate', '--ledger', self.ledger, '--batch', batch, '--budget', budget, *extra)
        return code, json.loads(out)

    def test_gate_allows_an_empty_batch(self):
        code, result = self.gate()
        self.assertEqual(code, 0)
        self.assertTrue(result['allowed'])

    def test_rejection_stops_only_its_own_batch(self):
        self.record('target_ok')
        self.record('rejected', 'b1', 'B')
        code, result = self.gate()
        self.assertEqual(code, 2)
        self.assertIn('rejected_in_batch', result['reasons'])
        self.assertEqual(self.gate('b2')[0], 0)

    def test_stability_batch_keeps_measuring_until_the_budget_ends(self):
        self.record('rejected', 'stable', 'A')
        self.assertEqual(self.gate('stable', 2, '--allow-rejections')[0], 0)
        self.record('target_ok', 'stable', 'A')
        code, result = self.gate('stable', 2, '--allow-rejections')
        self.assertEqual(code, 2)
        self.assertEqual(result['reasons'], ['budget_exhausted'])

    def test_not_sent_does_not_consume_budget_or_count_as_failure(self):
        self.record('not_sent')
        self.record('not_sent')
        code, result = self.gate(budget=1)
        self.assertEqual(code, 0)
        self.assertEqual(result['sent'], 0)

    def test_budget_counts_transport_errors(self):
        self.record('transport_error')
        code, result = self.gate(budget=1)
        self.assertEqual(code, 2)
        self.assertEqual(result['reasons'], ['budget_exhausted'])

    def test_unknown_attempts_block_the_batch(self):
        self.record('transport_error', 'b1', 'B', '--attempts', 'unknown')
        code, result = self.gate()
        self.assertEqual(code, 2)
        self.assertIn('attempts_unknown', result['reasons'])

    def test_sdk_drift_and_expiring_credentials_block(self):
        code, result = self.gate('b1', 3, '--sdk-local', 'aaa', '--sdk-page', 'bbb',
                                 '--expires-at', int(time.time()) + 5, '--min-remaining', 60)
        self.assertEqual(code, 2)
        self.assertEqual(result['reasons'], ['sdk_mismatch', 'credential_expiring'])
        self.assertEqual(self.gate('b1', 3, '--sdk-local', 'aaa', '--sdk-page', 'aaa')[0], 0)

    def test_summary_keeps_outcome_classes_apart(self):
        for outcome in ('not_sent', 'transport_error', 'rejected'):
            self.record(outcome)
        code, out, _ = run(LEDGER, 'summary', '--ledger', self.ledger)
        self.assertEqual(code, 0)
        batch = json.loads(out)['b1']
        self.assertEqual((batch['not_sent'], batch['transport_error'], batch['rejected']), (1, 1, 1))

    def request(self, name, **change):
        data = {'method': 'GET', 'url': 'https://example.test/api?a=1&b=2',
                'headers': [['Accept', 'json'], ['X-Sign', 'one'], ['Cookie', 's=1; t=2']]}
        data.update(change)
        path = self.root / name
        path.write_text(json.dumps(data), encoding='utf-8')
        return path

    def audit(self, base, candidate, *extra):
        code, out, _ = run(LEDGER, 'audit', '--base', base, '--candidate', candidate, *extra)
        return code, json.loads(out)

    def test_audit_confirms_a_real_single_variable(self):
        headers = [['Accept', 'json'], ['X-Sign', 'two'], ['Cookie', 's=1; t=2']]
        code, result = self.audit(self.request('a.json'), self.request('b.json', headers=headers),
                                  '--must-change', 'x-sign')
        self.assertEqual(code, 0)
        self.assertTrue(result['single_variable_confirmed'])

    def test_audit_catches_a_second_changed_field(self):
        headers = [['Accept', 'json'], ['X-Sign', 'two'], ['X-Nonce', 'r'], ['Cookie', 's=1; t=9']]
        code, result = self.audit(self.request('a.json'), self.request('b.json', headers=headers),
                                  '--allow', 'x-sign')
        self.assertEqual(code, 1)
        self.assertIn('cookie:t', result['unexpected'])
        self.assertIn('header:x-nonce', result['unexpected'])

    def test_audit_catches_header_reordering(self):
        headers = [['X-Sign', 'one'], ['Accept', 'json'], ['Cookie', 's=1; t=2']]
        code, result = self.audit(self.request('a.json'), self.request('b.json', headers=headers))
        self.assertEqual(code, 1)
        self.assertTrue(result['order_changed'])

    def test_audit_requires_the_declared_change(self):
        code, result = self.audit(self.request('a.json'), self.request('b.json'), '--must-change', 'x-sign')
        self.assertEqual(code, 1)
        self.assertEqual(result['missing_change'], ['x-sign'])

    def test_audit_output_never_contains_raw_values(self):
        headers = [['Accept', 'json'], ['X-Sign', 'secret-value'], ['Cookie', 's=1; t=2']]
        _, out, _ = run(LEDGER, 'audit', '--base', self.request('a.json'),
                        '--candidate', self.request('b.json', headers=headers), '--allow', 'x-sign')
        self.assertNotIn('secret-value', out)


class TokenTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)

    def tearDown(self):
        self.folder.cleanup()

    @staticmethod
    def build(index, key):
        magic = bytes.fromhex('c0ffee01')
        payload = bytes((index * 37 + position * 11) % 251 for position in range(40 + index % 3)) + b'TAILMARK'
        body = magic + len(payload).to_bytes(2, 'little') + payload
        data = zlib.crc32(body).to_bytes(4, 'little') + body
        return base64.b64encode(bytes(value ^ key for value in data)).decode()

    def samples(self, keys=(0x11, 0x5A, 0xC3, 0x07, 0x99)):
        path = self.root / 'samples.txt'
        path.write_text('\n'.join(self.build(index, key) for index, key in enumerate(keys)), encoding='utf-8')
        return path

    def inspect(self, *args):
        code, out, error = run(INSPECT, *args)
        self.assertEqual(code, 0, error)
        return json.loads(out)

    def test_text_shape_without_decoding(self):
        report = self.inspect(self.samples())
        self.assertEqual(report['text']['count'], 5)
        self.assertEqual(report['text']['guess'], 'base64-or-custom-alphabet')
        self.assertNotIn('bytes', report)

    def test_xor_alignment_recovers_masked_structure(self):
        report = self.inspect(self.samples(), '--encoding', 'base64', '--xor-align', '--magic', 'c0ffee01',
                              '--magic-offset', '4')
        self.assertIn(0x11, report['xor']['reference_key_candidates'])
        self.assertIn('c0ffee01', report['head_stable_runs'][0]['hex'])
        self.assertEqual(report['tail_stable_runs'][-1]['hex'][-16:], b'TAILMARK'.hex())

    def test_checksum_self_check_finds_the_key_without_magic(self):
        report = self.inspect(self.samples(), '--encoding', 'base64', '--xor-align', '--checksum', 'crc32')
        self.assertIn({'key': 0x11, 'endian': 'little'}, report['xor']['checksum_matches'])

    def test_length_field_is_detected_after_alignment(self):
        report = self.inspect(self.samples(), '--encoding', 'base64', '--xor-align', '--magic', 'c0ffee01',
                              '--magic-offset', '4')
        self.assertIn({'offset': 8, 'width': 2, 'endian': 'little', 'delta': 10}, report['length_field_candidates'])

    def test_custom_alphabet_round_trip(self):
        standard = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
        custom = standard[::-1]
        table = str.maketrans(standard, custom)
        path = self.root / 'custom.txt'
        tokens = [base64.b64encode(b'HEAD' + bytes([index]) * 8).decode().rstrip('=').translate(table)
                  for index in range(3)]
        path.write_text('\n'.join(tokens), encoding='utf-8')
        report = self.inspect(path, '--encoding', 'custom', '--alphabet', custom)
        self.assertEqual(report['head_stable_runs'][0]['hex'], b'HEAD'.hex())

    def test_json_field_input(self):
        path = self.root / 'rows.jsonl'
        path.write_text('\n'.join(json.dumps({'h': {'sig': 'aabb'}}) for _ in range(2)), encoding='utf-8')
        self.assertEqual(self.inspect(path, '--field', 'h.sig')['text']['guess'], 'hex')

    def test_custom_encoding_requires_an_alphabet(self):
        code, _, _ = run(INSPECT, self.samples(), '--encoding', 'custom')
        self.assertNotEqual(code, 0)


class BaselineIdentityTests(unittest.TestCase):
    def test_identities_survive_and_versions_default_to_the_skill(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'sdk.js').write_text('v1')
            code, _, error = run(BASELINE, 'create', '--root', folder, '--files', 'sdk.js',
                                 '--identity', 'sdk_public=1.2.3', '--identity', 'impl_revision=v2')
            self.assertEqual(code, 0, error)
            data = json.loads((root / 'project-manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(data['identities'], {'sdk_public': '1.2.3', 'impl_revision': 'v2'})
            self.assertNotEqual(data['versions']['skill'], 'unknown')
            code, out, _ = run(BASELINE, 'check', '--root', folder)
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out)['identities']['sdk_public'], '1.2.3')

    def test_malformed_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'sdk.js').write_text('v1')
            code, _, _ = run(BASELINE, 'create', '--root', folder, '--files', 'sdk.js', '--identity', 'broken')
            self.assertNotEqual(code, 0)


if __name__ == '__main__':
    unittest.main()
