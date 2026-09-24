import copy
import json
import sys
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
from urllib.error import HTTPError

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src/benchmark_board'))
from core import batch_candidates
from app import make_handler


def record(run,case,ratio=2,**changes):
    row={'id':run+case,'attempt_id':run+case,'revision':1,'run_id':run,'algorithm_id':'solver',
         'solver_commit':'a'*40,'problem':'P1','cores':5,'case_id':case,'status':'ok',
         'eligible':True,'baseline_verified':True,
         'metrics':{'makespan_cycles':100/ratio,'baseline_speedup':ratio,'solver_wall_seconds':.5}}
    row.update(changes)
    return row


class BatchTests(unittest.TestCase):
    def test_partial_cherry_picked_batch_cannot_outrank_full_batch(self):
        rows=[record('full','001',1),record('full','002',3),record('partial','001',50)]
        result=batch_candidates(rows,'P1',5,['001','002'])
        self.assertEqual([r['run_id'] for r in result['complete']],['full'])
        self.assertEqual(result['complete'][0]['mean_speedup'],2)
        self.assertEqual(result['partial'][0]['scored_count'],1)
        self.assertEqual(result['partial'][0]['missing_cases'],['002'])

    def test_runs_are_never_stitched_and_coverage_is_distinct_cases(self):
        a=record('one','001');duplicate=copy.deepcopy(a);duplicate.update(id='duplicate',attempt_id='duplicate')
        result=batch_candidates([a,duplicate,record('two','002')],'P1',5,['001','002'])
        self.assertEqual(result['complete'],[])
        self.assertEqual([r['valid_count'] for r in result['partial']],[1,1])

    def test_withdrawn_revision_report_and_wrong_scope_do_not_rank(self):
        old=record('withdrawn','001');new=copy.deepcopy(old);new.update(revision=2,status='withdrawn',eligible=False)
        rows=[old,new,record('report','001',100,eligible=False),record('other','001',100,problem='P2'),
              record('core','001',100,cores=4),record('right','001',2)]
        result=batch_candidates(rows,'P1',5,['001'])
        self.assertEqual([r['run_id'] for r in result['complete']],['right'])
        self.assertEqual(result['partial'],[])

    def test_missing_baseline_does_not_substitute_a_worse_plan(self):
        best=record('run','001',3,baseline_verified=False)
        worse=record('run','001',2,id='worse',attempt_id='worse')
        result=batch_candidates([best,worse],'P1',5,['001'])
        self.assertEqual(result['complete'],[])
        self.assertEqual(result['partial'][0]['scored_count'],0)
        self.assertIsNone(result['partial'][0]['mean_speedup'])

    def test_mixed_algorithm_or_version_run_is_labelled_not_ranked(self):
        for change in ({'algorithm_id':'other'},{'solver_commit':'b'*40}):
            with self.subTest(change=change):
                result=batch_candidates([record('mixed','001'),record('mixed','002',**change)],'P1',5,['001','002'])
                self.assertEqual(result['complete'],[])
                self.assertFalse(result['partial'][0]['single_source'])

    def test_current_case_scope_and_top_three_are_explicit(self):
        rows=[record(str(i),'002',i+1) for i in range(5)]
        result=batch_candidates(rows,'P1',5,['002'])
        self.assertEqual(result['complete_count'],5)
        self.assertEqual([r['run_id'] for r in result['complete']],['4','3','2'])
        self.assertEqual(result['case_ids'],['002'])

    def test_http_uses_common_read_only_record_contract_and_validates_scope(self):
        rows=[record('a','001')]
        class ReadOnly:
            def records(self):return copy.deepcopy(rows)
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(ReadOnly()))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        base=f'http://127.0.0.1:{server.server_port}/api/v1/batches'
        with urlopen(base+'?problem=P1&cores=5&cases=001') as response:
            self.assertEqual(json.load(response),batch_candidates(rows,'P1',5,['001']))
        for query in ('cores=6','problem=P9','cases=999'):
            with self.assertRaises(HTTPError) as error:urlopen(base+'?'+query)
            self.assertEqual(error.exception.code,400)


if __name__=='__main__':unittest.main()
