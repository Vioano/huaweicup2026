"""Bounded, immutable changes between two signed central snapshots."""
from __future__ import annotations

import gzip
import io
import json
import zlib

from .snapshot import canonical, reject_history_regression, validate_payload

MAX_DELTA_COMPRESSED = 4 * 1024 * 1024
MAX_DELTA_DECODED = 32 * 1024 * 1024


def pack_delta(base, target):
    """Return a small cumulative delta or None when a full snapshot is safer."""
    validate_payload(base)
    validate_payload(target)
    reject_history_regression(base, target)
    if base['snapshot_id'] == target['snapshot_id']:
        return None
    prefix=len(base['records'])
    if target['records'][:prefix] != base['records']:
        raise ValueError('Snapshot records are not an append-only prefix')
    delta={'schema_version':1,'base_snapshot_id':base['snapshot_id'],
           'target':{key:value for key,value in target.items() if key!='records'},
           'added_records':target['records'][prefix:]}
    raw=canonical(delta)
    if len(raw)>MAX_DELTA_DECODED: return None
    compressed=gzip.compress(raw,mtime=0)
    if len(compressed)>MAX_DELTA_COMPRESSED: return None
    return compressed


def unpack_delta(base, compressed):
    """Reconstruct and validate the exact target without accepting rewritten history."""
    validate_payload(base)
    if not isinstance(compressed,bytes) or len(compressed)>MAX_DELTA_COMPRESSED:
        raise ValueError('Snapshot delta exceeds compressed size bound')
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            raw=stream.read(MAX_DELTA_DECODED+1)
        if len(raw)>MAX_DELTA_DECODED: raise ValueError('Snapshot delta exceeds decoded size bound')
        delta=json.loads(raw)
    except (OSError,EOFError,TypeError,json.JSONDecodeError,zlib.error) as error:
        raise ValueError('Invalid compressed snapshot delta') from error
    if (not isinstance(delta,dict) or delta.get('schema_version')!=1 or
            delta.get('base_snapshot_id')!=base['snapshot_id'] or
            not isinstance(delta.get('target'),dict) or
            not isinstance(delta.get('added_records'),list)):
        raise ValueError('Snapshot delta base or shape mismatch')
    target=dict(delta['target'],records=base['records']+delta['added_records'])
    validate_payload(target)
    reject_history_regression(base,target)
    return target
