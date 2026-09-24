"""Domain-separated Ed25519 envelopes; keys never enter repository or logs."""
from __future__ import annotations

import base64
from pathlib import Path
import re
import shutil
import subprocess
import json

from .snapshot import canonical, digest

PROJECT = "huaweicup2026-benchmark-board"
DOMAINS = {"snapshot", "release", "submission", "receipt", "members"}


class Signatures:
    def __init__(self, node=None):
        self.node = node or shutil.which("node")
        if not self.node:
            raise RuntimeError("Node.js is required for built-in Ed25519 verification; no npm dependencies")
        self.helper = Path(__file__).with_name("crypto.mjs")

    def _call(self, request):
        result = subprocess.run([self.node, str(self.helper)], input=canonical(request),
                                capture_output=True, timeout=20)
        if result.returncode:
            # Do not forward arbitrary OpenSSL/Node output or private filesystem paths.
            raise ValueError("Local Ed25519 operation failed; verify runtime and key configuration")
        return json.loads(result.stdout)

    def public_key(self, private_key):
        return self._call({"operation": "public", "privateKeyPath": str(private_key)})["public_key"]

    def generate(self, private_key):
        return self._call({"operation": "generate", "privateKeyPath": str(private_key)})["public_key"]

    def sign(self, domain, issuer, payload, private_key):
        if domain not in DOMAINS or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,38}", issuer):
            raise ValueError("Invalid signature domain or issuer")
        public = self.public_key(private_key)
        envelope = {"schema_version": 1, "project": PROJECT, "domain": domain,
                    "issuer": issuer, "key_sha256": digest(public.encode()), "payload": payload}
        envelope["signature"] = self._call({"operation": "sign", "privateKeyPath": str(private_key),
                                            "message": base64.b64encode(canonical(envelope)).decode()})["signature"]
        return envelope

    def verify(self, envelope, *, domain, trusted_keys):
        if not isinstance(envelope, dict) or set(envelope) != {"schema_version", "project", "domain", "issuer", "key_sha256", "payload", "signature"}:
            raise ValueError("Invalid signed envelope")
        if envelope["schema_version"] != 1 or envelope["project"] != PROJECT or envelope["domain"] != domain:
            raise ValueError("Signature domain mismatch")
        public = trusted_keys.get(envelope["issuer"])
        if not public or len(public) > 4096 or digest(public.encode()) != envelope["key_sha256"]:
            raise ValueError("Unknown publisher or changed public key")
        message = {k: v for k, v in envelope.items() if k != "signature"}
        valid = self._call({"operation": "verify", "public_key": public, "signature": envelope["signature"],
                            "message": base64.b64encode(canonical(message)).decode()})["valid"]
        if not valid:
            raise ValueError("Envelope signature invalid")
        return envelope["payload"]
