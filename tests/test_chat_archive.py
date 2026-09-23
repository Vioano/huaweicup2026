import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('archive', Path(__file__).parents[1]/'scripts/export_chatgpt_archive.py')
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


class ArchiveIntegrity(unittest.TestCase):
    def fixture(self):
        cap={'conversation_id':'c','title':'chat','url':'https://chatgpt.com/c/c','exported_at':'2026-09-24T00:00:00Z',
             'verification':{'timed_out':False,'streaming':False,'stable_top_samples':3},
             'messages':[{'id':'u','role':'user','html':'<p>question</p>'},{'id':'a','role':'assistant','html':'<p>complete final answer</p>'}]}
        nat={'id':'c','page':{'hasMore':False},'turns':[{'items':[{'id':'u','type':'userMessage','content':[{'text':'question'}]}, {'id':'a','type':'agentMessage','text':'answer'}]}]}
        return cap,nat

    def test_missing_history_and_changed_order_are_rejected(self):
        cap,nat=self.fixture();cap['messages'].pop(0)
        self.assertTrue(archive.validate(cap,nat))
        cap,nat=self.fixture();cap['messages'].reverse()
        self.assertTrue(archive.validate(cap,nat))

    def test_more_pages_and_live_generation_are_not_complete(self):
        cap,nat=self.fixture();nat['page']['hasMore']=True
        self.assertTrue(archive.validate(cap,nat))
        nat['page']['hasMore']=False;cap['verification']['streaming']=True
        self.assertTrue(archive.validate(cap,nat))

    def test_capped_native_answer_uses_dom_and_refuses_overwrite(self):
        cap,nat=self.fixture();nat['turns'][0]['items'][1]['text']='x'*20000
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'chat.md';archive.export(cap,out,nat)
            self.assertIn('complete final answer',out.read_text())
            self.assertNotIn('x'*100,out.read_text())
            with self.assertRaises(FileExistsError):archive.export(cap,out,nat)

    def test_math_code_and_table_survive_conversion(self):
        html='<span role="math" data-math-source="A \\otimes B" style="display: block;"><span class="katex-display">visual duplicate</span></span><pre><code>if a &lt; b:\n    f()</code></pre><table><tr><th>x</th></tr><tr><td>1</td></tr></table>'
        md=archive.dom_markdown(html)
        self.assertIn('$$A \\otimes B$$',md);self.assertNotIn('visual duplicate',md)
        self.assertIn('if a < b:\n    f()',md);self.assertIn('| --- |',md)

    def test_restore_checks_original_byte_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'p0').write_bytes(b'one');(root/'p1').write_bytes(b'two')
            archive.restore([root/'p0',root/'p1'],root/'zip',archive.hashlib.sha256(b'onetwo').hexdigest())
            self.assertEqual((root/'zip').read_bytes(),b'onetwo')
            with self.assertRaises(ValueError):archive.restore([root/'p1',root/'p0'],root/'bad','0'*64)


if __name__=='__main__':unittest.main()
