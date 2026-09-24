"""Validate the bundled feed schema and evidence without executing submitted code.

The checker deliberately supports only the keywords in the bundled schema, not
arbitrary JSON Schema. Unknown validation keywords fail closed.
"""
from __future__ import annotations
import argparse
import json
import math
import re
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / 'docs/benchmarks/board-feed.schema.json'


def _check(value, spec, root, path='$'):
    known = {'$schema', '$defs', '$ref', 'title', 'description', 'type', 'anyOf',
             'const', 'enum', 'properties', 'required', 'additionalProperties',
             'items', 'minItems', 'maxItems', 'minimum', 'maximum',
             'exclusiveMinimum', 'pattern', 'minLength', 'maxLength', 'if', 'then'}
    if set(spec) - known:
        raise ValueError(f'{path}: unsupported schema keywords {sorted(set(spec)-known)}')
    if 'if' in spec:
        try:
            _check(value, spec['if'], root, path)
        except ValueError:
            pass
        else:
            _check(value, spec.get('then', {}), root, path)
    if '$ref' in spec:
        return _check(value, root['$defs'][spec['$ref'].removeprefix('#/$defs/')], root, path)
    if 'anyOf' in spec:
        for option in spec['anyOf']:
            try:
                _check(value, option, root, path)
                return
            except ValueError:
                pass
        raise ValueError(f'{path}: does not match allowed types/values')
    types = {'object': lambda v: isinstance(v, dict), 'array': lambda v: isinstance(v, list),
             'string': lambda v: isinstance(v, str), 'null': lambda v: v is None,
             'integer': lambda v: type(v) is int,
             'number': lambda v: type(v) in (int, float) and math.isfinite(v),
             'boolean': lambda v: type(v) is bool}
    if 'type' in spec and not types[spec['type']](value):
        raise ValueError(f'{path}: expected {spec["type"]}')
    if 'const' in spec and (type(value) is not type(spec['const']) or value != spec['const']):
        raise ValueError(f'{path}: expected constant {spec["const"]}')
    if 'enum' in spec and value not in spec['enum']:
        raise ValueError(f'{path}: unknown value {value!r}')
    if isinstance(value, dict):
        missing = set(spec.get('required', [])) - value.keys()
        if missing:
            raise ValueError(f'{path}: missing {sorted(missing)}')
        for key, item in value.items():
            rule = spec.get('properties', {}).get(key, spec.get('additionalProperties', True))
            if rule is False:
                raise ValueError(f'{path}.{key}: unknown field')
            if isinstance(rule, dict):
                _check(item, rule, root, f'{path}.{key}')
    if isinstance(value, list):
        if len(value) > spec.get('maxItems', math.inf) or len(value) < spec.get('minItems', 0):
            raise ValueError(f'{path}: invalid array length')
        for i, item in enumerate(value):
            if 'items' in spec:
                _check(item, spec['items'], root, f'{path}[{i}]')
    if isinstance(value, str):
        if len(value) < spec.get('minLength', 0) or len(value) > spec.get('maxLength', math.inf):
            raise ValueError(f'{path}: invalid string length')
        if 'pattern' in spec and not re.search(spec['pattern'], value):
            raise ValueError(f'{path}: invalid format')
    if type(value) in (float, int):
        if not math.isfinite(value) or value < spec.get('minimum', -math.inf) or value > spec.get('maximum', math.inf) or value <= spec.get('exclusiveMinimum', -math.inf):
            raise ValueError(f'{path}: number outside allowed range')


