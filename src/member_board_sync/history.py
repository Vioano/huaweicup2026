"""Bounded, read-only all-history audit, independent of production modules.

Checks signed current data, published older checkpoints, every HTTP record,
and complete batch membership/counts. Does not certify ranking semantics,
scientific results, latency guarantees, or a remote browser.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import urlopen

from audit import canonical, digest, expected_cells, require, verify_envelope, verify_snapshot, verify_extension


ANCHORS = [
    dict(snapshot_id='a5df67f93aa24ff1354ba1e37fae4287fbb7207d3bfdb86b802e4319ee1aef29',
         record_count=5962,
         records_sha256='0706f291c9df4965556fe53fc5f345e7eda235c925b0c89676923d4be09c5c2a',
         record_ids_sha256='1486f3a1e4f17ffa26c6456f580e30be28db31c88b3f59612dfb374edbea0ffa'),
    dict(snapshot_id='c9c2c41a2011e648fd8b05995c8a36434298921a8b91d36f4cae45778d494b99',
         record_count=6468,
         records_sha256='301cf60b1835d8a5a12b5b22adf65dc68b62baa428ea7d89bb909e264fe5e695',
         record_ids_sha256='89d66a16ddeddc8ee590dce98d001446cd76e0364fc77ad7bd688b262c07b4ba'),
]


def audit(args):
    started = datetime.now(timezone.utc).isoformat()
    accepted = args.sync_state / 'accepted'
    installed = json.loads((accepted/'current.json').read_bytes())
    public = {k:v for k,v in installed.items() if k not in ('_channel', 'verified_at')}
    config = json.loads((args.sync_state/'config.json').read_bytes())
    pem = config['trusted_keys']['nikolastarx'].encode()
    require(verify_envelope(installed['_channel'], pem, args.key_sha256) == public,
            'installed manifest differs from authenticated manifest')
    require(re.fullmatch(r'snapshot-[0-9a-f]{64}\.json\.gz', public['payload_file']), 'unsafe name')
    payload = verify_snapshot(public, (accepted/public['payload_file']).read_bytes())
    active = json.loads((args.sync_state/'software/active.json').read_bytes())
    release = verify_envelope(active['_channel'], pem, args.key_sha256, 'release')
    require(active['release_id'] == release['release_id'] and active['code_commit'] == release['code_commit'],
            'active release identity mismatch')
    release_root = Path(active['path'])
    for name, spec in release['files'].items():
        relative = Path(name)
        require(not relative.is_absolute() and '..' not in relative.parts, 'unsafe release path')
        content = (release_root/relative).read_bytes()
        require(digest(content) == spec['sha256'] and len(content) == spec['size'], 'release file differs: '+name)

    def get(path, query=None, raw=False):
        with urlopen(args.url.rstrip('/')+path+('?' + urlencode(query) if query else ''), timeout=30) as response:
            require(response.headers.get('Cache-Control') == 'no-store', 'unexpected caching')
            body=response.read(40*1024**2+1)
            require(len(body)<=40*1024**2, 'response too large')
            return body if raw else json.loads(body)

    before = get('/api/v1/health')
    require(before['runtime']['snapshot_id'] == public['snapshot_id'], 'initial snapshot changed')
    require(before['mode'] == 'central_mirror' and before['read_only'], 'not read-only mirror')
    offsets=list(range(0, public['record_count'], 500))
    with ThreadPoolExecutor(max_workers=4) as pool:
        pages=list(pool.map(lambda offset:get('/api/v1/records',dict(offset=offset,limit=500)),offsets))
    received=[]
    for offset,page in zip(offsets,pages):
        require(page['total']==public['record_count'], 'page total differs')
        require(page['next_offset']==(offset+500 if offset+500<public['record_count'] else None), 'page cursor differs')
        received.extend(page['records'])
    require(canonical(received)==canonical(payload['records']), 'HTTP history differs')

    latest={}
    for row in received:
        old=latest.get(row['attempt_id'])
        if old is None or row['revision']>old['revision']:
            latest[row['attempt_id']]=row
    groups=defaultdict(list)
    for row in latest.values():
        groups[(row['problem'],row['run_id'])].append(row)
    batches={}
    for problem in ('P1','P2','P3'):
        actual=get('/api/v1/batches',dict(problem=problem,cores=5))
        entries={b['run_id']:b for b in actual['batches']}
        expect={run:rows for (p,run),rows in groups.items() if p==problem}
        require(len(entries)==len(actual['batches']) and set(entries)==set(expect), 'batch membership differs '+problem)
        for run,rows in expect.items():
            scope=[r for r in rows if r['cores']==5 and r['case_id'] in {f'{n:03d}' for n in range(1,101)}]
            require(entries[run]['record_count']==len(rows), 'batch count differs '+run)
            require(entries[run]['scope_attempts']==len(scope), 'scope count differs '+run)
            require(entries[run]['status_counts']==dict(Counter(r['status'] for r in scope)), 'statuses differ '+run)
        batches[problem]=dict(raw_records=sum(r['problem']==problem for r in received),
            latest_attempts=sum(len(v) for v in expect.values()),batch_count=len(entries),
            all_batches={run:len(rows) for run,rows in sorted(expect.items())},
            missing=[],extra=[],count_mismatches=[],scope_status_mismatches=[],
            full_complete_count_reported=actual['full_complete_count'])
    web=release_root/'src/benchmark_board/web'
    hashes={name:digest((web/name).read_bytes()) for name in ('index.html','app.js','style.css')}
    asset_id=digest(canonical(hashes))
    runtime=get('/api/v1/runtime')
    require(runtime['file_hashes']==hashes and runtime['ui_asset_id']==asset_id, 'runtime UI differs')
    require(runtime['software']['code_commit']==release['code_commit']
            and runtime['software']['release_id']==release['release_id']
            and runtime['software']['health']=='ok', 'running release differs')
    require(payload['publisher']['board_code_commit']==release['code_commit'], 'central publisher code differs')
    for route,name in (('/','index.html'),('/app.js','app.js'),('/style.css','style.css'),('/agent','agent.html')):
        expected=(web/name).read_bytes()
        if route=='/':
            expected=expected.replace(b'</head>',f'<meta name="board-assets" content="{asset_id}"></head>'.encode(),1)
        require(get(route,raw=True)==expected, 'static HTTP differs '+route)
    cells=expected_cells(payload)
    actual_cells=get('/api/v1/cells',dict(include_reported='false'))
    require(actual_cells['runtime']['snapshot_id']==public['snapshot_id'], 'cell snapshot changed')
    require(canonical(actual_cells['cells'])==canonical(cells), 'all 1500 cell bodies differ')
    after=get('/api/v1/health')
    require(after['runtime']['snapshot_id']==public['snapshot_id'], 'snapshot changed during audit; inconclusive')

    anchors=[]
    for pin in ANCHORS:
        compressed=(accepted/('snapshot-'+pin['snapshot_id']+'.json.gz')).read_bytes()
        old=json.loads(gzip.decompress(compressed))
        require(all(old[k]==v for k,v in pin.items()), 'published checkpoint differs')
        manifest={k:old[k] for k in ('schema_version','sequence','generated_at','record_count',
                                   'record_ids_sha256','records_sha256','snapshot_id','publisher')}
        manifest.update(payload_size=len(compressed),payload_sha256=digest(compressed),decoded_size=len(gzip.decompress(compressed)))
        old=verify_snapshot(manifest,compressed)
        anchors.append(dict(published_pin=pin,**verify_extension(old,payload),
            authentication='Published Issue checkpoint hashes and current signed exact-content coverage; old envelope not separately available.'))
    attempts=defaultdict(list)
    for r in received:
        if r['problem']=='P3' and ('q3-unified-full500-20260925-s59' in r['algorithm_id'] or 'q3-unified-full500-20260925-s59' in r['run_id']):
            attempts[r['attempt_id']].append(r)
    revisions=[]
    for aid,rows in attempts.items():
        by_rev={r['revision']:r for r in rows}
        if 1 in by_rev and 2 in by_rev:
            a,b=by_rev[1],by_rev[2]
            require(a['metrics']==b['metrics'], 'revision metrics changed')
            require(a['status']==b['status']=='ok', 'revision status differs')
            revisions.append(dict(attempt_id=aid,old_id=a['id'],new_id=b['id'],
                                  changed_fields=sorted(k for k in a.keys()|b.keys() if a.get(k)!=b.get(k))))
    require(len(revisions)==500, 'expected 500 real revision pairs')

    dom=[]
    for c in cells:
        best=c['best']
        value=best.get('metrics',{}).get('baseline_speedup') if best else None
        dom.append([c['problem'],c['case_id'],c['cores'],f'{value:.3f}' if value is not None else '—'])
    latency=(datetime.fromisoformat(installed['verified_at'])-datetime.fromisoformat(public['generated_at'])).total_seconds()
    return dict(status='passed',started_at=started,completed_at=datetime.now(timezone.utc).isoformat(),
        scope='All raw HTTP records, complete latest-revision batch membership/counts/statuses at k5, installed signed release, published checkpoint preservation and real revision pairs.',
        snapshot=public,signed_envelope=installed['_channel'],key_sha256=args.key_sha256,
        release=dict(code_commit=release['code_commit'],release_id=release['release_id'],verified_files=len(release['files']),
                     ui_asset_id=asset_id,static_http_assets_equal=4,runtime_equal=True,central_publisher_code_equal=True),
        http=dict(snapshot_before=before['runtime']['snapshot_id'],snapshot_after=after['runtime']['snapshot_id'],
                  record_count=len(received),records_sha256=digest(canonical(received)),pages=len(pages),
                  missing_ids=[],extra_ids=[],canonical_mismatches=[]),
        raw_status_counts=dict(Counter(r['status'] for r in received)),
        raw_revision_counts=dict(Counter(str(r['revision']) for r in received)),
        batch_total=sum(b['batch_count'] for b in batches.values()),batches=batches,anchors=anchors,
        p3_revision_pairs=dict(count=len(revisions),all_metrics_unchanged=True,all_old_and_new_preserved=True,
                               pairs_sha256=digest(canonical(revisions)),sample=revisions[:2]),
        expected_overview_numeric_dom=dict(metric='baseline_speedup',cells=len(dom),all_http_cell_bodies_equal=True,
            tuple_sha256=digest(json.dumps(dom,separators=(',',':'),ensure_ascii=False).encode()),
            problem_tuple_sha256={p:digest(json.dumps([x for x in dom if x[0]==p],separators=(',',':'),ensure_ascii=False).encode()) for p in ('P1','P2','P3')}),
        snapshot_observation=dict(verified_at=installed['verified_at'],generated_to_verified_seconds=latency,
                                 interpretation='Observed two-host timestamps; includes clock offset, not a guaranteed latency bound.'),
        limitations=['No production changes, manual import, refresh, solver or E0 calls.',
                     'Does not re-certify new ranking/full-batch eligibility semantics or original evaluator artifacts.',
                     'Browser observations are separate; no remote browser or instantaneous delivery claim.'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sync-state',type=Path,required=True)
    p.add_argument('--url',required=True)
    p.add_argument('--key-sha256',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result=audit(a)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('status','batch_total','http','release','p3_revision_pairs','expected_overview_numeric_dom','snapshot_observation')},ensure_ascii=False))
