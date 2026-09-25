"""Fixed two-case, four-constructor probe; 0 official scheduling/evaluation."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from src.q3.attention_rows import construct
from src.q3.construct import Index
from src.q3.pipe_bound import analyze


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if head != a.source or len(head) != 40:
        raise ValueError('fixed source HEAD mismatch')
    dirty = subprocess.check_output(['git', 'diff', 'HEAD', '--', 'src/q3', str(Path(__file__).relative_to(ROOT))], cwd=ROOT)
    if dirty:
        raise ValueError('probe or algorithm has uncommitted changes')
    a.out.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((ROOT / 'docs/a/source-manifest.json').read_text())
    expected = {x['path']: x['sha256'] for x in manifest['files']}
    for name, digest in expected.items():
        if name.startswith('code/') or name == 'data/config.txt':
            if sha(ROOT / 'data/raw/a/official' / name) != digest:
                raise ValueError('frozen official source/config mismatch: ' + name)
    config = (ROOT / 'data/raw/a/official/data/config.txt').read_text()
    delay, = [int(line.split()[1]) for line in config.splitlines()
              if line.split()[:1] == ['cross_core_copy_delay_cycles']]
    counts = Counter()

    def profile(frame, event, arg):
        if event != 'call':
            return
        file = Path(frame.f_code.co_filename)
        name = frame.f_code.co_name
        if file.name in {'schedule_step1.py', 'schedule_step2.py', 'schedule_step3.py'}:
            raise AssertionError('official scheduling call forbidden: ' + name)
        if name in {'_build_scene_b_tasks', 'evaluate_multicore', 'evaluate_singlecore'}:
            raise AssertionError('official Task/evaluation call forbidden: ' + name)
        if name in {'derive_multicore_plan', 'validate_graph'}:
            counts[name] += 1

    report = {'source': head, 'input_hashes': {}, 'official_schedule_calls': 0,
              'e0_calls': 0, 'solver_calls': 0, 'records': [],
              'scope': 'static compute/FIFO/cross-delay model only; no official score'}
    started = time.monotonic()
    sys.setprofile(profile)
    try:
        for case in ('071', '069'):
            source = ROOT / f'data/raw/a/official/data/case_{case}.json'
            digest = sha(source)
            if digest != expected[f'data/case_{case}.json']:
                raise ValueError('input hash mismatch')
            report['input_hashes'][case] = digest
            graph = json.loads(source.read_bytes())
            index = Index(graph)
            for packed in (False, True):
                label = f'{case}-k5-' + ('short-v' if packed else 'control')
                t0 = time.monotonic()
                counts['construct'] += 1
                plan, meta = construct(index, 5, delay, pack_ffn=True,
                                       placement_mode='gap', final_order='placement',
                                       pack_short_vectors=packed)
                construction_wall = time.monotonic() - t0
                counts['pipe_bound'] += 1
                bound = analyze(graph, plan, delay)
                data = json.dumps(plan, sort_keys=True, separators=(',', ':')).encode() + b'\n'
                (a.out / (label + '-plan.json')).write_bytes(data)
                (a.out / (label + '-metadata.json')).write_text(json.dumps(meta, indent=2) + '\n')
                (a.out / (label + '-bound.json')).write_text(json.dumps(bound, indent=2) + '\n')
                report['records'].append({'case': case, 'label': label, 'plan_sha256': hashlib.sha256(data).hexdigest(),
                                          'construction_wall_seconds': construction_wall,
                                          'compute_lower_bound': bound['with_cross_core_delay']['lower_bound_cycles'],
                                          'placement_proxy': meta['placement_proxy_makespan_cycles'],
                                          'regions': meta.get('short_vector_regions'),
                                          'capsules': meta['capsule_count']})
    except BaseException as error:
        report['failure'] = repr(error)
        raise
    finally:
        sys.setprofile(None)
        report['static_helper_calls'] = dict(counts)
        report['diagnostic_wall_seconds'] = time.monotonic() - started
        (a.out / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
