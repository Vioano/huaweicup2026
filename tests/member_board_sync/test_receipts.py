"""Do not accept an otherwise valid receipt for another actor or submission."""
import base64
import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from member_board_sync.receipts import check_receipt
from member_board_sync.audit import canonical, digest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

class ReceiptTests(unittest.TestCase):
    def test_signature_and_submission_identity_are_both_required(self):
        key=Ed25519PrivateKey.generate()
        pem=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        payload=dict(id='a'*64,actor='member',state='accepted',receipt={'added':0})
        def signed(body,domain='receipt'):
            env=dict(schema_version=1,project='huaweicup2026-benchmark-board',domain=domain,
                     issuer='nikolastarx',key_sha256=digest(pem),payload=body)
            env['signature']=base64.b64encode(key.sign(canonical(env))).decode()
            return env
        env=signed(payload)
        self.assertEqual(check_receipt(env,pem,digest(pem),'a'*64,'member'),payload)
        for changed in (dict(payload,id='b'*64),dict(payload,actor='someone-else'),dict(payload,state='pending')):
            with self.assertRaises(ValueError):check_receipt(signed(changed),pem,digest(pem),'a'*64,'member')
        with self.assertRaises(ValueError):check_receipt(signed(payload,'snapshot'),pem,digest(pem),'a'*64,'member')
        modified=copy.deepcopy(env);modified['payload']['receipt']['added']=1
        with self.assertRaises(InvalidSignature):check_receipt(modified,pem,digest(pem),'a'*64,'member')

if __name__=='__main__':unittest.main()
