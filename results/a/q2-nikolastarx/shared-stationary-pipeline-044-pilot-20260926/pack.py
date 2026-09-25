"""Hash-only job-major pipeline capsule packer. Never runs a solver."""
from __future__ import annotations

import hashlib
import json
import argparse
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
SOLVER_SOURCE = 'cbad84f726fecd997eeb76f3735ce5a2269225cb'
OLD = 'c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f'
GRAPH = '9abd4468a4be365e384de47431ac914ee44fd6e7b6221dffc584561f388cd57e'
CONFIG = 'dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9'
SOURCE = ('direct.py', 'dag_direct.py', 'shared_input_wave.py',
          'shared_stationary_wave.py', 'shared_stationary_pipeline.py',
          'evaluate_feedback.py')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--official-data-root', type=Path,
                        default=ROOT / 'data/raw/a/official/data',
                        help='directory containing frozen case_044.json and config.txt')
    args = parser.parse_args()
    subprocess.check_call(['git', 'merge-base', '--is-ancestor', SOLVER_SOURCE, 'HEAD'], cwd=ROOT)
    summary = json.loads((ROOT / 'results/a/q2-nikolastarx/hypergap-full500-audit-20260925/completed-summary.json').read_bytes())
    assert summary['solver_commit'] == OLD
    old_rows = [r for r in summary['rows'] if r['case'] == '044' and r['cores'] == 5]
    assert len(old_rows) == 1
    old = old_rows[0]
    assert (old['status'], old['official']['makespan'], old['official']['movement']['added_copy_bytes']) == ('accepted', 43795, 930400)
    assert (old['graph_sha256'], old['config_sha256']) == (GRAPH, CONFIG)
    official_manifest = json.loads((ROOT / 'docs/a/source-manifest.json').read_bytes())
    official_hashes = {r['path']: r['sha256'] for r in official_manifest['files']}
    files = {}
    for name in SOURCE:
        rel = 'src/q2_nikolastarx/' + name
        raw = (ROOT / rel).read_bytes()
        if raw != git('show', f'{SOLVER_SOURCE}:{rel}'):
            raise ValueError('dirty or wrong solver source: ' + rel)
        files[rel] = raw
    runner = HERE / 'runner.py'
    files[runner.relative_to(ROOT).as_posix()] = runner.read_bytes()
    for path in sorted((ROOT / 'data/raw/a/official/code').glob('*.py')):
        rel = path.relative_to(ROOT).as_posix()
        raw = path.read_bytes()
        key = 'code/' + path.name
        if sha(raw) != official_hashes[key]:
            raise ValueError('official code identity mismatch: ' + rel)
        files[rel] = raw
    for name, expected in [('case_044.json', GRAPH), ('config.txt', CONFIG)]:
        raw = (args.official_data_root / name).read_bytes()
        if sha(raw) != expected or official_hashes['data/' + name] != expected:
            raise ValueError('frozen input identity mismatch: ' + name)
        files['data/raw/a/official/data/' + name] = raw
    manifest = {'case': '044', 'cores': 5,
                'strategy': 'shared_stationary_pipeline',
                'solver_source_commit': SOLVER_SOURCE,
                'old_solver_commit': OLD, 'old_official': {
                    'makespan': 43795, 'added_copy_bytes': 930400,
                    'result_sha256': old['official']['result_sha256']},
                'official_code_hash': official_manifest['official_code_hash'],
                'files': {k: sha(v) for k, v in sorted(files.items())}}
    manifest_raw = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()
    (HERE / 'capsule-manifest.json').write_bytes(manifest_raw)
    archive = HERE / 'capsule.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel, raw in sorted({**files, 'capsule-manifest.json': manifest_raw}.items()):
            entry = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            z.writestr(entry, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    report = {'status': 'hash_only_preflight_passed', 'solver_source_commit': SOLVER_SOURCE,
              'capsule_sha256': sha(archive.read_bytes()), 'manifest_sha256': sha(manifest_raw),
              'capsule_bytes': archive.stat().st_size, 'file_count': len(files),
              'solver_calls': 0, 'E0_calls': 0, 'E1_calls': 0, 'E2_calls': 0}
    (HERE / 'preflight.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
