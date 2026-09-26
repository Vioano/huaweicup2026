"""Acceptance transitions and source integrity; no network or evaluator calls."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.paper_acceptance.core import Board, Conflict, MARKER, ROOT
from src.paper_acceptance.app import Documents, TeamImages
from src.paper_acceptance.language import scan_text, import_author_report


class ReviewContractTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.pdf = self.root / 'paper.pdf'; self.pdf.write_bytes(b'fixed source')
        self.cat = {'paper_sha256': hashlib.sha256(self.pdf.read_bytes()).hexdigest(),
                    'paper_commit': 'a'*40, 'standard_version': '1', 'repo': 'huaweibei123/huaweicup2026',
                    'issue': 217, 'members': ['author', 'reviewer', 'leader'], 'leader': 'leader',
                    'items': [{'id': 'L01', 'initial_state': 'needs_work', 'checks': ['full words', 'sources', 'scope']}],
                    'documents': [{'id': 'current', 'path': str(self.pdf), 'pages': 1,
                                   'sha256': hashlib.sha256(self.pdf.read_bytes()).hexdigest()}]}
        self.path = self.root / 'catalogue.json'; self.path.write_text(json.dumps(self.cat))
        self.board = Board(self.root / 'state', self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_team_figure_manifest_and_blob_integrity(self):
        gallery = TeamImages(self.board)
        self.assertEqual(len(gallery.by_id), 41)
        self.assertTrue(gallery.by_id['fang-fig42-a']['curation_priority'])
        self.assertEqual(len({item['family'] for item in gallery.by_id.values()}), 22)
        self.assertEqual(gallery.by_id['fang-fig41']['number'], '图 4.1-1')
        self.assertTrue(all(item['number'].startswith('图 ') for item in gallery.by_id.values()))
        raw = b'\x89PNG\r\n\x1a\nexample'
        item = {'size_bytes': len(raw), 'git_blob_sha1': hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}
        self.assertEqual(TeamImages.checked(raw, item), raw)
        with self.assertRaisesRegex(ValueError, '哈希'):
            TeamImages.checked(raw[:-1]+b'X', item)

    def test_checkpoint_registry_keeps_new_freeze_separate_from_review_baseline(self):
        registry = json.loads((ROOT / 'docs/paper-acceptance/checkpoint-status.json').read_text())
        by_id = {item['id']: item for item in registry['checkpoints']}
        self.assertEqual(by_id[registry['acceptance_baseline']]['pdf_sha256'],
                         json.loads((ROOT / 'docs/paper-acceptance/catalogue.json').read_text())['paper_sha256'])
        self.assertNotEqual(by_id[registry['latest_known_checkpoint']]['pdf_sha256'],
                            by_id[registry['acceptance_baseline']]['pdf_sha256'])
        self.assertIn(by_id['CP06']['git_commit'], by_id['CP06']['public_pdf_url'])
        self.assertEqual(len({by_id[x]['pdf_sha256'] for x in ('CP04', 'CP05', 'CP06')}), 3)

    def values(self, decision='comment', revision=0, actor='author'):
        return dict(item_id='L01', paper_sha256=self.cat['paper_sha256'], standard_hash=self.board.standard_hash,
                    expected_revision=revision, decision=decision, note='Checked the fixed paper and linked source.',
                    evidence=['https://github.com/huaweibei123/huaweicup2026/blob/'+'a'*40+'/paper/fixed.pdf'],
                    checks=[True]*3, session=actor+'/s-unit')

    def event(self, decision='comment', revision=0, actor='author'):
        return self.board.draft(self.values(decision, revision, actor), actor)

    def comment(self, event, cid, actor='author'):
        body=MARKER+'\n```json\n'+json.dumps(event)+'\n```'
        return dict(id=cid, body=body, user={'login': actor}, created_at='2026-09-26T01:00:00Z',
                    updated_at='2026-09-26T01:00:00Z', html_url=f'https://github.com/example/issuecomment-{cid}')

    def test_draft_does_not_approve(self):
        self.event('ready')
        state=self.board.snapshot()['items'][0]
        self.assertEqual((state['state'],state['revision']),('needs_work',0))

    def test_full_distinct_account_transition(self):
        a=self.comment(self.event('ready'),1)
        self.board.ingest_comments([a])
        b=self.comment(self.event('verified',1,'reviewer'),2,'reviewer')
        self.board.ingest_comments([a,b])
        c=self.comment(self.event('accepted',2,'leader'),3,'leader')
        self.assertTrue(self.board.ingest_comments([a,b,c])['all_accepted'])

    def test_same_account_new_session_is_not_independent(self):
        a=self.comment(self.event('ready'),1); self.board.ingest_comments([a])
        v=self.values('verified',1); v['session']='author/s-different'
        with self.assertRaisesRegex(ValueError,'独立复核'): self.board.draft(v,'author')

    def test_cannot_skip_independent_review(self):
        with self.assertRaises(ValueError): self.event('accepted',0,'leader')

    def test_concurrent_stale_review_is_retained_as_conflict(self):
        a,b=self.event(),self.event('needs_work')
        result=self.board.ingest_comments([self.comment(a,1),self.comment(b,2)])
        self.assertEqual(result['items'][0]['revision'],1)
        self.assertEqual(result['reviews'][1]['disposition'],'conflict')

    def test_new_paper_invalidates_old_acceptance(self):
        a=self.comment(self.event('ready'),1); self.board.ingest_comments([a])
        self.cat['paper_sha256']='b'*64; self.path.write_text(json.dumps(self.cat))
        new=Board(self.board.state,self.path).snapshot()
        self.assertEqual(new['items'][0]['revision'],0)
        self.assertEqual(new['reviews'][0]['disposition'],'conflict')

    def test_new_standard_invalidates_old_review(self):
        a=self.comment(self.event('ready'),1); self.board.ingest_comments([a])
        self.cat['standard_version']='2'; self.path.write_text(json.dumps(self.cat))
        self.assertEqual(Board(self.board.state,self.path).snapshot()['items'][0]['revision'],0)

    def test_missing_checks_and_moving_branch_are_rejected(self):
        v=self.values('ready'); v['checks'][0]=False
        with self.assertRaises(ValueError): self.board.draft(v,'author')
        v=self.values('ready'); v['evidence']=['https://github.com/huaweibei123/huaweicup2026/blob/main/paper.pdf']
        with self.assertRaises(ValueError): self.board.draft(v,'author')

    def test_comment_author_cannot_forge_session_identity(self):
        e=self.event(); self.board.ingest_comments([self.comment(e,1,'outsider')])
        self.assertEqual(self.board.snapshot()['items'][0]['revision'],0)

    def test_edited_source_invalidates_and_fresh_client_does_not_apply(self):
        a=self.comment(self.event('ready'),1); self.board.ingest_comments([a])
        a['body']+=' changed'; a['updated_at']='2026-09-26T02:00:00Z'
        self.assertEqual(self.board.ingest_comments([a])['items'][0]['revision'],0)
        fresh=Board(self.root/'fresh',self.path)
        self.assertEqual(fresh.ingest_comments([a])['items'][0]['revision'],0)

    def test_deleted_source_invalidates_dependent_review(self):
        a=self.comment(self.event('ready'),1); self.board.ingest_comments([a])
        b=self.comment(self.event('verified',1,'reviewer'),2,'reviewer'); self.board.ingest_comments([a,b])
        s=self.board.ingest_comments([b])
        self.assertEqual(s['items'][0]['state'],'needs_work')
        self.assertTrue(all(r['disposition']=='conflict' for r in s['reviews']))

    def test_repeated_sync_is_idempotent(self):
        c=self.comment(self.event(),1)
        self.board.ingest_comments([c]); self.board.ingest_comments([c])
        self.assertEqual(self.board.snapshot()['items'][0]['revision'],1)

    def test_uncertain_delivery_is_not_blindly_reposted(self):
        e=self.event()
        with self.board.db() as db: db.execute("UPDATE events SET disposition='uncertain'")
        with patch.object(self.board,'authenticate',return_value='author'), patch.object(self.board,'sync'):
            with self.assertRaisesRegex(ValueError,'不自动重发'): self.board.publish(e['id'])

    def test_shared_record_reconciliation_prevents_duplicate_post(self):
        e=self.event(); c=self.comment(e,1)
        with patch.object(self.board,'authenticate',return_value='author'), patch.object(self.board,'sync',side_effect=lambda:self.board.ingest_comments([c])):
            self.assertEqual(self.board.publish(e['id'])['url'],c['html_url'])

    def test_pdf_change_is_rejected_before_cached_render(self):
        d=Documents(self.board); d.locate('current')
        self.pdf.write_bytes(b'changed source with another length')
        with self.assertRaisesRegex(ValueError,'字节已变化'): d.locate('current')

    def test_scanner_does_not_flag_cross_core_sync_or_generic_verification(self):
        rules=[dict(term='(?<!跨)(?<!同)核同(?!步)',kind='优先审改',issue='test',requirement='test'),
               dict(term='核对(?=联合|与最多|比较)',kind='优先审改',issue='test',requirement='test')]
        e=scan_text('跨核同步。同核同 Pipe。重新核对工作量。字节核对。逐格核同。核对联合比较。',rules,'a'*64)
        self.assertEqual([x['term'] for x in e],['核同','核对'])
        for x in e: self.assertEqual(x['original'][x['match_start']:x['match_end']],x['term'])

    def test_author_self_report_does_not_change_acceptance(self):
        report={'schema_version':1,'paper_sha256':self.cat['paper_sha256'],
                'entries':[dict(chapter='a',line=1,original='old',issue='unclear',replacement='new',source='standard',status='accepted')]}
        with patch('src.paper_acceptance.language.subprocess.run') as run:
            run.return_value.stdout=json.dumps(report).encode()
            receipt=import_author_report(self.board,'c'*40,'paper/review.json')
        self.assertFalse(receipt['acceptance_changed'])
        self.assertEqual(self.board.snapshot()['items'][0]['state'],'needs_work')

    def test_import_refuses_wrong_baseline(self):
        with patch('src.paper_acceptance.language.subprocess.run') as run:
            run.return_value.stdout=json.dumps({'schema_version':1,'paper_sha256':'f'*64,'entries':[]}).encode()
            with self.assertRaisesRegex(ValueError,'哈希不同'): import_author_report(self.board,'c'*40,'paper/review.json')

class SemanticReportTests(unittest.TestCase):
    def test_annotation_identity_and_class_origin_are_required(self):
        from src.paper_acceptance.semantic import validate_workflow
        e={'annotation_id':'a1','event_key':'b'*64+':a1','source_commit':'a'*40,'paper_sha256':'b'*64,
           'original':'原文','user_comment_verbatim':'用户批注','page':1,'rect':[1,2,3,4]}
        c={'id':'c1','annotation_ids':['a1'],'title':'类别','mechanism':'缺陷','scope':['正文'],
           'positive_example':'实例','negative_example':'非实例','rules':['L07'],'coverage_status':'未完成'}
        data={'schema_version':2,'events':[e],'issue_classes':[c]}
        self.assertFalse(validate_workflow(data)['acceptance_changed'])
        data['events'].append(dict(e))
        with self.assertRaisesRegex(ValueError,'重复'):validate_workflow(data)
        data['events'].pop();c['annotation_ids']=['unknown']
        with self.assertRaisesRegex(ValueError,'回指'):validate_workflow(data)

    def packet(self):
        return {'source_commit':'a'*40,'standard_version':'2026-09-26.4',
                'entries':[{'id':'u1','path':'paper/ch.md','line':3,'line_end':3,'original':'待审原句。'}]}

    def report(self):
        return {'source_commit':'a'*40,'standard_version':'2026-09-26.4','worker':'sol-a',
                'coverage':[{'unit_id':'u1','assessment':'findings'}],
                'findings':[{'id':'f1','unit_id':'u1','path':'paper/ch.md','line':3,'original':'待审原句。','rules':['L13']}]}

    def test_old_version_cannot_be_attached_to_new_text(self):
        from src.paper_acceptance.semantic import combine_reports
        r=self.report();r['source_commit']='b'*40
        with self.assertRaisesRegex(ValueError,'新旧稿'):combine_reports([self.packet()],[r])

    def test_invented_quote_and_missing_coverage_are_rejected(self):
        from src.paper_acceptance.semantic import combine_reports
        r=self.report();r['findings'][0]['original']='不存在的原句'
        with self.assertRaisesRegex(ValueError,'连续原文'):combine_reports([self.packet()],[r])
        r=self.report();r['coverage']=[]
        with self.assertRaisesRegex(ValueError,'覆盖清单'):combine_reports([self.packet()],[r])

    def test_worker_acceptance_claim_is_not_imported(self):
        from src.paper_acceptance.semantic import combine_reports
        r=self.report();r['coverage'][0]['assessment']='accepted'
        with self.assertRaisesRegex(ValueError,'最终通过'):combine_reports([self.packet()],[r])
        result=combine_reports([self.packet()],[self.report()])
        self.assertEqual(result['findings'][0]['supervisor_status'],'pending')
        self.assertEqual(result['findings'][0]['author_status'],'not_delivered')

if __name__=='__main__': unittest.main()
