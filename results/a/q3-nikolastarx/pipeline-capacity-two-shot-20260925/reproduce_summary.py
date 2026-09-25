"""Summarize the two preserved official results without any new evaluation."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def read(p):
    raw = p.read_bytes()
    if p.suffix == '.gz':
        raw = gzip.decompress(raw)
    return json.loads(raw)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--forest-root', required=True, type=Path)
    a = p.parse_args()
    run, manifest = read(OUT/'run.json'), read(OUT/'manifest.json')
    assert run['status'] == 'complete' and run['new_p3_reserved'] == 2
    assert run['manifest_sha256'] == sha(OUT/'manifest.json')
    rows = []
    for job in run['jobs']:
        assert job['status'] == 'ok'
        base, = [c for c in manifest['controls'] if c['case_id'] == job['case_id']]
        old_path = a.forest_root/base['artifacts']['result']['path']
        new_path = OUT/'evaluation'/job['case_id']/'result.json.gz'
        assert sha(old_path) == base['artifacts']['result']['sha256']
        assert sha(new_path) == job['result_sha256']
        assert sha(OUT/job['plan_file']) == job['plan_sha256']
        before, after = read(old_path), read(new_path)
        assert before['makespan'] == base['existing_makespan']
        assert after['makespan'] == job['makespan']
        row = {'case_id': job['case_id'], 'cores': 5,
               'source_commit': run['source_commit'],
               'plan_sha256': job['plan_sha256'], 'result_sha256': job['result_sha256'],
               'old': {k: before[k] for k in ('makespan','data_movement_bytes','cache_stats')},
               'new': {k: after[k] for k in ('makespan','data_movement_bytes','cache_stats')},
               'makespan_delta': after['makespan']-before['makespan'],
               'makespan_improvement_fraction': 1-after['makespan']/before['makespan'],
               'static_plan_lower_bound_cycles': job['static_plan_lower_bound'],
               'remaining_to_plan_bound_cycles': after['makespan']-job['static_plan_lower_bound'],
               'solver_wall_seconds': None,
               'evaluation_wall_seconds': job['child']['wall_seconds'],
               'sampled_group_rss_peak_bytes': job['child']['memory']['sampled_peak_rss_bytes']}
        rows.append(row)
    summary = {'scope': 'two fixed P3 mechanism results, not full500, cache gain or solver timing',
               'started_at': run['started_at'], 'finished_at': run['finished_at'],
               'new_p3': 2, 'new_p2': 0, 'new_solver': 0, 'retries': 0,
               'summary_script_new_e0': 0, 'cases': rows}
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([{'case':r['case_id'],'old':r['old']['makespan'],
                      'new':r['new']['makespan'],'improvement':r['makespan_improvement_fraction']}
                     for r in rows]))


if __name__ == '__main__':
    main()
