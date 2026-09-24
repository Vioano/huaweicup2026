"""Read-only, independent comparison of an accepted snapshot and a running board.

Does not import benchmark_board/benchmark_sync, ingest records, run solvers, or
modify the service. A passing report certifies this fixed snapshot only; it does
not certify automatic publication, hot updates, or scientific re-evaluation.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import urllib.parse
import urllib.request


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_envelope(envelope, pem, fingerprint, domain='snapshot'):
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    require(digest(pem) == fingerprint == envelope['key_sha256'], 'untrusted key')
    require((envelope['schema_version'], envelope['project'], envelope['domain'],
             envelope['issuer']) == (1, 'huaweicup2026-benchmark-board',
                                     domain, 'nikolastarx'), 'wrong signed context')
    key = load_pem_public_key(pem)
    require(isinstance(key, Ed25519PublicKey), 'wrong key type')
    key.verify(base64.b64decode(envelope['signature'], validate=True),
               canonical({k: v for k, v in envelope.items() if k != 'signature'}))
    return envelope['payload']['manifest']


def verify_snapshot(manifest, compressed):
    require(len(compressed) <= 32 * 1024**2, 'compressed size limit')
    require(len(compressed) == manifest['payload_size'], 'compressed size mismatch')
    require(digest(compressed) == manifest['payload_sha256'], 'compressed digest mismatch')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        raw = stream.read(256 * 1024**2 + 1)
    require(len(raw) <= 256 * 1024**2 and len(raw) == manifest['decoded_size'],
            'decoded size mismatch')
    payload = json.loads(raw)
    records = payload['records']
    ids = [r['id'] for r in records]
    require(len(ids) == len(set(ids)) == payload['record_count'], 'duplicate/count mismatch')
    require(all(re.fullmatch('[0-9a-f]{64}', x) for x in ids), 'invalid record id')
    require(len({(r['attempt_id'], r['revision']) for r in records}) == len(records),
            'duplicate attempt/revision')
    previous = 0
    for row in records:
        require(type(row['sequence']) is int and previous < row['sequence'] <= payload['sequence'],
                'invalid record sequence')
        previous = row['sequence']
    require(digest(('\n'.join(sorted(ids)) + '\n').encode()) == payload['record_ids_sha256'],
            'record id digest mismatch')
    require(digest(canonical(records)) == payload['records_sha256'], 'record content digest mismatch')
    semantic = {'sequence': payload['sequence'], 'records_sha256': payload['records_sha256'],
                'sources': {name: {k: v for k, v in state.items()
                                   if k not in ('checked_at', 'started_at')}
                            for name, state in payload['source_status'].items()},
                **{k: payload[k] for k in ('manifest', 'algorithms', 'publisher')}}
    require(digest(canonical(semantic)) == payload['snapshot_id'], 'snapshot digest mismatch')
    for key in ('schema_version', 'sequence', 'generated_at', 'record_count',
                'record_ids_sha256', 'records_sha256', 'snapshot_id', 'publisher'):
        require(payload[key] == manifest[key], 'manifest differs: ' + key)
    return payload


def expected_cells(payload, algorithm=None, run=None, preview=False):
    """Independent oracle: select highest revision before filters or admission."""
    attempts = defaultdict(list)
    for row in payload['records']:
        attempts[row['attempt_id']].append(row)
    latest = [max(rows, key=lambda r: r['revision']) for rows in attempts.values()]
    groups = defaultdict(list)
    for row in latest:
        if algorithm and row['algorithm_id'] != algorithm:
            continue
        if run and row['run_id'] != run:
            continue
        groups[(row['problem'], row['case_id'], row['cores'])].append(row)
    frozen = {f['path']: f['sha256'] for f in payload['manifest']['files']}
    def report_allowed(row):
        ident = row.get('identity', {})
        return (preview and row.get('evaluator', {}).get('route') == 'E0'
                and ident.get('official_sha256') == payload['manifest']['official_code_hash']
                and ident.get('config_sha256') == frozen['data/config.txt']
                and ident.get('graph_sha256') == frozen.get('data/case_' + row['case_id'] + '.json'))
    cells = []
    for problem in ('P1', 'P2', 'P3'):
        for case in (f'{i:03d}' for i in range(1, 101)):
            for cores in range(1, 6):
                rows = groups[(problem, case, cores)]
                admitted = [r for r in rows if r['status'] == 'ok' and r['eligible']]
                reported = [r for r in rows if r['status'] == 'ok' and report_allowed(r)]
                pool = admitted or reported
                best = min(pool, key=lambda r: (r['metrics']['makespan_cycles'], r['id'])) if pool else None
                missing = []
                for row in reversed(rows):
                    if row['status'] == 'ok' and not row['eligible']:
                        missing = [a for a in ('plan', 'result', 'run') if not row.get('artifacts', {}).get(a)]
                        break
                status = ('ok' if best and best['eligible'] else 'reported' if best
                          else ('reported' if rows[-1]['status'] == 'ok' else rows[-1]['status'])
                          if rows else 'not_run')
                cells.append(dict(problem=problem, case_id=case, cores=cores, best=best,
                                  attempts=len(rows), status=status, missing_artifacts=missing))
    return cells


def read_database(path):
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('BEGIN')
        require(db.execute('PRAGMA quick_check').fetchone()[0] == 'ok', 'SQLite integrity error')
        return list(db.execute('SELECT seq,id,attempt,revision,body FROM records ORDER BY seq'))


def verify_extension(previous, current):
    require(current['sequence'] >= previous['sequence'], 'snapshot cursor rollback')
    current_rows = {r['id']: canonical(r) for r in current['records']}
    for row in previous['records']:
        require(current_rows.get(row['id']) == canonical(row), 'central history dropped or rewritten')
    return dict(previous_snapshot_id=previous['snapshot_id'],
                previous_records=len(previous['records']),
                added_records=len(current['records']) - len(previous['records']),
                all_previous_records_preserved=True)


def audit(args):
    root = args.sync_state or args.bootstrap
    snapshot_dir = root / ('accepted' if args.sync_state else 'central')
    manifest = json.loads((snapshot_dir / 'current.json').read_bytes())
    if args.sync_state:
        config = json.loads((root / 'config.json').read_bytes())
        pem = config['trusted_keys']['nikolastarx'].encode('utf-8')
        envelope = manifest['_channel']
        active = json.loads((root / 'software/active.json').read_bytes())
        release_dir = Path(active['path'])
        signed_release = verify_envelope(active['_channel'], pem, args.key_sha256, 'release')
        require(active['release_id'] == signed_release['release_id']
                and active['code_commit'] == signed_release['code_commit'], 'active release identity differs')
        require(json.loads((release_dir / 'release.json').read_bytes()) == signed_release,
                'installed release manifest differs from signed authority')
        release = dict(commit=signed_release['code_commit'],
                       files=[dict(path=p, **spec) for p, spec in signed_release['files'].items()])
    else:
        pem = (root / 'central-public.pem').read_bytes()
        envelope = manifest.get('_channel') or json.loads((snapshot_dir / 'accepted-envelope.json').read_bytes())
        release_dir = args.release
        release = json.loads((root / 'release-files.json').read_bytes())
    signed = verify_envelope(envelope, pem, args.key_sha256)
    public_manifest = {k: v for k, v in manifest.items() if k not in ('_channel', 'verified_at')}
    require(signed == public_manifest, 'installed manifest differs from signed envelope')
    name = manifest['payload_file']
    require(re.fullmatch(r'snapshot-[0-9a-f]{64}\.json\.gz', name), 'unsafe payload name')
    payload = verify_snapshot(manifest, (snapshot_dir / name).read_bytes())
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'schema_version': 1,
              'scope': 'Fixed snapshot equality; not original artifact re-evaluation or live-update acceptance',
              'key_sha256': args.key_sha256, 'generation': envelope['payload']['generation'],
              'snapshot': public_manifest, 'checks': {}}
    checks = report['checks']
    if args.previous_report:
        previous = json.loads(args.previous_report.read_bytes())
        previous_manifest = previous['snapshot']
        require(re.fullmatch(r'snapshot-[0-9a-f]{64}\.json\.gz', previous_manifest['payload_file']),
                'unsafe previous payload name')
        previous_payload = verify_snapshot(previous_manifest,
            ((args.prior_payload_dir or snapshot_dir) / previous_manifest['payload_file']).read_bytes())
        require(report['generation'] >= previous['generation'], 'signed generation rollback')
        checks['central_history_extension'] = verify_extension(previous_payload, payload)
    requests = 0
    def get(path, query=None, raw=False):
        nonlocal requests
        url = args.url.rstrip('/') + path + ('?' + urllib.parse.urlencode(query) if query else '')
        with urllib.request.urlopen(url, timeout=30) as response:
            body = response.read(40 * 1024**2 + 1)
            require(len(body) <= 40 * 1024**2, 'HTTP body size limit')
            require(response.headers.get('Cache-Control') == 'no-store', 'HTTP cache policy differs')
        requests += 1
        return body if raw else json.loads(body)
    health = get('/api/v1/health')
    require(health['runtime']['snapshot_id'] == payload['snapshot_id'], 'service snapshot differs')
    require(health['mode'] == 'central_mirror' and health['status'] == 'ok'
            and health['read_only'] and health['runtime']['local_artifacts_verified'] is False,
            'mirror health or evidence semantics differ')
    checks['health'] = {k: health[k] for k in ('mode', 'records', 'status', 'read_only')}
    received = []
    offset = 0
    while True:
        page = get('/api/v1/records', dict(offset=offset, limit=500))
        require(page['total'] == len(payload['records']), 'HTTP total differs')
        received.extend(page['records'])
        if page['next_offset'] is None:
            break
        require(page['next_offset'] > offset, 'pagination stalled')
        offset = page['next_offset']
    require(canonical(received) == canonical(payload['records']), 'HTTP record content differs')
    checks['all_records'] = {'count': len(received), 'sha256': digest(canonical(received)), 'equal': True}
    require(get('/api/v1/catalog') == payload['algorithms'], 'catalog differs')
    algorithms = sorted({r['algorithm_id'] for r in received})
    runs = sorted({r['run_id'] for r in received})
    filters = [(None, None)] + [(a, None) for a in algorithms] + [(None, r) for r in runs]
    projections = []
    for algorithm, run in filters:
        for preview in (False, True):
            query = dict(include_reported=str(preview).lower())
            if algorithm:
                query['algorithm'] = algorithm
            if run:
                query['run'] = run
            actual = get('/api/v1/cells', query)
            expect = expected_cells(payload, algorithm, run, preview)
            require(canonical(actual['cells']) == canonical(expect), 'cell projection differs: ' + str(query))
            for key, value in (('cursor', payload['sequence']), ('record_count', len(received)),
                               ('algorithms', algorithms), ('runs', runs), ('sources', payload['source_status'])):
                require(actual[key] == value, 'projection metadata differs: ' + key)
            require(actual['runtime']['snapshot_id'] == payload['snapshot_id'], 'snapshot changed during audit')
            projections.append(dict(query=query, cells=len(expect), sha256=digest(canonical(expect))))
    checks['projections'] = projections
    winners = [c['best'] for c in expected_cells(payload) if c['best']]
    checks['winners'] = dict(eligible=sum(r['eligible'] for r in winners),
                             baselines=sum(r['baseline_verified'] for r in winners),
                             cache_pairs=sum(r['cache_pair_verified'] for r in winners),
                             statuses=dict(Counter(r['status'] for r in received)))
    checks['means'] = {}
    for problem in ('P1', 'P2', 'P3'):
        checks['means'][problem] = {}
        for cores in range(1, 6):
            values = [r['metrics']['baseline_speedup'] for r in winners
                      if r['problem'] == problem and r['cores'] == cores
                      and r['eligible'] and r['baseline_verified']
                      and r['metrics'].get('baseline_speedup') is not None]
            checks['means'][problem][str(cores)] = dict(count=len(values),
                mean=sum(values) / len(values) if values else None)
    displayed = [[c['problem'], c['case_id'], c['cores'],
                  f"{c['best']['metrics']['baseline_speedup']:.3f}" if c['best']
                  and c['best']['metrics'].get('baseline_speedup') is not None else 'NA']
                 for c in expected_cells(payload)]
    checks['browser_expected'] = dict(metric='baseline_speedup', cell_count=len(displayed),
                                      cells_sha256=digest(canonical(displayed)))
    if args.browser_observation:
        observed = json.loads(args.browser_observation.read_bytes())
        require(observed['snapshot_id'] == payload['snapshot_id'], 'DOM observation is for another snapshot')
        for key, value in checks['browser_expected'].items():
            require(observed[key] == value, 'rendered DOM differs: ' + key)
        means = [f"{checks['means'][p][str(k)]['mean']:.3f}"
                 if checks['means'][p][str(k)]['mean'] is not None else 'NA'
                 for p in ('P1', 'P2', 'P3') for k in range(1, 6)]
        require(observed['means'] == means, 'rendered means differ')
        checks['browser_observation'] = observed
        checks['browser_observation']['all_numeric_cells_equal'] = True
    # All event pages must describe the same complete record stream.
    events, cursor = [], 0
    while True:
        page = get('/api/v1/events', dict(after=cursor, wait=0))
        if not page['events']:
            break
        require(page['next_cursor'] > cursor, 'event cursor stalled')
        cursor = page['next_cursor']
        events.extend(page['events'])
    expected_events = [dict(cursor=r['sequence'], type='record', time=r['imported_at'],
                            data={k: r[k] for k in ('id', 'problem', 'case_id', 'cores', 'eligible')})
                       for r in received]
    require(canonical(events) == canonical(expected_events), 'event history differs')
    checks['events'] = {'count': len(events), 'last_cursor': cursor, 'equal': True}
    old = read_database(args.backup)
    current = read_database(args.local_db)
    require(old == current, 'preserved local ledger differs from backup')
    require({r[1] for r in old} <= {r['id'] for r in received}, 'local history ids missing centrally')
    checks['local_preservation'] = dict(records=len(old), sqlite_integrity='ok', equal_to_backup=True,
                                       ids_present_in_snapshot=True, rows_sha256=digest(canonical(old)))
    code = release['commit']
    require(re.fullmatch('[0-9a-f]{40}', code), 'release commit invalid')
    tree = json.loads(subprocess.check_output(['gh', 'api', 'repos/huaweibei123/huaweicup2026/git/trees/'
                                               + code + '?recursive=1'], timeout=90))
    require(not tree.get('truncated'), 'release tree truncated')
    blobs = {x['path']: x['sha'] for x in tree['tree'] if x['type'] == 'blob'}
    files = []
    for file in release['files']:
        path = file['path']
        require(not Path(path).is_absolute() and '..' not in Path(path).parts, 'unsafe release path')
        data = (release_dir / path).read_bytes()
        oid = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        require(oid == blobs[path] and (file.get('git_blob', oid) == oid), 'Git release bytes differ: ' + path)
        require(digest(data) == file['sha256'] and len(data) == file['size'], 'release digest differs')
        files.append(dict(path=path, sha256=digest(data), git_blob=oid))
    for path, relative in (('/', 'index.html'), ('/app.js', 'app.js'),
                           ('/style.css', 'style.css'), ('/agent', 'agent.html')):
        expected_bytes = (release_dir / 'src/benchmark_board/web' / relative).read_bytes()
        if path == '/' and args.sync_state:
            hashes = {n: digest((release_dir / 'src/benchmark_board/web' / n).read_bytes())
                      for n in ('index.html', 'app.js', 'style.css')}
            asset_id = digest(canonical(hashes))
            expected_bytes = expected_bytes.replace(b'</head>',
                f'<meta name="board-assets" content="{asset_id}"></head>'.encode(), 1)
            runtime = get('/api/v1/runtime')
            require(runtime['file_hashes'] == hashes and runtime['ui_asset_id'] == asset_id
                    and runtime['served_html_sha256'] == digest(expected_bytes), 'runtime UI identity differs')
            require(runtime['software']['release_id'] == active['release_id']
                    and runtime['software']['code_commit'] == code
                    and runtime['software']['health'] == 'ok', 'actual running release differs or is not healthy')
            checks['signed_running_release'] = dict(release_id=active['release_id'], code_commit=code,
                generation=active['_channel']['payload']['generation'], ui_asset_id=asset_id,
                file_hashes=hashes, software=runtime['software'])
            if args.browser_observation:
                require(observed.get('ui_asset_id') == asset_id, 'loaded browser asset identity differs')
        require(get(path, raw=True) == expected_bytes, 'HTTP static asset differs: ' + path)
    checks['release'] = dict(commit=code, verified_files=files, static_http_assets_equal=4,
                             loaded_browser_version='Requires separate DOM/hot-update test')
    end = get('/api/v1/health')
    require(end['runtime']['snapshot_id'] == payload['snapshot_id'], 'snapshot changed during audit')
    report.update(status='passed', http_requests=requests, completed_at=datetime.now(timezone.utc).isoformat())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--bootstrap', type=Path, help='Legacy compact mirror bootstrap directory')
    mode.add_argument('--sync-state', type=Path, help='Installed automatic sync state; reads no private key bytes')
    parser.add_argument('--release', type=Path, help='Legacy portable release root; formal mode reads signed active pointer')
    for name in ('backup', 'local-db', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--url', required=True)
    parser.add_argument('--key-sha256', required=True, help='PEM SHA256 pinned from authenticated captain message')
    parser.add_argument('--browser-observation', type=Path, help='Read-only CUA DOM observation for this exact snapshot')
    parser.add_argument('--previous-report', type=Path, help='Previously verified report; old compressed payload must remain available')
    parser.add_argument('--prior-payload-dir', type=Path, help='Optional retained prior payload directory')
    args = parser.parse_args()
    if args.bootstrap and args.release is None:
        parser.error('--bootstrap requires --release')
    result = audit(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'snapshot_id': result['snapshot']['snapshot_id'],
                      'records': result['snapshot']['record_count'],
                      'projections': len(result['checks']['projections']),
                      'http_requests': result['http_requests'], 'output': str(args.output)}))


if __name__ == '__main__':
    main()
