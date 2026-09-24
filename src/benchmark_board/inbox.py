"""Consume already-authenticated local deliveries using the central Ledger.

No remote execution, HTTP writes, signature implementation or independent database.
The transport must finish an immutable delivery before publishing request.json.
"""
from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from core import MAX_BLOB, digest, now, packed, safe_path, sha
from protocol import validate_feed

REPO = 'huaweibei123/huaweicup2026'
IDENTIFIER = re.compile(r'[A-Za-z0-9_-]{1,128}')


def atomic_result(path, result):
    fd, temp = tempfile.mkstemp(prefix='.result-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(packed(result) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)


def read_within(directory, relative, limit):
    target = (directory / relative).resolve()
    if not target.is_relative_to(directory.resolve()):
        raise ValueError('Delivery path escapes its directory')
    if not stat.S_ISREG(target.stat().st_mode):
        raise ValueError('Delivery path must be a regular file')
    with target.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit: raise ValueError('Delivery file exceeds size limit')
    return data


def consume(ledger, directory):
    """One stable submission; existing result is terminal, even after restart."""
    result_file = directory / 'result.json'
    if result_file.exists(): return None
    identifier = directory.name
    response = {'schema_version': 1, 'id': identifier, 'state': 'rejected',
                'receipt': None, 'error': None}
    try:
        request = json.loads(read_within(directory, 'request.json', 64 * 1024))
        if not isinstance(request, dict): raise ValueError('Delivery request must be an object')
        if request.get('schema_version') != 1 or request.get('id') != identifier or not IDENTIFIER.fullmatch(identifier):
            raise ValueError('Invalid delivery schema/id/directory')
        if request.get('feed_file') != 'feed.json':
            raise ValueError('feed_file must be feed.json')
        raw_source = request.get('source', {})
        if not isinstance(raw_source, dict): raise ValueError('Delivery source must be an object')
        commit = raw_source.get('commit')
        feed_path = safe_path(raw_source.get('feed'))
        if not sha(commit, 40): raise ValueError('Fixed source commit required')
        source_id = raw_source.get('id', '')
        if not isinstance(source_id, str) or not re.fullmatch(r'auto:[A-Za-z0-9_-]{1,100}:' + re.escape(identifier), source_id):
            raise ValueError('Invalid automatic source identity')
        fixed_url = f'https://github.com/{REPO}/blob/{commit}/{feed_path}'
        if raw_source.get('url') != fixed_url:
            raise ValueError('Source URL must identify the exact feed at the fixed commit')
        source = {'repo': REPO, 'commit': commit, 'path': feed_path, 'url': fixed_url}
        feed = json.loads(read_within(directory, 'feed.json', 8 * 1024 * 1024))
        if not isinstance(feed, dict): raise ValueError('Delivery feed must be an object')
        if feed.get('submission_version') != 1:
            raise ValueError('Automatic delivery requires submission_version=1')
        validate_feed(feed, submission=True)
        def loader(path):
            return read_within(directory, 'artifacts/' + safe_path(path), MAX_BLOB)
        # Check every declared original, including logs and failed-run receipts.
        # A transport error must not silently become an accepted report-only row.
        references = {}
        for row in feed['records']:
            specs = list(row.get('artifacts', {}).values())
            specs += [row.get(name, {}).get('result') for name in ('baseline', 'cache_pair') if row.get(name)]
            for spec in specs:
                if spec is None: continue
                path = safe_path(spec.get('path'))
                if not sha(spec.get('sha256')): raise ValueError('Artifact hash missing')
                if path in references and references[path] != spec['sha256']:
                    raise ValueError('Conflicting artifact hashes for one path')
                references[path] = spec['sha256']
        for path, expected in references.items():
            if digest(loader(path)) != expected:
                raise ValueError('Artifact bytes/hash mismatch: ' + path)
        receipt = ledger.ingest(feed, loader, source)
        ids = {digest(packed(row).encode()) for row in feed['records']}
        rows = ledger.records_by_ids(ids)
        response.update(state='accepted', receipt=receipt,
                        admission={'records': len(rows), 'eligible': sum(r['eligible'] for r in rows),
                                   'reported_ok': sum(r['status'] == 'ok' and not r['eligible'] for r in rows),
                                   'statuses': dict(Counter(r['status'] for r in rows))})
        ledger.source_status(source_id, {'status': 'ok', 'checked_at': now(), 'commit': commit,
                                        'feed': feed_path, 'added': receipt['added'],
                                        'message': '已接收自动交付；accepted 表示入库，入榜以各条 eligible 为准'})
    except (OSError, ValueError, KeyError, TypeError) as error:
        message = (error.strerror or 'Local file I/O failed') if isinstance(error, OSError) else str(error)
        response['error'] = type(error).__name__ + ': ' + message[:500]
    atomic_result(result_file, response)
    return response


def drain_inbox(ledger, root, limit=8):
    """Process a bounded queue, leaving incomplete/unpublished deliveries alone."""
    root = Path(root)
    if not root.exists(): return []
    results = []
    for directory in sorted(root.iterdir()):
        if directory.is_symlink() or not directory.is_dir() or not IDENTIFIER.fullmatch(directory.name): continue
        if not (directory / 'request.json').is_file() or (directory / 'result.json').exists(): continue
        try:
            result = consume(ledger, directory)
            if result: results.append(result)
        except OSError as error:
            # A full/unavailable disk cannot yield a durable result. Do not claim
            # success; on a later scan ingest will use its normal batch idempotency.
            results.append({'id': directory.name, 'state': 'retry', 'error': str(error)[:250]})
        if len(results) >= limit: break
    return results
