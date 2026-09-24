"""Offline command-order and interrupted-push fixture; no Git/network/scoring calls."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import q2_gap_stream_publish as publisher


def test_schedule_boundaries():
    assert publisher.planned(1) == (1, 50)
    assert publisher.planned(450) == (450, 450)
    assert publisher.planned(451) == (451, 455)
    assert publisher.planned(495) == (495, 495)
    assert publisher.planned(496) == (496, 496)
    assert publisher.planned(500) == (500, 500)


def test_commit_push_interruption_then_idempotent_resume():
    with tempfile.TemporaryDirectory(dir=publisher.ROOT / 'results/a/q2-nikolastarx') as tmp:
        root = Path(tmp)
        output = root / 'archive'
        folder = output / 'shard-051-055'
        feed = folder / 'board-feed.json'
        args = SimpleNamespace(output_root=output, journal=root / 'journal.json',
                               summary=root/'summary.json', manifest=root/'manifest.json',
                               run_id='fixture', producer_session='fixture/session',
                               task_url='https://github.com/huaweibei123/huaweicup2026/issues/33',
                               runtime_id='fixture', source_reference='fixture/summary.json',
                               branch=publisher.BRANCH, sync_python=root/'python',
                               sync_config=root/'config', sync_root=root)
        summary = {'rows': [{'e0_process': {'finished_at': '2026-09-25T00:00:00Z'}}
                            for _ in range(55)]}
        journal = {'ranges': {}}
        calls = []
        state = {'committed': False, 'pushes': 0}
        sha = 'a'*40

        def fake_export(*_a):
            folder.mkdir(parents=True, exist_ok=True)
            feed.write_text(json.dumps({'records': [{}]*5}))
            return {'feed': feed.relative_to(publisher.ROOT).as_posix(),
                    'summary_sha256': 'b'*64}

        def fake_command(argv, cwd=publisher.ROOT):
            calls.append(tuple(str(x) for x in argv))
            if 'protocol.py' in ' '.join(str(x) for x in argv):
                return json.dumps({'valid': True, 'eligible': 5, 'records': 5})
            if argv[:3] == ['git', 'diff', '--cached']:
                return folder.relative_to(publisher.ROOT).as_posix()+'/board-feed.json'
            if argv[:2] == ['git', 'commit']:
                state['committed'] = True
            if argv[:2] == ['git', 'rev-parse']:
                return sha
            if argv[:2] == ['git', 'push']:
                state['pushes'] += 1
                if state['pushes'] == 1:
                    raise RuntimeError('synthetic interrupted push')
            if 'src.benchmark_sync' in argv:
                return 'c'*64
            return ''

        with (patch.object(publisher, 'export', fake_export),
              patch.object(publisher, 'command', fake_command),
              patch.object(publisher, 'verify_checkout', lambda _branch: None),
              patch.object(publisher, 'fixed_commit', lambda _folder: sha if state['committed'] else '')):
            try:
                publisher.process_range(args, journal, summary, {}, 51, 55, False)
            except RuntimeError as error:
                assert 'interrupted push' in str(error)
            else:
                raise AssertionError('synthetic interruption was swallowed')
            assert journal['ranges']['051-055']['commit'] == sha
            publisher.process_range(args, journal, summary, {}, 51, 55, False)
            before = len(calls)
            publisher.process_range(args, journal, summary, {}, 51, 55, False)
            assert len(calls) == before
        assert sum(call[:2] == ('git', 'commit') for call in calls) == 1
        assert sum(call[:2] == ('git', 'push') for call in calls) == 2
        assert sum('src.benchmark_sync' in call for call in calls) == 1
        assert journal['ranges']['051-055']['delivery_id'] == 'c'*64
