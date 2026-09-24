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
from core import batch_candidates, project_records
from composites import record_ids_digest
from app import make_handler, ui_bundle


def record(run,case,ratio=2,**changes):
    row={'id':run+case,'attempt_id':run+case,'revision':1,'run_id':run,'algorithm_id':'solver',
         'solver_commit':'a'*40,'problem':'P1','cores':5,'case_id':case,'status':'ok',
         'eligible':True,'baseline_verified':True,
         'provenance':{'solver':{'source':{'path':'src/solver.py','entrypoint':'main'}}},
         'metrics':{'makespan_cycles':100/ratio,'baseline_speedup':ratio,'solver_wall_seconds':.5}}
    row.update(changes)
    return row


class BatchTests(unittest.TestCase):
    def test_fixed_composite_uses_original_attempts_and_rejects_changed_bytes(self):
        members=tuple((f'fixed-s{i}',1+25*(i-1),25*i) for i in range(1,5))
        rows=[]
        for run,first,last in members:
            for n in range(first,last+1):
                case=f'{n:03d}'
                for core in range(1,6):
                    rows.append(record(run,case,id=f'id-{case}-{core}',
                        attempt_id=f'{run}-p2-{case}-k{core}',problem='P2',cores=core,
                        algorithm_id='fixed-solver',solver_commit='b'*40,
                        evaluator={'route':'E0'},baseline={'route':'E0'},
                        imported_at='2026-09-25T00:00:00+00:00'))
        spec={'id':'composite:fixed','label':'fixed collection','problem':'P2',
              'algorithm_id':'fixed-solver','solver_commit':'b'*40,
              'source_commit':'c'*40,'manifest_path':'results/fixed/manifest.json',
              'record_ids_sha256':record_ids_digest(rows),'members':members}
        result=batch_candidates(rows,'P2',5,['001'],composites=(spec,))
        candidate=next(r for r in result['batches'] if r['run_id']==spec['id'])
        self.assertTrue(candidate['full_complete'])
        self.assertTrue(candidate['composite_verified'])
        self.assertEqual(candidate['full_valid_count'],500)
        self.assertEqual(candidate['component_runs'],[m[0] for m in members])
        selected=project_records(rows,{'official_code_hash':'x','files':[]},1,{},run=spec['id'],composites=(spec,))
        cell=next(c for c in selected['cells'] if (c['problem'],c['case_id'],c['cores'])==('P2','001',1))
        self.assertEqual(cell['best']['run_id'],'fixed-s1')
        self.assertEqual(cell['best']['attempt_id'],'fixed-s1-p2-001-k1')
        self.assertIn(spec['id'],selected['runs'])

        changed=copy.deepcopy(rows);changed[0]['id']='different-original-bytes'
        invalid=batch_candidates(changed,'P2',5,['001'],composites=(spec,))
        candidate=next(r for r in invalid['batches'] if r['run_id']==spec['id'])
        self.assertFalse(candidate['composite_verified'])
        self.assertFalse(candidate['full_complete'])
        self.assertFalse(candidate['complete'])
        self.assertEqual(candidate['full_valid_count'],500)

        revised=copy.deepcopy(rows);revised.append(dict(rows[0],id='revision-two',revision=2))
        invalid=batch_candidates(revised,'P2',5,['001'],composites=(spec,))
        candidate=next(r for r in invalid['batches'] if r['run_id']==spec['id'])
        self.assertEqual(candidate['full_valid_count'],499)
        self.assertFalse(candidate['full_complete'])

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
        self.assertEqual({r['run_id'] for r in result['batches']},{'withdrawn','report','core','right'})
        self.assertTrue(all(r['valid_count']==0 for r in result['partial']))

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
        self.assertEqual(len(result['batches']),5)

    def test_full_problem_requires_same_run_and_source_across_all_500_cells(self):
        rows=[]
        for core in range(1,6):
            for n in range(1,101):
                case=f'{n:03d}'
                rows.append(record('full',case,core,id=f'full-{case}-{core}',
                                   attempt_id=f'full-{case}-{core}',cores=core,
                                   variant='structural-a' if n%2 else 'structural-b'))
        rows.append(record('partial','001',30))
        result=batch_candidates(rows,'P1',5,['001'])
        self.assertEqual(result['full_complete_count'],1)
        self.assertEqual(result['full'][0]['run_id'],'full')
        self.assertEqual(result['full'][0]['full_valid_count'],500)
        self.assertEqual(result['full'][0]['full_mean_speedup'],5)
        self.assertEqual(result['batches'][0]['run_id'],'full')
        self.assertFalse(result['batches'][1]['full_complete'])
        self.assertEqual(result['batches'][1]['mean_speedup'],30)
        self.assertEqual(result['batches'][1]['full_valid_count'],1)

    def test_repeated_attempt_in_one_cell_is_preview_until_selection_rule_is_audited(self):
        rows=[record('repeat',f'{n:03d}',core,id=f'{n}-{core}',attempt_id=f'{n}-{core}',cores=core)
              for core in range(1,6) for n in range(1,101)]
        rows.append(record('repeat','001',100,id='extra',attempt_id='extra',cores=5))
        result=batch_candidates(rows,'P1',5,['001'])
        self.assertEqual(result['full_complete_count'],0)
        self.assertEqual(result['batches'][0]['full_valid_count'],500)
        self.assertFalse(result['batches'][0]['one_attempt_per_cell'])
        self.assertFalse(result['batches'][0]['full_complete'])

    def test_all_full_runs_remain_searchable_when_top_three_is_truncated(self):
        rows=[record(f'run-{run}',f'{n:03d}',run,id=f'{run}-{n}-{core}',
                     attempt_id=f'{run}-{n}-{core}',cores=core)
              for run in range(1,5) for core in range(1,6) for n in range(1,101)]
        result=batch_candidates(rows,'P1',5,['001'])
        self.assertEqual(result['full_complete_count'],4)
        self.assertEqual([row['run_id'] for row in result['full']],['run-4','run-3','run-2'])
        self.assertEqual([row['run_id'] for row in result['batches']],['run-4','run-3','run-2','run-1'])

    def test_full_problem_coverage_does_not_hide_missing_baseline_ratio(self):
        rows=[]
        for core in range(1,6):
            for n in range(1,101):
                case=f'{n:03d}'
                rows.append(record('full',case,core,id=f'{case}-{core}',attempt_id=f'{case}-{core}',
                                   cores=core,baseline_verified=not(core==5 and n==100)))
        result=batch_candidates(rows,'P1',5,[f'{n:03d}' for n in range(1,101)])
        self.assertEqual(result['full_complete_count'],1)
        self.assertEqual(result['full'][0]['full_scored_count'],499)
        self.assertIsNone(result['full'][0]['full_mean_speedup'])

    def test_full_problem_with_multiple_solver_entrypoints_is_not_a_primary_batch(self):
        rows=[]
        for core in range(1,6):
            for n in range(1,101):
                case=f'{n:03d}'
                rows.append(record('mixed-entry',case,core,id=f'{case}-{core}',attempt_id=f'{case}-{core}',
                                   cores=core))
        rows[-1]['provenance']['solver']['source']['entrypoint']='other_main'
        result=batch_candidates(rows,'P1',5,[f'{n:03d}' for n in range(1,101)])
        self.assertEqual(result['full_complete_count'],0)
        self.assertEqual(result['batches'][0]['full_valid_count'],500)
        self.assertFalse(result['batches'][0]['fixed_entrypoint'])

    def test_all_problem_batches_remain_discoverable_without_selected_core_results(self):
        rows=[record('other-core','002',cores=2),record('failed','001',status='failed',eligible=False),
              record('outside-cases','050'),record('other-problem','001',problem='P3')]
        result=batch_candidates(rows,'P1',5,['001'])
        self.assertEqual({r['run_id'] for r in result['batches']},{'other-core','failed','outside-cases'})
        self.assertEqual(result['complete'],[])
        failed=next(r for r in result['batches'] if r['run_id']=='failed')
        self.assertEqual(failed['status_counts'],{'failed':1})
        self.assertEqual(failed['valid_count'],0)

    def test_focus_page_layout_scope_is_present_before_scripts_run(self):
        for problem in ('P1','P2','P3'):
            page,assets=ui_bundle(problem)
            self.assertIn(f'data-problem="{problem}"'.encode(),page)
            self.assertEqual(assets['ui_asset_id'],ui_bundle()[1]['ui_asset_id'])
            self.assertNotIn(b'<script>',page)
        self.assertNotIn(b'data-problem=',ui_bundle('P9')[0])

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
