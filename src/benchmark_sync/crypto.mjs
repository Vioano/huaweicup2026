import { createPrivateKey, createPublicKey, generateKeyPairSync, sign, verify } from 'node:crypto';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

const input = JSON.parse(readFileSync(0, 'utf8'));
let output;
if (input.operation === 'generate') {
  const pair = generateKeyPairSync('ed25519');
  const privatePem = pair.privateKey.export({ type: 'pkcs8', format: 'pem' });
  mkdirSync(dirname(input.privateKeyPath), { recursive: true, mode: 0o700 });
  writeFileSync(input.privateKeyPath, privatePem, { mode: 0o600, flag: 'wx' });
  output = { public_key: pair.publicKey.export({ type: 'spki', format: 'pem' }) };
} else if (input.operation === 'public') {
  const key = createPrivateKey(readFileSync(input.privateKeyPath));
  output = { public_key: createPublicKey(key).export({ type: 'spki', format: 'pem' }) };
} else if (input.operation === 'sign') {
  const key = createPrivateKey(readFileSync(input.privateKeyPath));
  if (key.asymmetricKeyType !== 'ed25519') throw new Error('Ed25519 key required');
  output = { signature: sign(null, Buffer.from(input.message, 'base64'), key).toString('base64') };
} else if (input.operation === 'verify') {
  const key = createPublicKey(input.public_key);
  if (key.asymmetricKeyType !== 'ed25519') throw new Error('Ed25519 key required');
  output = { valid: verify(null, Buffer.from(input.message, 'base64'), key, Buffer.from(input.signature, 'base64')) };
} else {
  throw new Error('Unsupported cryptographic operation');
}
process.stdout.write(JSON.stringify(output));
