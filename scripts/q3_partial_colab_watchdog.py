"""Independent host guard for one named Colab session; no allocation or retries.

The stop attempt starts at the controller's absolute 600s deadline. Parent EOF
does not cancel it or stop early: allocation may still be in flight when its
caller dies. Its CLI timeout is bounded at 25s; failure leaves state unknown.
"""
import argparse
import json
import os
from pathlib import Path
import select
import subprocess
import time

SESSION = 'q3-partial-044-20260925'
EMPTY = '[colab] No active sessions found on server.'


def empty_sessions(stdout, stderr):
    return (stdout.strip() == EMPTY and not stderr.strip()) or (stderr.strip() == EMPTY and not stdout.strip())


def write_receipt(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(temporary, path)


def cli_call(cli, args, timeout):
    try:
        result = subprocess.run([str(cli), '--auth', 'oauth2', *args],
                                capture_output=True, text=True, timeout=timeout)
        return {'returncode': result.returncode, 'stdout': result.stdout,
                'stderr': result.stderr}
    except subprocess.TimeoutExpired as error:
        return {'returncode': None, 'timeout': timeout,
                'stdout': str(error.stdout or ''), 'stderr': str(error.stderr or '')}
    except OSError as error:
        return {'returncode': None, 'error': type(error).__name__ + ': ' + str(error)}


def cleanup(cli, receipt_path, trigger):
    receipt = {'session': SESSION, 'trigger': trigger, 'status': 'stop_unknown',
               'attempted_at_monotonic': time.monotonic()}
    stop = cli_call(cli, ['stop', '--session', SESSION], 25)
    receipt['stop'] = stop
    if stop['returncode'] == 0:
        sessions = cli_call(cli, ['sessions'], 10)
        receipt['sessions_after'] = sessions
        if sessions['returncode'] == 0 and empty_sessions(sessions['stdout'], sessions['stderr']):
            receipt['status'] = 'stopped_confirmed'
    write_receipt(receipt_path, receipt)
    return receipt


def guard(cli, receipt_path, arm_fd, ready_fd, absolute_deadline):
    os.write(ready_fd, b'READY\n')
    os.close(ready_fd)
    stop_due = absolute_deadline
    parent_gone = False
    try:
        while True:
            remaining = stop_due - time.monotonic()
            if remaining <= 0:
                return cleanup(cli, receipt_path, 'parent_exit_absolute_deadline'
                               if parent_gone else 'absolute_deadline')
            if parent_gone:
                time.sleep(min(remaining, 0.25))
                continue
            readable, _, _ = select.select([arm_fd], [], [], min(remaining, 0.25))
            if readable:
                command = os.read(arm_fd, 1)
                if command == b'D':
                    receipt = {'session': SESSION, 'status': 'disarmed_by_confirmed_parent',
                               'at_monotonic': time.monotonic()}
                    write_receipt(receipt_path, receipt)
                    return receipt
                parent_gone = True
                write_receipt(receipt_path, {'session': SESSION,
                    'status': 'armed_after_parent_exit', 'absolute_deadline': absolute_deadline})
    finally:
        os.close(arm_fd)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cli', type=Path, required=True)
    p.add_argument('--receipt', type=Path, required=True)
    p.add_argument('--arm-fd', type=int, required=True)
    p.add_argument('--ready-fd', type=int, required=True)
    p.add_argument('--deadline', type=float, required=True)
    a = p.parse_args()
    guard(a.cli, a.receipt, a.arm_fd, a.ready_fd, a.deadline)


if __name__ == '__main__':
    main()
