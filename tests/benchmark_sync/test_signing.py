from pathlib import Path
import tempfile
import unittest
from src.benchmark_sync.signing import Signatures

class SigningTests(unittest.TestCase):
    def test_domain_identity_and_content_are_authenticated(self):
        with tempfile.TemporaryDirectory() as folder:
            key=Path(folder)/'private.pem'; s=Signatures(); public=s.generate(key)
            before=key.read_bytes(); envelope=s.sign('snapshot','leader',{'sequence':5},key)
            self.assertEqual(s.verify(envelope,domain='snapshot',trusted_keys={'leader':public}),{'sequence':5})
            for changed,domain,trust in [(dict(envelope,payload={'sequence':6}),'snapshot',{'leader':public}),
                                          (envelope,'receipt',{'leader':public}),
                                          (envelope,'snapshot',{}),
                                          (dict(envelope,issuer='member'),'snapshot',{'leader':public})]:
                with self.assertRaises(ValueError): s.verify(changed,domain=domain,trusted_keys=trust)
            with self.assertRaises(ValueError): s.generate(key)
            self.assertEqual(key.read_bytes(),before)
