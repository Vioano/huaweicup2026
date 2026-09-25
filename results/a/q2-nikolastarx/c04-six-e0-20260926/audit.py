"""Read-only integrity/metric check of the completed C04 pilot; no scoring."""
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[3]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    report = json.loads((HERE / 'report.json').read_bytes())
    ledger_bytes = (HERE / 'ledger.json').read_bytes()
    ledger = json.loads(ledger_bytes)
    assert sha(ledger_bytes) == report['archived_ledger_sha256']
    assert ledger['status'] == 'completed' and ledger['external_E0_started'] == 6
    assert ledger['E1'] == ledger['E2'] == ledger['retry'] == 0
    assert ledger['_archive_provenance']['all_official_result_and_trace_bytes_unmodified']
    assert sha((HERE / 'resource-gate.json').read_bytes()) == report['gate_sha256']
    manifest_bytes = (HERE.parent / 'c04-six-pilot-preparation-20260926/manifest.json').read_bytes()
    assert sha(manifest_bytes) == report['preparation_manifest_sha256']
    candidates = json.loads(manifest_bytes)['candidates']
    for entry in report['artifacts']:
        archived = (HERE / entry['path']).read_bytes()
        raw = gzip.decompress(archived)
        assert sha(archived) == entry['archive_sha256']
        assert sha(raw) == entry['uncompressed_sha256']
        if not entry['redacted']:
            assert sha(raw) == entry['original_sha256'] and len(raw) == entry['original_bytes']
    assert len(candidates) == len(ledger['rows']) == len(report['rows']) == 6
    assert len({(r['case'], r['cores']) for r in report['rows']}) == 6
    for candidate, row, summary in zip(candidates, ledger['rows'], report['rows']):
        assert candidate['case'] == row['case'] == summary['case']
        assert candidate['cores'] == row['cores'] == summary['cores'] == 5
        assert sha((ROOT / candidate['plan_path']).read_bytes()) == candidate['plan_sha256']
        raw = gzip.decompress((HERE / f"{row['case']}-k5/result.json.gz").read_bytes())
        result = json.loads(raw)
        assert sha(raw) == row['result_sha256']
        assert result['scene'] == 'B' and result['num_cores'] == 5
        assert result['makespan'] == row['makespan'] == summary['c04_makespan']
        movement = result['data_movement_bytes']
        assert movement == row['data_movement_bytes']
        assert movement['scheduled_copy_bytes'] == candidate['static_copy_bytes']
        assert movement['spill_added_copy_bytes'] == 0
        process = json.loads(gzip.decompress((HERE / f"{row['case']}-k5/process/process.json.gz").read_bytes()))
        assert process == row['process']
        assert process['status'] == 'ok' and process['exit_code'] == 0 and not process['surviving_pids']
        for ref in candidate['control_artifacts']:
            compressed = (ROOT / ref['path']).read_bytes()
            assert sha(compressed) == ref['sha256']
            control_raw = gzip.decompress(compressed)
            assert sha(control_raw) == ref['uncompressed_sha256']
            if ref['path'].endswith('result.json.gz'):
                control = json.loads(control_raw)
                assert control['makespan'] == candidate['control_makespan'] == summary['control_makespan']
                assert control['data_movement_bytes'] == candidate['control_movement']
        assert result['makespan'] > candidate['control_makespan']
    print('PASS: 6 official result/plan/control/receipt identities; 0 wins, 6 losses; audit made no scoring calls.')


if __name__ == '__main__':
    main()
