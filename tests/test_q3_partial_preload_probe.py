"""Three call-routing tests using fake subprocesses; zero official calls."""
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.q3 import partial_preload_probe as probe
from src.q3.partial_preload_prepare import BUDGET
from scripts import q3_prefix_linux_supervisor as linux


class RoutingTests(unittest.TestCase):
    def exercise(self, value, prepare_failed=False):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            candidate = base / 'candidate'
            candidate.mkdir()
            output = base / 'run'
            phases = []
            def fake_supervise(argv, out, phase, deadline, swaps, budget):
                phases.append(phase)
                if phase == 'prepare':
                    target = out / 'prepare'
                    target.mkdir()
                    (target / 'prepared.json.gz').write_bytes(gzip.compress(b'{}'))
                    probe.write(target / 'run.json', {
                        'status': 'complete', 'counts_started': {'Step1':5,'Step2':5,'Step3':5,'Task':1},
                        'prepared_sha256': probe.digest(target / 'prepared.json.gz')})
                    return {'status': 'failed' if prepare_failed else 'complete'}
                result = out / f'{phase}.json.gz'
                score = value if phase == 'candidate-p3' else 42000
                result.write_bytes(gzip.compress(json.dumps({'makespan':score,
                    'data_movement_bytes':{},'cache_stats':{}}).encode()))
                probe.write(out / f'{phase}.worker.json', {'status':'complete',
                    'counts_started':probe.limits(3 if phase=='candidate-p3' else 2),
                    'result_sha256':probe.digest(result)})
                return {'status':'complete'}
            args = ['probe',str(candidate),str(output),'--source','a'*40,
                    '--manifest-sha256','b'*64,'--admission-ref','MOCK']
            with patch.object(probe,'BASE',base), patch.object(probe,'ROOT',Path.cwd()), \
                 patch.object(probe.sys,'argv',args), patch.object(probe.sys,'platform','linux'), \
                 patch('src.q3.partial_preload_prepare.load_candidate',return_value=({'budget':BUDGET},)), \
                 patch.object(probe,'verify_source',return_value=('official',{})), \
                 patch.object(probe,'control_result',return_value={'makespan':38024,
                       'data_movement_bytes':{},'cache_stats':{}}), \
                 patch.object(linux,'host_observation',return_value={'mem_available_mib':2048,'swapouts':0}), \
                 patch.object(linux,'supervise',side_effect=fake_supervise), \
                 patch.object(probe.subprocess,'Popen') as child:
                child.return_value.wait.return_value=0
                if prepare_failed:
                    with self.assertRaisesRegex(RuntimeError,'prepare'):probe.main()
                else:probe.main()
            return phases, probe.read(output/'run.json')

    def test_no_gain_spends_only_one_score(self):
        phases, receipt = self.exercise(38024)
        self.assertEqual(phases,['prepare','candidate-p3'])
        self.assertIsNone(receipt['candidate_G'])

    def test_gain_gets_two_exact_pairs(self):
        phases, receipt = self.exercise(37000)
        self.assertEqual(phases,['prepare','candidate-p3','candidate-p2','control-p2'])
        self.assertAlmostEqual(receipt['candidate_G'],42000/37000)
        self.assertAlmostEqual(receipt['control_G'],42000/38024)

    def test_failed_prepare_never_scores(self):
        phases, receipt = self.exercise(37000,True)
        self.assertEqual(phases,['prepare'])
        self.assertEqual(receipt['status'],'failed')


if __name__=='__main__':unittest.main()
