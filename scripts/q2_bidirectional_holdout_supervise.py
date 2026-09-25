"""Outer, fail-closed Mac supervisor for the fixed local bidirectional holdout12 producer.

No scoring is done by this module itself. An admitted, hash-pinned gate is
required before it will invoke the producer. Output is a fresh parent folder.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

SOURCE = '15d86e13b4a8abb4bce445ac241aecac13f553bf'
SELECTION_SHA = '6060d2a281e963614eb0634dbf90454b3b7b52be73d0d6cc67287436e33d16b1'
MONITOR_SHA = '9b9dbbf1b43423cafb1492285af3d9e7ec55d7201539a65c56c12f5f0edc4849'
SCOPE = 'p2-bidirectional-holdout12'
RSS_LIMIT = 2 << 30
GROWTH_LIMIT = 2 << 30
FREE_RESERVE = 10 << 30
DEADLINE_SECONDS = 1800
SAMPLE_SECONDS = 1.0


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def save(path, value):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    tmp.replace(path)


def read(path):
    return json.loads(path.read_text())


def gate_check(gate, pins):
    doc = read(gate)
    if doc.get('status') != 'admitted' or doc.get('scope') != SCOPE:
        raise ValueError('gate is not admitted for this scope')
    try:
        expiry = datetime.fromisoformat(doc['expires_at_utc'].replace('Z', '+00:00'))
    except (KeyError, ValueError, TypeError) as error:
        raise ValueError('gate has no valid expiry') from error
    if expiry.tzinfo is None or datetime.now(timezone.utc) >= expiry:
        raise ValueError('gate expired')
    for key, value in pins.items():
        if doc.get(key) != value:
            raise ValueError('gate pin mismatch: ' + key)
    return sha(gate)


def disk_usage(root):
    total = 0
    for base, _, files in os.walk(root):
        for name in files:
            try:
                total += (Path(base) / name).stat().st_size
            except FileNotFoundError:
                pass
    return total


def preflight_paths(args):
    paths = {key: Path(getattr(args, key)).resolve(strict=True)
             for key in ('repo', 'python', 'runner', 'manifest', 'raw_root', 'e2_root', 'gate')}
    out = Path(args.output).resolve()
    if out.exists():
        raise ValueError('supervisor output must be fresh')
    if any(out == paths[key] or out.is_relative_to(paths[key])
           for key in ('repo', 'raw_root', 'e2_root')):
        raise ValueError('output overlaps fixed source/input')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=paths['repo'], text=True).strip()
    if head != SOURCE:
        raise ValueError('fixed source HEAD differs')
    monitor_path = paths['repo'] / 'src/q2_nikolastarx/evaluate_feedback.py'
    if sha(monitor_path) != MONITOR_SHA:
        raise ValueError('fixed monitor bytes differ')
    manifest = read(paths['manifest'])
    if (manifest.get('schema') != 'q2-bidirectional-holdout12-v1'
            or manifest.get('solver_source_commit') != SOURCE
            or sha(paths['runner']) != manifest.get('runner_sha256')):
        raise ValueError('runner/source manifest mismatch')
    limits = manifest.get('limits', {})
    if (limits.get('cells') != 12 or limits.get('workers') != 1
            or limits.get('batch_seconds') != DEADLINE_SECONDS
            or limits.get('rss_bytes_total') != RSS_LIMIT):
        raise ValueError('supervisor/producer limits differ')
    selection = manifest.get('selection_manifest')
    if (not isinstance(selection, dict) or set(selection) != {'path', 'sha256'}
            or Path(selection['path']).is_absolute() or '..' in Path(selection['path']).parts):
        raise ValueError('invalid selection reference')
    selection_path = (paths['manifest'].parent / selection['path']).resolve(strict=True)
    if not selection_path.is_relative_to(paths['manifest'].parent):
        raise ValueError('selection escapes manifest directory')
    selection_sha = sha(selection_path)
    if selection_sha != selection['sha256'] or selection_sha != SELECTION_SHA:
        raise ValueError('selection hash differs')
    selected = read(selection_path).get('coordinates')
    if (manifest.get('coordinates') != selected or not isinstance(selected, list)
            or len(selected) != 12 or len({tuple(x) for x in selected}) != 12
            or any(not isinstance(x, list) or len(x) != 2 or x[1] != 5 for x in selected)):
        raise ValueError('manifest/selection coordinate mismatch')
    pins = {'source_commit': SOURCE, 'runner_sha256': sha(paths['runner']),
            'manifest_sha256': sha(paths['manifest']), 'selection_sha256': selection_sha,
            'supervisor_sha256': sha(Path(__file__))}
    gate_sha = gate_check(paths['gate'], pins)
    spec = importlib.util.spec_from_file_location('fixed15d_monitor', monitor_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return paths, out, pins, gate_sha, module


def run(args):
    # The wall clock starts before gate/preflight; every later step shares it.
    start = time.monotonic()
    deadline = start + DEADLINE_SECONDS
    paths, output, pins, gate_sha, monitor = preflight_paths(args)
    output.mkdir(parents=True, exist_ok=False)
    results = output / 'results'
    receipt = {'scope': SCOPE, 'status': 'starting', 'started_at': utc(),
               'pins': pins, 'gate_sha256': gate_sha, 'output': str(output),
               'limits': {'seconds': DEADLINE_SECONDS, 'aggregate_rss_bytes': RSS_LIMIT,
                          'output_growth_observation_bytes': GROWTH_LIMIT,
                          'disk_free_reserve_bytes': FREE_RESERVE,
                          'sample_seconds': SAMPLE_SECONDS, 'workers': 1},
               'observed_peak_rss_bytes': 0, 'observed_peak_output_bytes': 0,
               'samples': 0, 'known_processes': 0, 'cleanup_killed_pids': [],
               'surviving_pids': [], 'exit_code': None, 'summary_path': str(results / 'summary.json')}
    process = None
    known = {}
    failure = None
    stdout = output / 'producer.stdout.txt'
    stderr = output / 'producer.stderr.txt'
    try:
        if time.monotonic() >= deadline:
            raise TimeoutError('deadline before dispatch')
        if shutil.disk_usage(output).free < FREE_RESERVE:
            raise RuntimeError('disk reserve below 10 GiB before dispatch')
        if gate_check(paths['gate'], pins) != gate_sha:
            raise RuntimeError('gate changed before dispatch')
        command = [str(paths['python']), '-B', str(paths['runner']), 'run',
                   '--repo', str(paths['repo']), '--raw-root', str(paths['raw_root']),
                   '--e2-root', str(paths['e2_root']), '--python', str(paths['python']),
                   '--manifest', str(paths['manifest']), '--output', str(results)]
        receipt['producer_command'] = command
        with stdout.open('w') as out, stderr.open('w') as err:
            process = subprocess.Popen(command, cwd=paths['repo'], stdout=out, stderr=err,
                                       start_new_session=True,
                                       env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            receipt['pid'] = process.pid
            receipt['status'] = 'running'
            while True:
                # ps errors or malformed snapshots are fatal, never interpreted as zero RSS.
                snapshot = monitor.process_snapshot()
                if not snapshot or os.getpid() not in snapshot:
                    raise RuntimeError('process snapshot missing observer')
                if process.pid not in known:
                    if process.poll() is None and process.pid in snapshot:
                        known[process.pid] = snapshot[process.pid]['birth']
                    elif process.poll() is None:
                        raise RuntimeError('live producer missing from process snapshot')
                    else:
                        # A short-lived process cannot safely bind descendants.
                        receipt['short_exit_before_identity'] = True
                        break
                alive = monitor.discover(snapshot, process.pid, known)
                if process.pid in snapshot and snapshot[process.pid]['birth'] != known[process.pid]:
                    raise RuntimeError('producer PID identity changed')
                if process.poll() is None and process.pid not in alive:
                    raise RuntimeError('live producer lost from tree')
                observer = snapshot[os.getpid()]['rss']
                rss = observer + sum(snapshot[pid]['rss'] for pid in alive)
                receipt['samples'] += 1
                receipt['known_processes'] = len(known)
                receipt['observed_peak_rss_bytes'] = max(receipt['observed_peak_rss_bytes'], rss)
                growth = disk_usage(output)
                receipt['observed_peak_output_bytes'] = max(receipt['observed_peak_output_bytes'], growth)
                if rss > RSS_LIMIT:
                    receipt['status'] = 'rss_limit'; break
                if growth > GROWTH_LIMIT:
                    receipt['status'] = 'output_growth_limit'; break
                if shutil.disk_usage(output).free < FREE_RESERVE:
                    receipt['status'] = 'disk_reserve'; break
                if gate_check(paths['gate'], pins) != gate_sha:
                    receipt['status'] = 'gate_changed'; break
                if time.monotonic() >= deadline:
                    receipt['status'] = 'timeout'; break
                if process.poll() is not None:
                    break
                time.sleep(min(SAMPLE_SECONDS, max(0, deadline - time.monotonic())))
    except BaseException as exc:
        failure = exc
        receipt['status'] = 'supervision_error'
        receipt['error'] = repr(exc)
    finally:
        if process is not None:
            # Catch detached descendants and retain all failure evidence.
            try:
                if known:
                    receipt['cleanup_killed_pids'] = monitor.cleanup_tree(process.pid, known)
                elif process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    receipt['cleanup_killed_pids'] = [process.pid]
                process.wait(timeout=5)
            except BaseException as exc:
                receipt['cleanup_error'] = repr(exc)
                receipt['status'] = 'cleanup_error'
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                        receipt['emergency_group_killed'] = True
                        process.wait(timeout=5)
                    except BaseException as emergency:
                        receipt['emergency_cleanup_error'] = repr(emergency)
            receipt['exit_code'] = process.poll()
            try:
                snapshot = monitor.process_snapshot()
                if not snapshot or os.getpid() not in snapshot:
                    raise RuntimeError('final process snapshot unavailable')
                receipt['surviving_pids'] = sorted(monitor.discover(snapshot, process.pid, known)) if known else []
            except BaseException as exc:
                receipt['final_snapshot_error'] = repr(exc)
                receipt['status'] = 'monitor_uncertain'
        if receipt['status'] == 'running' or receipt['status'] == 'starting':
            receipt['status'] = 'producer_exited'
        summary_path = results / 'summary.json'
        if summary_path.is_file():
            try:
                summary = read(summary_path)
                receipt['producer_status'] = summary.get('status')
                receipt['accepted_cells'] = summary.get('accepted_cells')
                receipt['in_flight'] = summary.get('in_flight')
                rows = summary.get('rows')
                receipt['accepted_rows'] = (len(rows) if isinstance(rows, list) and
                                            all(isinstance(row, dict) and row.get('status') == 'accepted'
                                                for row in rows) else None)
                receipt['summary_sha256'] = sha(summary_path)
            except BaseException as exc:
                receipt['summary_error'] = repr(exc)
        if (receipt['status'] == 'producer_exited' and receipt['exit_code'] == 0
                and receipt.get('producer_status') == 'completed'
                and receipt.get('accepted_cells') == 12
                and receipt.get('accepted_rows') == 12
                and receipt.get('in_flight') == []
                and not receipt['surviving_pids'] and not receipt.get('short_exit_before_identity')):
            receipt['status'] = 'completed'
        receipt['finished_at'] = utc()
        receipt['wall_seconds'] = time.monotonic() - start
        save(output / 'supervisor-receipt.json', receipt)
    if failure:
        raise RuntimeError('supervision failed; see receipt') from failure
    if receipt['status'] != 'completed':
        raise SystemExit(1)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'python', 'runner', 'manifest', 'raw-root', 'e2-root', 'gate', 'output'):
        parser.add_argument('--' + name, required=True)
    run(parser.parse_args())


if __name__ == '__main__':
    main()
