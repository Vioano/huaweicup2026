"""Read central admission snapshots without creating or modifying a local ledger.

The transport owns authentication, durable anti-rollback state and atomic current.json
installation. Hash checks here protect the reader; they are not publisher signatures.
"""
from __future__ import annotations

import copy
import json
import re
import sys
import threading
from pathlib import Path
from urllib.parse import quote

from core import METRICS, number, now, project_records, safe_path, sha

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark_sync.snapshot import MAX_COMPRESSED, reject_history_regression, unpack


def artifact_links(records, key):
    links = set()
    for row in records:
        source = row.get('source', {})
        repo, commit = source.get('repo', ''), source.get('commit')
        if not isinstance(repo, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo) or not sha(commit, 40):
            continue
        specs = list(row.get('artifacts', {}).values())
        specs += [row.get(field, {}).get('result') for field in ('baseline', 'cache_pair')]
        for spec in specs:
            if not isinstance(spec, dict) or spec.get('sha256') != key:
                continue
            try:
                path = safe_path(spec.get('path'))
            except ValueError:
                continue
            links.add(f'https://github.com/{repo}/blob/{commit}/{quote(path, safe="/")}')
    return sorted(links)


class MirrorView:
    mode = 'central_mirror'

    def __init__(self, current, manifest, sync_status=None):
        self.current = Path(current)
        self.expected_manifest = manifest
        self.sync_status = Path(sync_status) if sync_status else None
        self._lock = threading.RLock()
        self._payload = None
        self._last_manifest = None
        self._error = None
        self._loaded_at = None
        self.refresh()  # A missing/corrupt first snapshot fails closed.

    def _validate_records(self, payload):
        if payload.get('manifest') != self.expected_manifest:
            raise ValueError('Snapshot frozen inputs differ from this website release')
        previous_sequence = 0
        for row in payload['records']:
            seq = row.get('sequence')
            if type(seq) is not int or not previous_sequence < seq <= payload['sequence']:
                raise ValueError('Snapshot record sequence is invalid')
            previous_sequence = seq
            for name in ('attempt_id', 'algorithm_id', 'algorithm_name', 'run_id', 'imported_at'):
                if not isinstance(row.get(name), str) or not row[name]:
                    raise ValueError('Snapshot record missing ' + name)
            if row.get('status') not in ('ok', 'failed', 'timeout', 'running', 'not_run', 'unsupported', 'withdrawn'):
                raise ValueError('Snapshot record status invalid')
            if not isinstance(row.get('admission_notes'), list):
                raise ValueError('Snapshot admission notes missing')
            for field in ('eligible', 'baseline_verified', 'cache_pair_verified'):
                if type(row.get(field)) is not bool:
                    raise ValueError('Snapshot admission flag invalid')
            for name, value in row['metrics'].items():
                if name not in METRICS or (value is not None and not number(value, name == 'makespan_cycles')):
                    raise ValueError('Snapshot metric invalid')
            if row['status'] == 'ok' and not number(row['metrics'].get('makespan_cycles'), True):
                raise ValueError('Snapshot successful record lacks Makespan')
            if row['eligible'] and row['status'] != 'ok':
                raise ValueError('Snapshot failed record cannot be eligible')
        if not isinstance(payload.get('source_status'), dict) or not isinstance(payload.get('algorithms'), dict):
            raise ValueError('Snapshot catalog/source status missing')
        if not isinstance(payload.get('publisher'), dict) or not isinstance(payload.get('generated_at'), str):
            raise ValueError('Snapshot publisher/time missing')

    def refresh(self):
        with self._lock:
            try:
                with self.current.open('rb') as stream:
                    raw = stream.read(64 * 1024 + 1)
                if len(raw) > 64 * 1024:
                    raise ValueError('Snapshot manifest too large')
                if raw == self._last_manifest:
                    self._error = None
                    return
                manifest = json.loads(raw)
                name = manifest.get('payload_file', '')
                if not isinstance(name, str) or not re.fullmatch(r'snapshot-[0-9a-f]{64}\.json\.gz', name):
                    raise ValueError('Snapshot payload filename invalid')
                with (self.current.parent / name).open('rb') as stream:
                    data = stream.read(MAX_COMPRESSED + 1)
                candidate = unpack(data, manifest)
                self._validate_records(candidate)
                if self._payload:
                    reject_history_regression(self._payload, candidate)
                self._payload = candidate
                self._last_manifest = raw
                self._loaded_at = now()
                self._error = None
            except (OSError, ValueError, KeyError, TypeError, EOFError) as error:
                self._error = type(error).__name__ + ': ' + str(error)[:250]
                if self._payload is None:
                    raise ValueError('No verified mirror available: ' + self._error) from error

    def _runtime(self):
        state = {'mode': self.mode, 'verification_location': 'central',
                 'local_artifacts_verified': False, 'snapshot_id': self._payload['snapshot_id'],
                 'generated_at': self._payload['generated_at'], 'loaded_at': self._loaded_at,
                 'publisher': self._payload['publisher'], 'error': self._error,
                 'status': 'degraded' if self._error else 'ok'}
        if self.sync_status:
            try:
                with self.sync_status.open('rb') as stream:
                    raw = stream.read(64 * 1024 + 1)
                if len(raw) > 64 * 1024:
                    raise ValueError('Sync status too large')
                state['sync'] = json.loads(raw)
            except (OSError, ValueError) as error:
                state['sync'] = {'status': 'unavailable', 'message': str(error)[:250]}
        return state

    def health(self):
        self.refresh()
        with self._lock:
            runtime = self._runtime()
            return {'status': runtime['status'], 'time': now(), 'read_only': True,
                    'mode': self.mode, 'records': len(self._payload['records']),
                    'sources': self._payload['source_status'], 'runtime': runtime}

    def records(self, filters=None):
        self.refresh()
        with self._lock:
            rows = self._payload['records']
            for key, value in (filters or {}).items():
                if value not in (None, '', 'all'):
                    rows = [r for r in rows if str(r.get(key)) == str(value)]
            return copy.deepcopy(rows)

    def snapshot(self, algorithm=None, run=None, include_reported=False):
        self.refresh()
        with self._lock:
            p = self._payload
            result = project_records(p['records'], p['manifest'], p['sequence'],
                                     p['source_status'], algorithm, run, include_reported)
            result['runtime'] = self._runtime()
            return copy.deepcopy(result)

    def catalog(self):
        self.refresh()
        with self._lock:
            return copy.deepcopy(self._payload['algorithms'])

    def events(self, after, limit=200):
        # Records retain central sequence, including revisions and withdrawals.
        return [{'cursor': r['sequence'], 'type': 'record', 'time': r['imported_at'],
                 'data': {k: r[k] for k in ('id', 'problem', 'case_id', 'cores', 'eligible')}}
                for r in self.records() if r['sequence'] > after][:min(limit, 1000)]

    def blob_sources(self, key):
        return artifact_links(self.records(), key)
