"""Post-hoc filter coverage on fixed historical component-split proposals.

This does not select final submissions or produce a solver score.
"""
from pathlib import Path
import csv
import gzip
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx.candidate_ddr import mandatory_copy_work

SOURCES = {
    'old': ('571536962b3f6ad9468584a0e5ae04398e684543',
            'results/a/q2-nikolastarx/semantic-benchmark-s59ee-20260925/20260924T1729Z-s59ee/board-feed-500.json',
            'b1652e0ef23699bd6c8139de948fff91d03ecacc64cf6b627e15e8d31fe9df3c'),
    'cut': ('d50f48280d236c351e9cb8e75ae5a3a006cf6c89',
            'results/a/q2-nikolastarx/frontier-benchmark-s59ee-20260925/20260924T1827Z-s59ee/board-feed-500.json',
            '15347fde245b5777edefc7d1b76bc7d49ba6c2989c278b8bdc3732b51fea3576'),
}


def main():
    p = subprocess.Popen(['git','cat-file','--batch'], cwd=ROOT,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    def read(commit, path, sha256):
        p.stdin.write(f'{commit}:{path}\n'.encode()); p.stdin.flush()
        header = p.stdout.readline().split()
        assert len(header) == 3 and header[1] == b'blob', path
        raw = p.stdout.read(int(header[2])); assert p.stdout.read(1) == b'\n'
        assert hashlib.sha256(raw).hexdigest() == sha256, path
        return json.loads(gzip.decompress(raw) if path.endswith('.gz') else raw)
    feeds = {label: {(r['case_id'],r['cores']):r for r in read(*source)['records']}
             for label, source in SOURCES.items()}
    paired_path = ROOT/'results/a/q2-nikolastarx/frontier500-regression-20260925/paired-cells.csv'
    pairs = [r for r in csv.DictReader(paired_path.open())
             if r['new_selected_strategy'] == 'dominant_component_dag']
    results = []
    for row in pairs:
        key = row['case_id'], int(row['cores'])
        old, cut = feeds['old'][key], feeds['cut'][key]
        plan = read(SOURCES['cut'][0], **cut['artifacts']['plan'])
        truth = read(SOURCES['cut'][0], **cut['artifacts']['result'])
        old_truth = read(SOURCES['old'][0], **old['artifacts']['result'])
        graph_raw = (ROOT/f'data/raw/a/official/data/case_{key[0]}.json').read_bytes()
        assert hashlib.sha256(graph_raw).hexdigest() == cut['identity']['graph_sha256'] == old['identity']['graph_sha256']
        assert truth['makespan'] == int(row['new_M']) == cut['metrics']['makespan_cycles']
        assert old_truth['makespan'] == int(row['old_M']) == old['metrics']['makespan_cycles']
        work = mandatory_copy_work(json.loads(graph_raw), plan, truth['bandwidth_bytes_per_cycle'])
        movement = truth['data_movement_bytes']
        assert work['transfer_bytes'] == movement['scheduled_copy_bytes']-movement['spill_added_copy_bytes']
        assert work['service_work'] <= truth['makespan']
        rejected = work['service_work'] > old_truth['makespan']
        results.append({'case':key[0], 'cores':key[1], 'work':work,
                        'whole_E0_M':old_truth['makespan'], 'cut_E0_M':truth['makespan'],
                        'outcome':'loss' if truth['makespan']>old_truth['makespan'] else 'win' if truth['makespan']<old_truth['makespan'] else 'tie',
                        'rejected_by_work':rejected,
                        'candidate_plan':cut['artifacts']['plan'], 'cut_truth':cut['artifacts']['result'],
                        'whole_truth':old['artifacts']['result']})
    p.stdin.close(); assert p.wait()==0
    counts = {}
    for k in (4,5):
        rr = [r for r in results if r['cores']==k]
        counts[str(k)] = {f'{kind}_{gate}':sum(r['outcome']==kind and r['rejected_by_work']==gate for r in rr)
                          for kind in ('win','loss','tie') for gate in (False,True)}
        counts[str(k)]['proposals'] = len(rr)
    report = {'scope':'Post-hoc static filter coverage, historical fixed proposals only; not a new algorithm or best-cell portfolio score.',
              'new_evaluator_calls':0,'feed_sources':SOURCES,
              'paired_audit_sha256':hashlib.sha256(paired_path.read_bytes()).hexdigest(),
              'counter_sha256':hashlib.sha256((ROOT/'src/q2_nikolastarx/candidate_ddr.py').read_bytes()).hexdigest(),
              'counts':counts,'rows':results}
    (OUT/'frontier-coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(counts,indent=2))


if __name__=='__main__':
    main()
