"""Export reviewed online metrics/traces without PDFs or long extracted passages.
No model calls. Full source text stays in the local cache; page/offset/hash stays public.
"""
import copy
import hashlib
import json
from pathlib import Path
from paper_agent_eval.budget import Ledger
from paper_agent_eval.metrics import aggregate
from paper_agent_eval.util import atomic_json,jsonl,read_json,canonical,redact

ROOT=Path(__file__).resolve().parents[1]


def strip_passages(value):
    if isinstance(value,list):return [strip_passages(v) for v in value]
    if not isinstance(value,dict):return value
    result={k:strip_passages(v) for k,v in value.items() if k!='text'}
    if 'text' in value:
        result['text_sha256']=hashlib.sha256(value['text'].encode()).hexdigest()
        result['text_chars']=len(value['text'])
        result['text_omitted']='Full source passage retained in local cache; rebuild from versioned PDF.'
    return result


def main():
    out=ROOT/'benchmarks/online';tasks=jsonl(out/'tasks.jsonl');records=[];manifests={};hashes={}
    for system in ['agent','baseline']:
        directory=ROOT/'runs'/('fulltext-v1-'+system)
        rows=jsonl(directory/'records.jsonl')
        if len(rows)!=len(tasks):raise ValueError('Do not export incomplete formal results')
        manifests[system]=read_json(directory/'manifest.json')
        hashes[system]=hashlib.sha256((directory/'records.jsonl').read_bytes()).hexdigest()
        for r in rows:
            row=copy.deepcopy(r)
            row['calls']=strip_passages(row['calls'])
            row['grade'].pop('judge_input',None)
            if '\n>' in row['answer'] and len(row['answer'])>1500:
                row['answer_sha256']=hashlib.sha256(row['answer'].encode()).hexdigest()
                row['answer_omitted']='Contains long verbatim PDF quotations. Original response remains unchanged in private run log; public metrics and verdict are unchanged.'
                row['answer']=None
                for message in row['messages']:
                    if message.get('role')=='assistant' and not message.get('tool_calls') and message.get('content'):
                        message['content_sha256']=hashlib.sha256(message['content'].encode()).hexdigest()
                        message['content']=None
            records.append(row)
    (out/'records.jsonl').write_text(''.join(canonical(redact(r))+'\n' for r in records))
    summaries={s:aggregate([r for r in records if r['system']==s],tasks) for s in ['agent','baseline']}
    atomic_json(out/'results.json',summaries)
    atomic_json(out/'experiment.json',dict(manifests=manifests,original_record_sha256=hashes,
        export_policy='Scores, timing, usage and tool arguments unchanged. Answers retained except any long PDF-quotation response, explicitly omitted with its original hash; raw response stays unchanged locally. Retrieved full-text passages replaced by page, start, length and SHA-256; raw judge input omitted. No downloaded PDFs/indexes/full text published.'))
    budget=Ledger().report();usage=[u for group in budget['usage_records'] for u in group.get('attempt_usages',[])]
    attempts=sum(len(group.get('attempts',[])) for group in budget['usage_records'])
    budget_summary=dict(model='deepseek-v4-pro',requests=attempts,reported_prompt_tokens=sum(u['prompt_tokens'] for u in usage),
        reported_completion_tokens=sum(u['completion_tokens'] for u in usage),reported_total_tokens=sum(u['total_tokens'] for u in usage),
        exposure_usd=budget['exposure_usd'],uncertain_groups=budget['uncertain_groups'],ceiling_usd=5,stop_threshold_usd=4.5,
        scope='ALL new preflight, tool roundtrip, smoke, judge calibration, formal Agent, baseline, judge and retries; excludes historical experiment',
        basis=budget['basis'],price_source='https://api-docs.deepseek.com/quick_start/pricing/',checked_utc_date='2026-11-18',safety_multiplier=1.25)
    atomic_json(out/'budget-summary.json',budget_summary)
    for name in ['live-preflight.json','online-smoke.json','judge-calibration.json']:
        path=ROOT/'.local-run'/name
        if path.exists():
            data=read_json(path)
            # Calibration is explicit fixture grading, never counted as formal task outputs.
            if name=='online-smoke.json':data=strip_passages(data)
            if name=='judge-calibration.json':
                for item in data:item['grade'].pop('judge_input',None)
            atomic_json(out/name,redact(data))
    lines=['# Real full-text mini-evaluation','','Six frozen tasks, one independent Agent and baseline execution per task. Separate from the historical abstract-only benchmark; no best-of selection or original 250-task rerun.','',
           '|Metric|Agent|Baseline|','|---|---:|---:|']
    for label,field in [('Passed /6','passed'),('Accuracy','accuracy'),('Non-tool accuracy (all 6 tasks)','non_tool_accuracy'),('Average model calls / task','average_model_calls'),('Average latency (seconds)','average_latency_s'),('P95 latency (seconds)','p95_latency_s'),('Average total tokens / task','average_tokens_per_task'),('Usage coverage','usage_coverage')]:
        lines.append('|'+label+'|'+'|'.join(str(summaries[s][field]) for s in ['agent','baseline'])+'|')
    lines+=['','|Task|Agent pass|Baseline pass|','|---|---|---|']
    for task in tasks:
        lines.append('|'+task['id']+'|'+'|'.join(str(next(r for r in records if r['task_id']==task['id'] and r['system']==s)['grade']['passed']) for s in ['agent','baseline'])+'|')
    lines+=['','Both systems have the same role, question and mode description; only Agent can retrieve actual PDF evidence. Baseline receives no passages. This comparison measures evidence access plus the tool loop, not reasoning under equal evidence. All tasks are rubric/unanswerable, so there is no structural tool-grader penalty in this mini-set. Original judge verdicts and reasons are preserved. A manual spot check found overbroad DDPM constant-rate language in fulltext-05 and an unsourced PSNR formula in fulltext-06 despite passed Grounded checks; these are grading limitations, not corrected scores. Baseline emits pseudo-tool markup as plain text on the five body questions; no actual tool executes.','',
            'The two separate offline download/parse robustness cases are not paid task executions and are not included in accuracy. No three-run stability claim is made for this small new evaluation.','',
            'Source versions, actual PDF/index hashes and parser details are in manifest.json. Full passages stay local; public traces retain PDF page indices, chunk starts, lengths and text hashes for reconstruction. Raw model answers and numeric experimental facts are not changed. The one response containing long PDF quotations is explicitly withheld in the public export with its original hash; it is not replaced by a fabricated answer.','',
            'Cost for ALL new calls, including preflight and judge calibration: '+str(attempts)+' requests; '+str(budget_summary['reported_total_tokens'])+' reported tokens; $'+str(budget_summary['exposure_usd'])+' conservative exposure (peak cache-miss rates ×1.25), not an invoice. See budget-summary.json.']
    (out/'results.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(summaries=summaries,budget=budget_summary),indent=2))

if __name__=='__main__':main()
