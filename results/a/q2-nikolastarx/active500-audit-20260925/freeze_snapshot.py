"""Bind the preceding local paired audit to the producer's immutable data."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
DATA = '60afc38b327680fbda0ff10182e3e05a01edd72d'
CLEAN = '85004b67147a8dfd0b556709b26a9ec41af4c721'
BASE = 'results/a/q2-nikolastarx/active-core-full500-20260925-s59/20260924T1910Z-s59ee'
FEED = BASE + '/board-feed-500-with-runtime-notes.json'
FEED_SHA = '0b850686966d1d7c1ce1a8babb1655051756b42f9a59d5c6f6becd6a87f2f99c'


def main():
    summary = json.loads((OUT/'summary.json').read_text())
    process = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=ROOT,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    def blob(path):
        process.stdin.write(f'{DATA}:{path}\n'.encode())
        process.stdin.flush()
        header = process.stdout.readline().split()
        assert len(header) == 3 and header[1] == b'blob', path
        content = process.stdout.read(int(header[2]))
        assert process.stdout.read(1) == b'\n'
        return content
    raw = blob(FEED)
    assert hashlib.sha256(raw).hexdigest() == FEED_SHA
    records = json.loads(raw)['records']
    assert len(records) == 500
    assert {(r['case_id'], r['cores']) for r in records} == {(f'{i:03d}', k) for i in range(1, 101) for k in range(1, 6)}
    refs = {}
    for r in records:
        assert r['solver_commit'] == summary['provenance']['new_source']
        for item in list(r['artifacts'].values()) + [r['baseline']['result']]:
            if item['path'] in refs:
                assert refs[item['path']] == item['sha256']
            refs[item['path']] = item['sha256']
    for path, digest in refs.items():
        assert hashlib.sha256(blob(path)).hexdigest() == digest, path
    feeds = summary['provenance']['new_shards']
    assert len(feeds) == 500
    for path, digest in feeds.items():
        assert hashlib.sha256(blob(BASE+'/'+path)).hexdigest() == digest, path
    process.stdin.close()
    assert process.wait() == 0
    def tree(commit):
        return subprocess.check_output(['git','rev-parse', f'{commit}:{BASE}'], cwd=ROOT, text=True).strip()
    tree_sha = tree(DATA)
    assert tree_sha == tree(CLEAN)
    prov = summary['provenance']
    prov.pop('clean_results_pr', None)
    prov.update(new_data_commit=DATA, clean_data_commit=CLEAN,
                new_data_status='All 500 audited shard feeds and referenced originals match the fixed producer commit.',
                new_unified_feed_path=FEED, new_unified_feed_sha256=FEED_SHA,
                clean_results_tree=tree_sha, fixed_commit_original_blobs_verified=len(refs),
                fixed_commit_shard_feeds_verified=len(feeds))
    summary['runtime_note'] = 'Runner/controller Python 3.14.5; producer records solver and external E0 child argv using locked .venv Python 3.12.13. Runtime-notes feed preserves this distinction. Concurrent wall samples are not exclusive timing.'
    (OUT/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    cores = summary['cores']
    text = '# Active-core 500 paired data audit\n\nAll ratios use the same verified official per-case single-core B_i. Each mean averages all 100 B_i/M_i ratios for the selected core count.\n\n| Cores | Old mean | New mean | Wins | Losses | Ties |\n|---:|---:|---:|---:|---:|---:|\n'
    for k, row in cores.items():
        text += f"| {k} | {row['old_mean_B_over_M']:.9f} | {row['new_mean_B_over_M']:.9f} | {row['win']} | {row['loss']} | {row['tie']} |\n"
    text += '\nTotal: '+', '.join(f'{sum(r[x] for r in cores.values())} {x}' for x in ['win','loss','tie'])+'.\n\n'
    text += f'Data commit `{DATA}`; clean data commit `{CLEAN}`; identical results subtree `{tree_sha}`. Unified feed `{FEED}` has SHA-256 `{FEED_SHA}`. Verified {len(feeds)} prior audited shard feeds and {len(refs)} distinct original blobs against the fixed commit.\n\n'
    text += 'The paired audit checks graph/config/source identities, referenced result/run/plan hashes, DDR fields and each available manifest (500 new, 0 declared by old feed). No new solver or E0/E1/E2 calls. This is an evidence audit, not full independent algorithm acceptance.\n\n'+summary['runtime_note']+'\n\n'
    text += 'Reproduction: run `audit_active500.py --new-root PRODUCER_CHECKOUT --old-root REPOSITORY --new-shards PRODUCER_CHECKOUT/'+BASE+'`, then `freeze_snapshot.py`. Both scripts read existing artifacts; neither evaluates plans. Final summary/README come from the second script.\n'
    (OUT/'README.md').write_text(text)
    print(json.dumps({'original_blobs':len(refs),'shard_feeds':len(feeds),'tree':tree_sha,'evaluator_calls':0}))


if __name__ == '__main__':
    main()
