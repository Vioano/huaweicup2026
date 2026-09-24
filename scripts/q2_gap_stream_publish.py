"""One-process, fail-stop watcher for a released P2 gap full500 run.

Never starts a solver/evaluator/sync daemon. Launch only after root release.
"""
from __future__ import annotations

import argparse
import fcntl
import gc
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from q2_gap_stream_export import ROOT, SOLVER, accepted_prefix, export, read, sha

FIRST = 'bbf42eff6d344c3f1c73f0461b1f05e99422b4b5'
FIRST_RANGE = (1, 50)
BRANCH = 'codex/q2-gap-archive-s8ee'


def utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def command(argv, cwd=ROOT):
    return subprocess.check_output(argv, cwd=cwd, text=True, timeout=120).strip()


def planned(start):
    if not 1 <= start <= 500:
        raise ValueError('start outside full500')
    if start <= 450:
        return start, min(((start-1)//50+1)*50, 450)
    if start <= 495:
        return start, min(((start-451)//5+1)*5+450, 495)
    return start, start


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    temp.replace(path)


def verify_checkout(branch):
    if command(['git', 'branch', '--show-current']) != branch:
        raise ValueError('Archive branch differs')
    if command(['git', 'diff', '--cached', '--name-only']):
        raise ValueError('Other staged files exist')
    for name in ('scripts/q2_gap_stream_export.py', 'scripts/q2_gap_stream_publish.py'):
        raw = (ROOT / name).read_bytes()
        committed = subprocess.check_output(['git', 'show', 'HEAD:'+name], cwd=ROOT)
        if raw != committed:
            raise ValueError('Exporter/publisher differs from HEAD: '+name)


def fixed_commit(folder):
    relative = folder.relative_to(ROOT).as_posix()
    return command(['git', 'log', '-1', '--format=%H', '--', relative])


def process_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def process_range(args, journal, summary, manifest, start, end, final):
    folder = args.output_root / f'shard-{start:03d}-{end:03d}'
    key = f'{start:03d}-{end:03d}'
    step = journal['ranges'].setdefault(key, {'range': [start, end], 'last_e0_utc':
                                             summary['rows'][end-1]['e0_process']['finished_at']})
    if (start, end) == FIRST_RANGE:
        if not folder.exists() or fixed_commit(folder) != FIRST:
            raise ValueError('First already-enqueued shard differs from fixed commit')
        if step.get('source') == 'preexisting_pushed_enqueued':
            return
        step.update(commit=FIRST, source='preexisting_pushed_enqueued',
                    recorded_utc=step.get('recorded_utc', utc()))
        atomic_json(args.journal, journal)
        return
    if 'enqueue_utc' in step:
        if fixed_commit(folder) != step['commit']:
            raise ValueError('Previously enqueued shard commit drift')
        return
    if 'feed' not in step:
        receipt = export(args.summary, args.manifest, args.output_root, args.run_id,
                         None, args.producer_session, args.task_url, args.runtime_id,
                         args.source_reference, final, start, end)
        step.update(feed=receipt['feed'], summary_sha256=receipt['summary_sha256'],
                    export_utc=utc())
        atomic_json(args.journal, journal)
    feed = ROOT / step['feed']
    if not feed.exists() or len(read(feed)['records']) != end-start+1:
        raise ValueError('Feed absent or count mismatch')
    if 'preflight_utc' not in step:
        raw = command([sys.executable, 'src/benchmark_board/protocol.py',
                       step['feed'], '--submission'])
        checked = json.loads(raw)
        if (not checked.get('valid') or checked.get('eligible') != end-start+1
                or checked.get('records') != end-start+1):
            raise ValueError('Board preflight did not accept every cell: '+raw[:500])
        step['preflight_utc'] = utc()
        atomic_json(args.journal, journal)
    if sys.platform == 'darwin':
        command(['dot_clean', str(folder)])
    if any(p.name.startswith('._') or p.name == '.DS_Store' for p in folder.rglob('*')):
        raise ValueError('Archive metadata remains after scoped cleanup')
    verify_checkout(args.branch)
    committed = fixed_commit(folder) if folder.exists() else ''
    if 'commit' not in step:
        if committed and command(['git', 'status', '--porcelain', '--', str(folder.relative_to(ROOT))]) == '':
            step.update(commit=committed, commit_utc=command(['git', 'show', '-s', '--format=%cI', committed]),
                        recovered_at_utc=utc(), recovered_commit=True)
        else:
            command(['git', 'add', '--', folder.relative_to(ROOT).as_posix()])
            staged = command(['git', 'diff', '--cached', '--name-only']).splitlines()
            prefix = folder.relative_to(ROOT).as_posix()+'/'
            if not staged or any(not p.startswith(prefix) for p in staged):
                raise ValueError('Unexpected staged path; publisher stops')
            command(['git', 'commit', '-q', '-m', f'Archive P2 gap full500 cells {key}'])
            step.update(commit=command(['git', 'rev-parse', 'HEAD']), commit_utc=utc())
        atomic_json(args.journal, journal)
    if fixed_commit(folder) != step['commit']:
        raise ValueError('Shard commit drift')
    if 'push_utc' not in step:
        command(['git', 'push', 'origin', f'HEAD:refs/heads/{args.branch}'])
        step['push_utc'] = utc()
        atomic_json(args.journal, journal)
    if 'enqueue_utc' not in step:
        delivery_id = command([str(args.sync_python), '-m', 'src.benchmark_sync', '--config',
                 str(args.sync_config), 'enqueue', '--repo', str(ROOT),
                 '--commit', step['commit'], '--feed', step['feed']], cwd=args.sync_root)
        if len(delivery_id) != 64 or any(c not in '0123456789abcdef' for c in delivery_id):
            raise ValueError('Enqueue returned no canonical delivery ID')
        step['delivery_id'] = delivery_id
        step['enqueue_utc'] = utc()
        atomic_json(args.journal, journal)
    print(json.dumps({'range': key, 'commit': step['commit'], 'enqueued_utc': step['enqueue_utc']}), flush=True)


def watch(args):
    if args.branch != BRANCH or not args.journal.is_relative_to(ROOT/'output'):
        raise ValueError('Publisher branch or journal area differs')
    verify_checkout(args.branch)
    producer_hashes = {name: sha((ROOT/name).read_bytes()) for name in (
        'scripts/q2_gap_stream_export.py', 'scripts/q2_gap_stream_publish.py')}
    manifest_raw = args.manifest.read_bytes()
    manifest = json.loads(manifest_raw)
    if len(manifest['rows']) != 500:
        raise ValueError('Expected fixed 500-coordinate manifest')
    first = args.output_root / 'shard-001-050'
    if (not first.exists() or fixed_commit(first) != FIRST
            or read(first/'snapshot.json')['run_id'] != args.run_id):
        raise ValueError('First fixed archive not present')
    journal = read(args.journal) if args.journal.exists() else {
        'run_id': args.run_id, 'branch': args.branch, 'manifest_sha256': sha(manifest_raw),
        'source_reference': args.source_reference, 'ranges': {}}
    if (journal['run_id'] != args.run_id or journal['branch'] != args.branch
            or journal['manifest_sha256'] != sha(manifest_raw)
            or journal['source_reference'] != args.source_reference):
        raise ValueError('Journal identity drift')
    broken_reads = 0
    while True:
        if any(sha((ROOT/name).read_bytes()) != expected for name, expected in producer_hashes.items()):
            raise ValueError('Running publisher/exporter bytes changed')
        try:
            summary = json.loads(args.summary.read_bytes())
        except (OSError, json.JSONDecodeError):
            broken_reads += 1
            if broken_reads > 3:
                raise ValueError('Summary unavailable after three polls')
            time.sleep(5)
            continue
        broken_reads = 0
        if (summary['manifest_sha256'] != sha(manifest_raw)
                or summary['solver_commit'] != SOLVER):
            raise ValueError('Source manifest drift')
        prefix = accepted_prefix(summary, manifest)
        done = len(prefix)
        terminated = summary['status'] != 'running'
        if not terminated and not process_alive(args.expected_scoring_pid):
            raise ValueError('Scoring PID missing while summary still running; uncertain')
        start = 1
        while start <= done:
            lo, planned_end = planned(start)
            if planned_end > done and not terminated:
                break
            end = min(planned_end, done)
            process_range(args, journal, summary, manifest, lo, end, terminated and end < planned_end)
            start = end + 1
        if terminated:
            journal['terminal_status'] = summary['status']
            journal['terminal_utc'] = utc()
            atomic_json(args.journal, journal)
            if summary['status'] != 'completed' or done != 500:
                raise ValueError(f'Scoring summary stopped: {summary["status"]}; accepted={done}')
            return
        # Do not retain a multi-GB decoded trace between polls, or while the
        # next snapshot is decoded. All durable progress is in the journal.
        del prefix, summary
        gc.collect()
        time.sleep(5)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('summary', 'manifest', 'output-root', 'journal', 'sync-root', 'sync-python', 'sync-config'):
        p.add_argument('--'+name, required=True, type=Path)
    for name in ('run-id', 'source-reference', 'producer-session', 'task-url', 'runtime-id'):
        p.add_argument('--'+name, required=True)
    p.add_argument('--expected-scoring-pid', required=True, type=int)
    p.add_argument('--branch', default=BRANCH)
    args = p.parse_args()
    for name in ('summary', 'manifest', 'output_root', 'journal', 'sync_root', 'sync_python', 'sync_config'):
        setattr(args, name, getattr(args, name).resolve())
    try:
        args.journal.parent.mkdir(parents=True, exist_ok=True)
        with args.journal.with_suffix('.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            watch(args)
    except Exception as error:
        print(json.dumps({'publisher_stopped': repr(error), 'scoring_untouched': True}), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
