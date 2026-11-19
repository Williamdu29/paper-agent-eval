"""Recompute preserved historical facts; never generate fresh responses."""
import copy
from .grading import normalized
from .metrics import aggregate,stable
from .util import jsonl,read_json


def report(directory):
    tasks=jsonl(directory/'tasks.jsonl');rows=jsonl(directory/'records.jsonl');lookup={t['id']:t for t in tasks}
    assert len(rows)==250 and len({(r['task_id'],r['run_id']) for r in rows})==250
    summaries={}
    for policy in ['strict','contains']:
        records=copy.deepcopy(rows)
        for r in records:
            t=lookup[r['task_id']]
            if t['type']=='exact':
                mode=t.get('normalization',[]);answer=normalized(r['answer'],mode)
                r['grade']['passed']=any(normalized(e,mode)==answer if policy=='strict' else normalized(e,mode) in answer for e in t['expected']) and not r['error'] and bool(r['answer'].strip())
            r['latency_s']=r['latency'];r['model_calls']=r['model_turns']
        groups={run:aggregate([r for r in records if r['run_id']==run],tasks) for run in ['main_agent','main_baseline','stability1','stability2','stability3']}
        groups['stability']=stable(records,tasks,['stability1','stability2','stability3'])
        summaries[policy]=groups
    return dict(provenance=read_json(directory/'provenance.json'),results=summaries,
                limitation='Historical fixed-abstract benchmark; original rubric judgments include a documented false positive (baseline t44). Not evidence of online/full-text performance.')
