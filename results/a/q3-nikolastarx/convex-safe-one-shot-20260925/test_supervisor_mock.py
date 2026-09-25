"""Three pure-mock cases; no child process, evaluator, Task, or Step."""
import json
from pathlib import Path
import sys
from unittest import mock
import convex_supervisor as sup

def test_resource_rules():
    entry = {'pressure_level': 1, 'other_scorers': [], 'disk_free_bytes': 12*1024**3,
             'owned_rss_bytes': 0, 'swap_used_mib': 1000, 'physical_free_bytes': 1}
    assert sup.guard(entry, 1000, start=True) is None
    for field, value in [('pressure_level', 2), ('disk_free_bytes', 9*1024**3),
                         ('owned_rss_bytes', 2*1024**3+1), ('swap_used_mib', 1256.01),
                         ('other_scorers', [{'pid': 9}])]:
        assert sup.guard({**entry, field: value}, 1000) is not None
    print('resource: pressure/disk/RSS/swap/conflict stop; low physical free observed')

def test_terminal_identity():
    class Ended:
        pid = 101
        returncode = None
        def wait(self, timeout):
            assert timeout == 10
            self.returncode = 0
    parent = {'pid': 101, 'ppid': 1, 'pgid': 101, 'args': 'zombie'}
    worker = {'pid': 202, 'ppid': 1, 'pgid': 202, 'args': 'worker'}
    with mock.patch.object(sup.identity_guard, 'processes', return_value=[parent]), mock.patch.object(
            sup.identity_guard, 'identity', side_effect=AssertionError('zombie identity read')), mock.patch.object(
            sup.os, 'killpg') as kill:
        report = {'status': 'running'}
        sup.finish_exited(Ended(), {101: (1, 1)}, report)
        assert report['status'] == 'complete'
        kill.assert_not_called()
    for current in ((2, 2), (3, 3), None):
        with mock.patch.object(sup.identity_guard, 'processes', return_value=[parent, worker]), mock.patch.object(
                sup.identity_guard, 'identity', return_value=current), mock.patch.object(
                sup.os, 'getpgrp', return_value=999), mock.patch.object(sup.os, 'killpg') as kill:
            report = {'status': 'running'}
            if current == (2, 2):
                sup.finish_exited(Ended(), {101: (1, 1), 202: (2, 2)}, report)
                kill.assert_called_once_with(202, sup.signal.SIGKILL)
                assert report['status'] == 'failed'
            else:
                try:
                    sup.finish_exited(Ended(), {101: (1, 1), 202: (2, 2)}, report)
                except RuntimeError:
                    pass
                else:
                    raise AssertionError('unverified group accepted')
                kill.assert_not_called()
    print('identity: exited zombie safe; verified residual targeted; reuse/unknown refused')

def test_unapproved_no_spawn():
    manifest = {'execution_authorized': False}
    with mock.patch.object(sys, 'argv', ['convex_supervisor.py', '--manifest', '/never.json']), mock.patch.object(
            Path, 'read_text', return_value=json.dumps(manifest)), mock.patch.object(
            sup, 'verify_manifest', return_value=manifest), mock.patch.object(
            sup.subprocess, 'Popen') as popen, mock.patch.object(Path, 'mkdir') as mkdir:
        try:
            sup.main()
        except PermissionError:
            pass
        else:
            raise AssertionError('unapproved manifest accepted')
        popen.assert_not_called()
        mkdir.assert_not_called()
    print('authorization: false manifest dispatched zero child processes')

if __name__ == '__main__':
    test_resource_rules()
    test_terminal_identity()
    test_unapproved_no_spawn()
    print('3 pure-mock supervisor cases passed; 0 real child/E0/Task/Step')
