"""Pure static coverage check for the five previously recognized four-track graphs.

No official Task, Step, P2, or P3 evaluator is imported or invoked.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

from src.q3.fifth_core_contiguous import construct
from src.q3.layered_query_flow import GuardError


ROOT = Path(__file__).resolve().parents[4]
CASES = (31, 35, 64, 68, 88)


def config(path: Path) -> dict:
    result = {}
    section = None
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('['):
            section = line[1:-1]
            result[section] = {}
        else:
            key, value = line.split()
            result[section][key] = int(value)
    return result


def main() -> None:
    source = ROOT / 'src/q3/fifth_core_contiguous.py'
    archive = ROOT / 'data/raw/a/official-cases.zip'
    cfg_path = ROOT / 'data/raw/a/official/data/config.txt'
    cfg = config(cfg_path)
    rows = []
    with zipfile.ZipFile(archive) as z:
        for number in CASES:
            raw = z.read(f'data/case_{number:03d}.json')
            try:
                plan, meta, _ = construct(
                    json.loads(raw), 5, cfg['capacity'],
                    cfg['multicore_scene_b']['cross_core_copy_delay_cycles'])
            except GuardError as error:
                rows.append({'case_id': f'{number:03d}', 'status': 'unsupported',
                             'graph_sha256': hashlib.sha256(raw).hexdigest(),
                             'reason': str(error)})
                continue
            payload = (json.dumps(plan, ensure_ascii=False, indent=2) + '\n').encode()
            rows.append({'case_id': f'{number:03d}', 'status': 'static_only',
                         'graph_sha256': hashlib.sha256(raw).hexdigest(),
                         'plan_sha256': hashlib.sha256(payload).hexdigest(),
                         'tracks': len(meta['tracks']),
                         'shared_components': meta['shared_components'],
                         'core_lengths': meta['core_lengths'],
                         'frontier_peaks': meta['memory']['bucket_frontier_peaks'],
                         'max_remote_edges': meta['whole_word_envelope']['max_remote_edges']})
    print(json.dumps({
        'schema': 'q3-r9f-static-coverage-v1',
        'status': 'STATIC_ONLY_NO_OFFICIAL_SCORE', 'official_calls': 0,
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'config_sha256': hashlib.sha256(cfg_path.read_bytes()).hexdigest(),
        'cases': rows,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
