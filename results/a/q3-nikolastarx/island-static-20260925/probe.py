"""Three seen attention graphs: fresh construction only, no solver/E0 invocation."""
import collections
import hashlib
import json
from pathlib import Path
import subprocess
import time
import zipfile
from src.q3.attention_rows import construct as attention
from src.q3.construct import Index
from src.q3.island_repair import construct as repair

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def dump(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')

records = []
with zipfile.ZipFile(ROOT / 'data/raw/a/official-cases.zip') as archive:
    for case in ('066', '082', '071'):
        names = [n for n in archive.namelist() if n.endswith('/case_' + case + '.json') and not n.startswith('__MACOSX/')]
        if len(names) != 1:
            raise ValueError(names)
        raw = archive.read(names[0])
        index = Index(json.loads(raw))
        anchor, anchor_metadata = attention(index, 5, 500, pack_ffn=True, placement_mode='gap', final_order='placement')
        start = time.perf_counter()
        candidate, metadata = repair(index, anchor, 500)
        seconds = time.perf_counter() - start
        folder = OUT / case
        folder.mkdir()
        dump(folder / 'anchor.json', anchor)
        dump(folder / 'candidate.json', candidate)
        dump(folder / 'repair.json', metadata)
        record = {
            'case': case, 'cores': 5, 'graph_sha256': sha(raw),
            'anchor': 'fresh gap attention placement witness, not necessarily official incumbent',
            'before_compute_bound': metadata['initial_compute_bound'],
            'after_compute_bound': metadata['candidate_compute_bound'],
            'returned_candidate': metadata['returned_candidate'],
            'block_status_counts': dict(collections.Counter(b['status'] for b in metadata['blocks'])),
            'trials': metadata['local_trials'], 'repair_only_seconds': seconds,
            'timing_scope': 'constructor call only; excludes anchor construction, I/O and official evaluation; not solver time',
            'official_evaluations': 0,
            'files': {p.name: sha(p.read_bytes()) for p in sorted(folder.iterdir())}}
        records.append(record)
        print(json.dumps(record))
report = {
    'schema': 'q3-original-island-static-v1',
    'constructor_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'probe_sha256': sha(Path(__file__).read_bytes()),
    'records': records, 'official_evaluations': 0, 'complete_solver_calls': 0,
    'generalization_evidence': False,
    'limitations': 'Seen real graphs but compute relaxation only. No E0 acceptance, memory proof or actual solver speed claim.'}
dump(OUT / 'summary.json', report)