def validate_feed(feed, submission=False):
    schema = json.loads(SCHEMA.read_text())
    _check(feed, schema, schema)
    strict = submission or feed.get('submission_version') == 1
    seen = set()
    for i, record in enumerate(feed['records']):
        path = f'$.records[{i}]'
        key = (record['attempt_id'], record['revision'])
        if key in seen:
            raise ValueError(f'{path}: duplicate attempt/revision in feed')
        seen.add(key)
        if record['status'] == 'ok' and record['metrics'].get('makespan_cycles') is None:
            raise ValueError(f'{path}: ok requires makespan_cycles')
        if not strict:
            continue
        required = {'variant', 'parameters', 'runtime_id', 'observed_at', 'timing', 'provenance', 'notes', 'source_url'}
        if required - record.keys():
            raise ValueError(f'{path}: submission missing {sorted(required - record.keys())}')
        if 'solver_includes_evaluation' not in record['timing']:
            raise ValueError(f'{path}.timing: solver_includes_evaluation required (null if unknown)')
        for name in ('makespan_cycles', 'solver_wall_seconds', 'evaluation_wall_seconds'):
            if name not in record['metrics']:
                raise ValueError(f'{path}.metrics: missing {name}; use null if unmeasured')
        p = record['provenance']
        source = p['solver']['source']
        if source is not None and source['commit'] != record['solver_commit']:
            raise ValueError(f'{path}: solver source commit differs from solver_commit')
        if (p['solver']['selected_algorithm_id'] is None) != (p['solver']['selected_solver_commit'] is None):
            raise ValueError(f'{path}: selected child algorithm and commit must appear together')
        if record['status'] in ('failed', 'timeout', 'unsupported', 'withdrawn') and p['measurement']['failure'] is None:
            raise ValueError(f'{path}: unsuccessful/withdrawn submission needs failure reason')
        if record['status'] != 'ok' and record['metrics']['makespan_cycles'] is not None:
            raise ValueError(f'{path}: incomplete attempt cannot report final makespan')
        if record['status'] == 'ok' and p['measurement']['failure'] is not None:
            raise ValueError(f'{path}: ok cannot contain final failure')
        missing = p['missing_reasons']
        def nulls(value, prefix):
            if value is None:
                yield prefix
            elif isinstance(value, dict):
                for key, item in value.items():
                    if key != 'missing_reasons':
                        yield from nulls(item, prefix + '.' + key)
        for key in nulls(p, 'provenance'):
            if key.endswith(('.failure', '.selected_algorithm_id', '.selected_solver_commit')):
                continue
            if key not in missing:
                raise ValueError(f'{path}: missing_reasons must explain {key}')
    return strict


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('feed', type=Path)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    parser.add_argument('--commit', help='Read feed and artifacts from this exact Git commit')
    parser.add_argument('--submission', action='store_true', help='Require complete submission profile')
    args = parser.parse_args()
    from core import Ledger, MAX_BLOB, safe_path, packed
    from app import blob
    repo = args.repo.resolve()
    try:
        if args.commit:
            if not re.fullmatch('[0-9a-f]{40}', args.commit):
                raise ValueError('--commit must be a full SHA')
            load = lambda name: blob(repo, args.commit, name)
            raw = load(args.feed.as_posix())
        else:
            def load(name):
                safe_path(name)
                path = (repo / name).resolve()
                if not path.is_relative_to(repo):
                    raise ValueError('artifact escapes repo through a symlink')
                if path.stat().st_size > MAX_BLOB:
                    raise ValueError('artifact too large')
                return path.read_bytes()
            if args.feed.stat().st_size > 8 * 1024 * 1024:
                raise ValueError('feed too large')
            raw = args.feed.read_bytes()
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError('feed too large')
        feed = json.loads(raw)
        strict = validate_feed(feed, args.submission)
        manifest = json.loads((ROOT / 'docs/a/source-manifest.json').read_text())
        calibrations = json.loads((ROOT / 'docs/benchmarks/board-calibrations.json').read_text())
        with tempfile.TemporaryDirectory(prefix='board-validate-') as tmp:
            ledger = Ledger(Path(tmp), manifest, calibrations)
            ledger.ingest(feed, load, {'commit': args.commit, 'path': str(args.feed), 'validation_only': True})
            rows = ledger.records()
            print(packed({'valid': True, 'submission': strict, 'records': len(rows),
                          'eligible': sum(r['eligible'] for r in rows),
                          'reported_or_failed': [{'attempt_id': r['attempt_id'], 'reasons': r['admission_notes']} for r in rows if not r['eligible']],
                          'scope': 'format and available bytes only; no solver/evaluator execution or production write'}))
    except (ValueError, OSError, KeyError) as error:
        print(json.dumps({'valid': False, 'error': str(error)}, ensure_ascii=False))
        raise SystemExit(1)

if __name__ == '__main__':
    main()
