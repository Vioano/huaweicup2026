"""Execute the nine authorized units once; the fixed approval ledger cannot reset."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

from .budget_search import PYTHON, ROOT, rel, save
from .job_control import run_job

RUN = ROOT/'results/a/q2-yuanzhifang/stage-b-20260924-042906'
UNITS = [f'{case}-{method}' for case in ('002','008','044') for method in ('D','M1','M2')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--units', nargs='+', choices=UNITS, default=UNITS)
    args = parser.parse_args()
    RUN.mkdir(parents=True, exist_ok=True)
    lock = RUN/'controller.lock'
    # Exclusive filesystem ownership. An interrupted owner is not auto-released.
    with lock.open('x', encoding='utf-8') as stream:
        stream.write(datetime.now(timezone.utc).isoformat())
    stage_file = RUN/'stage.json'
    try:
        if stage_file.exists():
            stage = json.loads(stage_file.read_text(encoding='utf-8'))
        else:
            stage = {'approval_id':'stage-b-20260924-042906', 'units':{},
                     'started_monotonic':time.monotonic(), 'started_utc':datetime.now(timezone.utc).isoformat(),
                     'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
                     'per_unit_calls':32,'per_unit_seconds':600,'total_calls':288,'total_seconds':5400}
            save(stage_file, stage)
        overall_deadline = stage['started_monotonic']+5400
        blocked_cases = {name.split('-')[0] for name, unit in stage['units'].items() if unit.get('baseline_failed')}
        for name in args.units:
            case, method = name.split('-')
            if name in stage['units']:
                print(json.dumps({'unit':name,'skipped':'already reserved; no ledger reset'}),flush=True)
                continue
            if case in blocked_cases:
                print(json.dumps({'unit':name,'skipped':'case baseline failed; needs coordination'}),flush=True)
                continue
            started = time.monotonic()
            if started >= overall_deadline:
                break
            deadline = min(started+600, overall_deadline)
            folder = RUN/name
            folder.mkdir(exist_ok=False)
            stage['units'][name] = {'status':'reserved','started_monotonic':started,
                                    'deadline_monotonic':deadline,'relative_folder':rel(folder)}
            save(stage_file, stage)
            command = [PYTHON,'-X','utf8','-B','-m','src.q2.budget_search','--folder',rel(folder),
                       '--case',case,'--method',method,'--started',str(started),'--deadline',str(deadline)]
            receipt = run_job(command,cwd=ROOT,folder=folder,started=started,deadline=deadline)
            receipt['command'] = ['python',*command[1:]]
            receipt_started = time.monotonic()
            save(folder/'controller.json',receipt)
            # Sample boundary after all unit evidence/hash writes AND process cleanup.
            # This small control-plane receipt is timed, not hidden as method setup.
            end = time.monotonic()
            accounting = {'wall_through_controller_receipt':end-started,
                          'controller_receipt_write_seconds':end-receipt_started,
                          'deadline_overshoot_seconds':max(0,end-deadline),
                          'measurement_boundary':'after controller.json fsync/replace; stage ledger control bookkeeping follows'}
            summary_path = folder/'summary.json'
            summary = json.loads(summary_path.read_text(encoding='utf-8')) if summary_path.exists() else {}
            accounting.update(status=receipt['status'], result_status=summary.get('status','incomplete'),
                              calls_charged=summary.get('calls_charged'), baseline_failed=summary.get('status')=='baseline_failed')
            stage['units'][name].update(accounting)
            save(stage_file,stage)
            ledger_done = time.monotonic()
            # Written to stdout and captured by caller; includes stage-ledger write as well.
            print(json.dumps({'unit':name,**accounting,'wall_through_stage_ledger':ledger_done-started,
                              'all_bookkeeping_overshoot':max(0,ledger_done-deadline)}),flush=True)
            if accounting['baseline_failed']:
                blocked_cases.add(case)
            if receipt['status'] in {'resource_limit','monitor_error','timeout'}:
                # Do not launch further work after a supervision failure.
                break
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
