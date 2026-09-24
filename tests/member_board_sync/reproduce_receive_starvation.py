"""Exercise exact reviewed receive_submissions method without network/ledger writes."""
import ast
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--engine', type=Path, required=True)
args = parser.parse_args()
source = args.engine
root = Path(__file__).parent
if hashlib.sha256(source.read_bytes()).hexdigest() != '484d22eed2f54449301ac4a5f29fed9d819a18917e69554ea0f7a74ac302b82b':
    raise ValueError('This reproduction is pinned to PR112 commit 577a9a61 engine.py')
tree = ast.parse(source.read_text(encoding='utf-8'))
engine = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Engine')
method = next(n for n in engine.body if isinstance(n, ast.FunctionDef) and n.name == 'receive_submissions')
canonical = lambda x: json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
digest = lambda b: hashlib.sha256(b).hexdigest()

class Clock:
    value = 0
    def monotonic(self): return self.value
clock = Clock()
ns = dict(json=json, Path=Path, time=clock, canonical=canonical, digest=digest)
exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), ns)

entries = {}
submissions = []
for n in range(64):
    body = {'actor': 'member', 'nonce': n}
    identity = digest(canonical(body))
    path = 'submissions/member/' + identity + '.json'
    entries[path] = canonical({'issuer': 'member', 'payload': body})
    entries['receipts/member/' + identity + '.json'] = canonical({
        'issuer': 'captain', 'payload': {'id': identity, 'actor': 'member', 'state': 'accepted'}})
    submissions.append(path)
submissions.sort()
pending = submissions[-1]
del entries[pending.replace('submissions/', 'receipts/')]

class Remote:
    repository = 'test/test'
    reads = []
    def tree(self, head): return entries
    def read(self, head, path):
        self.reads.append(path)
        return entries[path]
remote = Remote()
def verify(envelope, *args, **kwargs):
    # Deterministic 2-second combined I/O/verification cost per envelope.
    clock.value += 2
    return envelope['payload']
subject = SimpleNamespace(config={'central': {'inbox': str(root / 'unused-inbox')}},
                          remote=remote, verify=verify, errors=[])
cycles = []
for _ in range(3):
    before = len(remote.reads)
    ns['receive_submissions'](subject, 'a' * 40)
    cycles.append(remote.reads[before:])
result = dict(source_sha256=digest(source.read_bytes()), completed_prefix=63, cycles=3,
              simulated_seconds_per_envelope=2, pending_submission=pending,
              pending_ever_read=pending in remote.reads,
              unique_submissions_read=len({x for x in remote.reads if x.startswith('submissions/')}),
              same_prefix_each_cycle=cycles[0] == cycles[1] == cycles[2], errors=subject.errors)
print(json.dumps(result, indent=2))
assert result['pending_ever_read'] is False and result['same_prefix_each_cycle'], result
