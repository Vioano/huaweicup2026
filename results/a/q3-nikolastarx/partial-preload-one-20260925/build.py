"""Freeze one structurally selected partial preload; no official imports/calls."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
STATIC = OUT.parent / 'pipeline-prefix-static-20260925'
COMPILER = OUT.parent / 'partial-bucket-compile-20260925/compile.py'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    summary = read(STATIC / 'summary.json')
    for name, sha in summary['artifacts'].items():
        if digest(STATIC / name) != sha:
            raise ValueError('saved source identity differs')
    plan = read(STATIC / 'case_044_multicore_res.json')
    snapshots = read(STATIC / 'snapshots.json.gz')
    cert = read(STATIC / 'certificate.json')
    spec = importlib.util.spec_from_file_location('partial_compiler', COMPILER)
    compiler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compiler)
    mapping = {int(u): sg for u, sg in plan['node_to_subgraph'].items()}
    bandwidth = int(next(line.split()[1] for line in
                        (ROOT / 'data/raw/a/official/data/config.txt').read_text().splitlines()
                        if line.startswith('bandwidth ')))
    if bandwidth <= 0:
        raise ValueError('positive frozen DDR bandwidth required')
    # Structural rule: among downstream stages with >=2 cold prefix inputs,
    # choose greatest prefix exclusive DDR work (tie: lower core index).
    # Split at the earliest compute boundary that retains all but the final
    # prefix input. Its remaining read may overlap the head's computation.
    # This is one falsifiable heuristic, not official optimality or a search.
    eligible = []
    for c in range(1, len(plan['core_schedules'])):
        saved = snapshots['candidate'][str(c)]
        prefix = cert['cores'][c]['prefix_copy_ids']
        if len(prefix) < 2:
            continue
        first = saved['subgraph_order'][0]
        pilot = [u for u in saved['pre_step2_word'] if mapping.get(u) == first]
        pos = {u: i for i, u in enumerate(pilot)}
        ops, tensors, _, consumers, inputs, outputs, _ = compiler.ports(saved['graph'])
        uses = [min(pos[v] for t in outputs[u] for v in consumers[t] if v in pos)
                for u in prefix]
        if uses != sorted(uses) or uses[-1] == uses[-2]:
            continue
        # Repeated/multiple equal final consumers cannot expose this split.
        h = next((i for i in range(1, len(pilot))
                  if sum(p < i for p in uses) == len(prefix) - 1), None)
        if h is None:
            continue
        sizes = [sum(tensors[t]['size'] for t in inputs[u]) for u in prefix]
        eligible.append({'core': c, 'head_count': h, 'input_sizes': sizes,
                         'first_use_positions': uses,
                         'prefix_nominal_cycles': sum(max(1, (s + bandwidth - 1) // bandwidth)
                                                      for s in sizes)})
    selected = max(eligible, key=lambda r: (r['prefix_nominal_cycles'], -r['core']))
    candidate, words, facts = compiler.compile_split(
        plan, snapshots, cert, selected['core'], selected['head_count'])
    prefixes = {str(r['core']): list(r['prefix_copy_ids']) for r in cert['cores']}
    prefixes[str(selected['core'])] = prefixes[str(selected['core'])][:-1]
    facts['selection'] = {'rule': 'max_prefix_nominal_work_then_one_last_read_overlap',
                          'eligible_stages': eligible, 'selected': selected,
                          'compiler_sha256': digest(COMPILER),
                          'scope': 'saved same-core Task skeleton; no official compile/score'}
    for name, value in [('case_044_multicore_res.json', candidate),
                        ('predicted-words.json', words), ('expected-prefixes.json', prefixes),
                        ('facts.json', facts)]:
        write(name, value)
    names = ['case_044_multicore_res.json', 'predicted-words.json',
             'expected-prefixes.json', 'facts.json']
    refs = [STATIC / n for n in ['case_044_multicore_res.json', 'snapshots.json.gz',
                                 'certificate.json', 'summary.json']]
    manifest = {'schema': 'q3-partial-preload-v1', 'case_id': '044', 'cores': 5,
                'changed_core': selected['core'], 'head_count': selected['head_count'],
                'budget': {'workers': 1, 'max_prepare': 1, 'max_P3': 1, 'max_P2': 2,
                           'max_E0': 3, 'per_phase_seconds': 90, 'total_seconds': 600,
                           'memory_limit_bytes': 536870912, 'retries': 0},
                'artifacts': {n: digest(OUT / n) for n in names},
                'references': {p.relative_to(ROOT).as_posix(): digest(p) for p in refs},
                'source_input_sha256': {p: h for p, h in summary['source_input_sha256'].items()
                                        if p.startswith('data/')}}
    write('manifest.json', manifest)
    print(json.dumps({'selected': selected, 'manifest_sha256': digest(OUT / 'manifest.json'),
                      'official_calls': 0, 'global_pre_step2': facts['global_pre_step2']}))


if __name__ == '__main__':
    main()
