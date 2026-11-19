"""No domain imports and no hardcoded task count."""
import math


def aggregate(records,tasks):
    n=len(tasks);types={t['id']:t['type'] for t in tasks};non_count=sum(v!='tool' for v in types.values())
    def avg(field):
        values=[r[field] for r in records if r.get(field) is not None]
        return sum(values)/len(values) if values else None
    latency=sorted(r['latency_s'] for r in records)
    passed=sum(r['grade']['passed'] for r in records)
    return dict(completed=len(records),total=n,passed=passed,accuracy=passed/n if records else None,
                non_tool_total=non_count,non_tool_accuracy=sum(r['grade']['passed'] for r in records if types[r['task_id']]!='tool')/non_count if records and non_count else None,
                average_model_calls=avg('model_calls'),average_latency_s=avg('latency_s'),p95_latency_s=latency[math.ceil(.95*len(latency))-1] if latency else None,
                average_tokens_per_task=avg('total_tokens'),usage_coverage=sum(r.get('total_tokens') is not None for r in records)/len(records) if records else None,
                by_type={typ:dict(passed=sum(r['grade']['passed'] for r in records if types[r['task_id']]==typ),total=sum(v==typ for v in types.values())) for typ in sorted(set(types.values()))})


def stable(records,tasks,run_ids):
    lookup={(r['task_id'],r['run_id']):r['grade']['passed'] for r in records};rows=[]
    for t in tasks:
        states=[lookup.get((t['id'],run)) for run in run_ids]
        complete=all(type(p) is bool for p in states)
        rows.append(dict(task_id=t['id'],question=t['question'],states=states,any_pass=any(states) if complete else None,all_pass=all(states) if complete else None,flip=len(set(states))>1 if complete else None))
    complete=all(r['any_pass'] is not None for r in rows)
    return dict(pass_at_k=sum(r['any_pass'] for r in rows)/len(tasks) if complete else None,
                pass_all_k=sum(r['all_pass'] for r in rows)/len(tasks) if complete else None,rows=rows)
