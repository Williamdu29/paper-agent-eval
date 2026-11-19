"""Offline fixtures only. No real provider calls or third-party PDFs."""
from contextlib import redirect_stdout,redirect_stderr
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from paper_agent_eval.contracts import Input,Result
from paper_agent_eval.agent import ToolAgent
from paper_agent_eval.budget import Ledger,BudgetExceeded,reserve_bound
from paper_agent_eval.provider import DeepSeek,ProviderError
from paper_agent_eval.papers import Fixed,Online,factory
from paper_agent_eval.arxiv import Arxiv,identifier,PaperError,safe_url,parse_atom
from paper_agent_eval.retrieval import extract_pdf,chunks,retrieve,Index
from paper_agent_eval.grading import Grader,deterministic
from paper_agent_eval.evaluation import evaluate
from paper_agent_eval.metrics import aggregate,stable
from paper_agent_eval.util import redact,atomic_json,read_json
from paper_agent_eval.cli import main

ROOT=Path(__file__).resolve().parents[1]
ATOM=b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2003.08934v2</id><title> Test   Paper </title><author><name>Author A</name></author><published>2020-03-19T00:00:00Z</published><updated>2020-08-03T00:00:00Z</updated><summary>Public abstract.</summary></entry></feed>'''


def make_pdf(pages):
    """Own minimal PDF fixture, unrestricted test data, no downloaded content."""
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',None]
    kids=[]
    for text in pages:
        page_id=len(objects)+1;stream_id=page_id+1;kids.append(f'{page_id} 0 R')
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /Contents {stream_id} 0 R >>'.encode())
        stream=('BT /F1 12 Tf 30 750 Td ('+text+') Tj ET').encode()
        objects.append(b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream')
    objects[1]=('<< /Type /Pages /Count '+str(len(pages))+' /Kids ['+' '.join(kids)+'] >>').encode()
    out=b'%PDF-1.4\n';offsets=[0]
    for i,obj in enumerate(objects,1):offsets.append(len(out));out+=f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n'
    xref=len(out);out+=f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode()
    out+=b''.join(f'{p:010d} 00000 n \n'.encode() for p in offsets[1:])
    return out+f'trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF'.encode()


class TempTest(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()


class BudgetTests(TempTest):
    def setUp(self):
        super().setUp()
        from datetime import date
        self.clock=patch('paper_agent_eval.budget.date')
        clock=self.clock.start();clock.today.return_value=date(2026,11,18);clock.fromisoformat.side_effect=date.fromisoformat
        self.addCleanup(self.clock.stop)
    def test_expired_price_blocks_before_transport(self):
        from datetime import date
        with patch('paper_agent_eval.budget.date') as clock:
            clock.today.return_value=date(2026,11,30);clock.fromisoformat.side_effect=date.fromisoformat
            with self.assertRaises(BudgetExceeded):reserve_bound('deepseek-v4-pro',{'max_tokens':100},0)
    def test_persistence_and_stop(self):
        path=self.path/'budget.sqlite3';ledger=Ledger(path)
        identifier=ledger.reserve('test',4.4)
        with self.assertRaises(BudgetExceeded):Ledger(path).reserve('test',.11)
        self.assertEqual(Ledger(path).report()['uncertain_groups'],1)
        ledger.settle(identifier,.1,'estimated',{'total_tokens':3})
        self.assertAlmostEqual(Ledger(path).report()['exposure_usd'],.1)
        with self.assertRaises(ValueError):ledger.settle(identifier,0,'estimated')
    def test_bounds_cover_retry(self):
        body={'messages':[{'content':'中文'}],'max_tokens':100}
        a,_=reserve_bound('deepseek-v4-pro',body,0);b,bound=reserve_bound('deepseek-v4-pro',body,2)
        self.assertAlmostEqual(b,a*3);self.assertGreater(bound,8192)
        with self.assertRaises(BudgetExceeded):reserve_bound('unverified-model',body,0)
    def test_timeout_retains_exposure(self):
        ledger=Ledger(self.path/'ledger.sqlite3')
        with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'offline-fixture'}):
            client=DeepSeek(ledger=ledger,retries=1)
            opener=__import__('unittest.mock',fromlist=['Mock']).Mock();opener.open.side_effect=TimeoutError()
            with patch('urllib.request.build_opener',return_value=opener),patch('time.sleep'):
                with self.assertRaises(ProviderError):client.call([{'role':'user','content':'q'}])
            self.assertNotIn('offline-fixture',repr(client))
        self.assertGreater(ledger.report()['exposure_usd'],0);self.assertEqual(ledger.report()['uncertain_groups'],1)
    def test_usage_and_missing_usage(self):
        for usage in [None,dict(prompt_tokens=12,completion_tokens=4,total_tokens=16)]:
            ledger=Ledger(self.path/('missing.sqlite3' if usage is None else 'usage.sqlite3'))
            class Response:
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def read(self,*args):return json.dumps(dict(choices=[dict(message=dict(role='assistant',content='ok',reasoning_content='discard'),finish_reason='stop')],usage=usage)).encode()
            opener=__import__('unittest.mock',fromlist=['Mock']).Mock();opener.open.return_value=Response()
            with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'offline-fixture'}),patch('urllib.request.build_opener',return_value=opener):
                result=DeepSeek(ledger=ledger).call([{'role':'user','content':'q'}])
            self.assertEqual(result['usage'],usage);self.assertNotIn('reasoning_content',result['message'])
            self.assertEqual(ledger.report()['uncertain_groups'],int(usage is None))
    def test_redaction(self):
        with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'offline-fixture'}):
            x=redact(dict(api_key='offline-fixture',text='Bearer offline-fixture',total_tokens=3))
        self.assertNotIn('offline-fixture',json.dumps(x));self.assertEqual(x['total_tokens'],3)


class NetworkTests(TempTest):
    def test_atom(self):
        paper=parse_atom(ATOM)[0]
        self.assertEqual(paper['id'],'2003.08934v2');self.assertEqual(paper['authors'],['Author A']);self.assertEqual(paper['title'],'Test Paper')
        with self.assertRaises(PaperError):parse_atom(b'<!DOCTYPE a><feed/>')
        with self.assertRaises(PaperError):parse_atom(b'broken')
    def test_ids_and_urls(self):
        self.assertEqual(identifier('https://arxiv.org/pdf/2003.08934v2.pdf'),'2003.08934v2')
        for value in ['../.env','file:///etc/passwd','https://arxiv.org.evil/abs/2003.08934','https://user@arxiv.org/abs/2003.08934','https://arxiv.org/abs/2003.08934?x=1']:
            with self.assertRaises(PaperError):identifier(value)
        for url in ['http://arxiv.org/pdf/2003.08934','https://127.0.0.1/pdf/2003.08934','https://arxiv.org/.env','https://arxiv.org:444/pdf/2003.08934']:
            with self.assertRaises(PaperError):safe_url(url)
    def test_cache_no_network(self):
        arxiv=Arxiv(self.path)
        with patch.object(arxiv,'fetch',return_value=ATOM) as fetch:
            self.assertEqual(arxiv.search('test',2)[0]['id'],'2003.08934v2')
            arxiv.search('test',2);self.assertEqual(fetch.call_count,1)
        with self.assertRaises(PaperError):Arxiv(self.path,cache_only=True).fetch('https://arxiv.org/pdf/2003.08934v2')
    def test_download_and_tamper(self):
        arxiv=Arxiv(self.path)
        paper=parse_atom(ATOM)[0]
        with patch.object(arxiv,'resolve',return_value=paper),patch.object(arxiv,'fetch',return_value=make_pdf(['own fixture'])):
            directory,data=arxiv.download(paper['id']);self.assertIn('pdf_sha256',data)
            (directory/'paper.pdf').write_bytes(b'bad')
            with self.assertRaises(PaperError):arxiv.download(paper['id'])
        with patch.object(arxiv,'resolve',return_value=paper),patch.object(arxiv,'fetch',return_value=b'<html>not pdf</html>'):
            (directory/'manifest.json').unlink();(directory/'paper.pdf').unlink()
            with self.assertRaises(PaperError):arxiv.download(paper['id'])
    def test_fixed_isolation(self):
        fixed=Fixed()
        with patch('urllib.request.build_opener',side_effect=AssertionError('network forbidden')):
            self.assertEqual(fixed.execute('read_paper',{'paper_id':'../.env'})['status'],'not_in_corpus')
            self.assertEqual(len(fixed.execute('search_papers',{'query':''})['papers']),10)
        with self.assertRaises(ValueError):fixed.execute('search_papers',{'query':'','limit':True})
        with self.assertRaises(ValueError):fixed.execute('retrieve_text',{'paper_id':'2003.08934'})


class PDFTests(TempTest):
    def test_real_parser_own_fixture(self):
        path=self.path/'fixture.pdf';path.write_bytes(make_pdf(['Own first page.','Own second page with zebra.']))
        data=extract_pdf(path)
        self.assertEqual(len(data['pages']),2);self.assertIn('zebra',data['pages'][1])
        found=retrieve(dict(paper_id='fixture',chunks=chunks(data['pages'])),'zebra')
        self.assertEqual(found['evidence'][0]['pdf_page'],2)
    def test_textless_pdf(self):
        p=self.path/'empty.pdf';p.write_bytes(make_pdf(['']))
        with self.assertRaisesRegex(PaperError,'No text layer'):extract_pdf(p)
    def test_invalid_pdf(self):
        p=self.path/'bad.pdf';p.write_bytes(b'bad')
        with self.assertRaises(PaperError):extract_pdf(p)
    def test_boundaries_and_limits(self):
        docs=chunks(['alpha '*300,'beta '*300],size=200,overlap=20)
        self.assertEqual({d['pdf_page'] for d in docs},{1,2})
        result=retrieve(dict(paper_id='fixture',chunks=docs),'beta',top_k=3,max_chars=500)
        self.assertTrue(all(d['pdf_page']==2 for d in result['evidence']));self.assertLessEqual(sum(len(d['text']) for d in result['evidence']),500)
        self.assertEqual(retrieve(dict(paper_id='fixture',chunks=docs),'nohit')['evidence'],[])


class EvaluationTests(TempTest):
    def tasks(self):return [dict(id='1',type='exact',question='abc',expected=['cba']),dict(id='2',type='exact',question='drawer',expected=['reward'])]
    def test_nonpaper_adapter_resume_and_mismatch(self):
        tasks=self.tasks();config={'adapter':'paper_agent_eval.example:factory','context':''}
        output=self.path/'run';first=evaluate(tasks,config,output);second=evaluate(tasks,config,output)
        self.assertEqual(first['accuracy'],1);self.assertEqual(first,second)
        self.assertEqual(len((output/'records.jsonl').read_text().splitlines()),2)
        with self.assertRaises(ValueError):evaluate(tasks,dict(config,context='changed'),output)
        # Simulate interruption after execution persistence but before grading.
        (output/'records.jsonl').unlink()
        with patch('paper_agent_eval.example.Reverse.run',side_effect=AssertionError('must not run')):
            self.assertEqual(evaluate(tasks,config,output)['accuracy'],1)
    def test_exact_tool_and_error_graders(self):
        record=Result(answer='CNF with explanation').to_dict()
        task=dict(type='exact',expected=['CNF'])
        self.assertFalse(deterministic(task,record)['passed']);self.assertTrue(deterministic(task,record,'contains')['passed'])
        tool=dict(type='tool',expected_call=dict(name='x',arguments={'a':1,'b':2},match='exact'))
        record['calls']=[dict(name='x',arguments={'b':2,'a':1},error=None)]
        self.assertTrue(deterministic(tool,record)['passed']);record['calls']=[];self.assertFalse(deterministic(tool,record)['passed'])
        record['status']='timeout';self.assertFalse(deterministic(task,record,'contains')['passed'])
    def test_judge_schema_and_payload(self):
        task=dict(type='rubric',question='q',reference_answer='fact',reference_sources=['source fact'],rubric=['mention fact'])
        class Judge:
            model='offline';max_tokens=100
            def call(self,messages,**kwargs):
                payload=json.loads(messages[1]['content']);assert 'system' not in payload;assert payload['reference_sources']==['source fact']
                return dict(message={'content':'{"checks":[]}'},finish_reason='stop',usage=None,attempts=[])
        self.assertEqual(Grader(Judge()).grade(task,Result(answer='fact').to_dict())['status'],'grader_error')
    def test_metrics_and_stability(self):
        tasks=self.tasks();records=[]
        for run,states in [('a',[True,True]),('b',[True,False]),('c',[True,True])]:
            for t,p in zip(tasks,states):records.append(dict(task_id=t['id'],run_id=run,latency_s=2,model_calls=1,total_tokens=10,grade={'passed':p}))
        result=stable(records,tasks,['a','b','c'])
        self.assertEqual(result['pass_at_k'],1);self.assertEqual(result['pass_all_k'],.5);self.assertTrue(result['rows'][1]['flip'])
        self.assertEqual(aggregate(records[:2],tasks)['average_tokens_per_task'],10)
    def test_history_recompute(self):
        from paper_agent_eval.history import report
        h=report(ROOT/'benchmarks/historical')
        for policy in ['strict','contains']:
            self.assertEqual(h['results'][policy]['main_agent']['passed'],47)
            self.assertEqual(h['results'][policy]['main_baseline']['passed'],24)
            self.assertEqual(h['results'][policy]['stability']['pass_all_k'],.94)
    def test_tool_loop_and_state(self):
        class Client:
            model='offline';max_tokens=100
            def __init__(self):self.calls=0
            def call(self,messages,tools=None,judge=False):
                self.calls+=1
                if self.calls==1:
                    message=dict(role='assistant',content=None,tool_calls=[dict(id='c1',type='function',function=dict(name='read_paper',arguments='{"paper_id":"2312.14132"}'))])
                else:
                    assert messages[-1]['role']=='tool'
                    message=dict(role='assistant',content='pointmaps')
                return dict(message=message,finish_reason='stop',usage=dict(prompt_tokens=10,completion_tokens=2,total_tokens=12),attempts=[dict(ok=True)])
        client=Client();agent=factory(dict(mode='fixed'),client)
        result=agent.run(Input('What does DUSt3R regress?'))
        self.assertEqual(result.answer,'pointmaps');self.assertEqual(result.model_calls,2)
        self.assertEqual(result.usage['total_tokens'],24);self.assertEqual(len(result.calls),1)
        self.assertIn('abstract',result.calls[0]['result'])
    def test_run_family_and_labels(self):
        config={'adapter':'paper_agent_eval.example:factory','context':''}
        a=self.path/'a';b=self.path/'b'
        evaluate(self.tasks(),config,a,run_id='a')
        evaluate(self.tasks(),config,b,run_id='b')
        self.assertEqual(read_json(a/'manifest.json')['hash'],read_json(b/'manifest.json')['hash'])
        with self.assertRaises(ValueError):evaluate(self.tasks(),config,a,run_id='b')

    def test_recorded_online_metrics(self):
        from paper_agent_eval.util import jsonl
        tasks=jsonl(ROOT/'benchmarks/online/tasks.jsonl')
        rows=jsonl(ROOT/'benchmarks/online/records.jsonl')
        self.assertEqual(len(rows),12)
        self.assertEqual(aggregate([r for r in rows if r['system']=='agent'],tasks)['passed'],6)
        self.assertEqual(aggregate([r for r in rows if r['system']=='baseline'],tasks)['passed'],1)
        for r in rows:
            if r['answer'] is None:self.assertTrue(r.get('answer_sha256') and r.get('answer_omitted'))
            for c in r['calls']:
                if c.get('result') and isinstance(c['result'],dict):
                    for e in c['result'].get('evidence',[]):
                        self.assertNotIn('text',e);self.assertIn('text_sha256',e)

    def test_cli_offline(self):
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            self.assertEqual(main(['eval','--tasks',str(ROOT/'examples/reverse.tasks.jsonl'),'--config',str(ROOT/'examples/reverse.json'),'--out',str(self.path/'cli')]),0)
            self.assertEqual(main(['report','--tasks',str(ROOT/'examples/reverse.tasks.jsonl'),'--records',str(self.path/'cli/records.jsonl')]),0)
