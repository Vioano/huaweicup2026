"""Adversarial acceptance-oracle tests; no running website or ledger writes."""
import base64
import copy
import gzip
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from member_board_sync.audit import canonical, digest, expected_cells, verify_envelope, verify_snapshot
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def row(attempt, revision=1, cycles=10, eligible=True, status='ok', algorithm='a'):
    return dict(id=digest(f'{attempt}/{revision}'.encode()), attempt_id=attempt, revision=revision,
                algorithm_id=algorithm, run_id='r', problem='P1', case_id='001', cores=1,
                status=status, eligible=eligible, metrics={'makespan_cycles': cycles},
                evaluator={'route': 'E0'}, identity=dict(official_sha256='o', graph_sha256='g', config_sha256='c'))


def payload(records):
    return dict(records=records, manifest={'official_code_hash': 'o', 'files': [
        {'path': 'data/case_001.json', 'sha256': 'g'}, {'path': 'data/config.txt', 'sha256': 'c'}]})


class SelectionTests(unittest.TestCase):
    def test_withdrawn_revision_never_revives_old_winner(self):
        records = [row('withdraw', cycles=1), row('other', cycles=20),
                   row('withdraw', 2, cycles=None, eligible=False, status='withdrawn')]
        cell = expected_cells(payload(records))[0]
        self.assertEqual(cell['best']['attempt_id'], 'other')
        self.assertEqual(cell['attempts'], 2)

    def test_preview_cannot_replace_admitted_with_faster_report(self):
        rows = [row('admitted', cycles=20), row('report', cycles=1, eligible=False)]
        self.assertEqual(expected_cells(payload(rows), preview=True)[0]['best']['attempt_id'], 'admitted')

    def test_filter_applies_after_revision_selection(self):
        rows = [row('x', algorithm='old'), row('x', 2, algorithm='new')]
        self.assertIsNone(expected_cells(payload(rows), algorithm='old')[0]['best'])

    def test_evidence_identity_gates_report_preview(self):
        report = row('report', eligible=False)
        report['identity']['graph_sha256'] = 'wrong'
        self.assertIsNone(expected_cells(payload([report]), preview=True)[0]['best'])

    def test_ties_and_empty_cells_are_deterministic(self):
        rows = [row('x'), row('y')]
        cells = expected_cells(payload(rows))
        self.assertEqual(cells[0]['best']['id'], min(r['id'] for r in rows))
        self.assertEqual(len(cells), 1500)
        self.assertEqual(cells[-1]['status'], 'not_run')


class IntegrityTests(unittest.TestCase):
    def test_signature_tampering_and_wrong_signer_rejected(self):
        key = Ed25519PrivateKey.generate()
        pem = key.public_key().public_bytes(serialization.Encoding.PEM,
                                            serialization.PublicFormat.SubjectPublicKeyInfo)
        fingerprint = digest(pem)
        envelope = dict(schema_version=1, project='huaweicup2026-benchmark-board',
                        domain='snapshot', issuer='nikolastarx', key_sha256=fingerprint,
                        payload={'manifest': {'sequence': 1}})
        envelope['signature'] = base64.b64encode(key.sign(canonical(envelope))).decode()
        self.assertEqual(verify_envelope(envelope, pem, fingerprint), {'sequence': 1})
        modified = copy.deepcopy(envelope)
        modified['payload']['manifest']['sequence'] = 2
        with self.assertRaises(InvalidSignature):
            verify_envelope(modified, pem, fingerprint)
        with self.assertRaises(ValueError):
            verify_envelope(envelope, pem, '0' * 64)

    def test_wrong_signed_domain_rejected_even_with_valid_signature(self):
        key = Ed25519PrivateKey.generate()
        pem = key.public_key().public_bytes(serialization.Encoding.PEM,
                                            serialization.PublicFormat.SubjectPublicKeyInfo)
        env = dict(schema_version=1, project='huaweicup2026-benchmark-board', domain='software',
                   issuer='nikolastarx', key_sha256=digest(pem), payload={'manifest': {}})
        env['signature'] = base64.b64encode(key.sign(canonical(env))).decode()
        with self.assertRaises(ValueError):
            verify_envelope(env, pem, digest(pem))

    def test_compressed_corruption_fails_before_json_parsing(self):
        data = gzip.compress(b'{}', mtime=0)
        manifest = dict(payload_size=len(data), payload_sha256=digest(data), decoded_size=2)
        with self.assertRaisesRegex(ValueError, 'compressed digest mismatch'):
            verify_snapshot(manifest, data[:-1] + bytes([data[-1] ^ 1]))


if __name__ == '__main__':
    unittest.main()
