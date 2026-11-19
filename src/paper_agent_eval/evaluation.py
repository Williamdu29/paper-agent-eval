"""Task-blind adapters, frozen run manifests, per-task checkpoints, independent grades."""
import importlib
import inspect
from pathlib import Path
import time
from .contracts import Input,Result
from .grading import Grader
from .metrics import aggregate
from .util import atomic_json,append_jsonl,digest,jsonl,read_json,redact,sqlite_db


def load_tasks(path):
    tasks=jsonl(path)
    if not tasks or len({t['id'] for t in tasks})!=len(tasks):raise ValueError('Nonempty tasks with unique IDs required')
    for t in tasks:
        if not isinstance(t['question'],str) or t['type'] not in ('exact','tool','rubric','unanswerable'):raise ValueError('Invalid task')
        if t['type']=='exact' and not t.get('expected'):raise ValueError('Exact expected missing')
        if t['type']=='tool' and not t.get('expected_call'):raise ValueError('Tool rule missing')
        if t['type'] in ('rubric','unanswerable') and not all(t.get(k) for k in ('rubric','reference_answer','reference_sources')):raise ValueError('Judge references missing')
    return tasks


def factory(reference):
    module,name=reference.split(':');return getattr(importlib.import_module(module),name)


def snapshot(tasks,config):
    package=Path(__file__).parent
    code={str(p.relative_to(package)):__import__('hashlib').sha256(p.read_bytes()).hexdigest() for p in package.rglob('*') if p.is_file() and p.suffix in ('.py','.json','.swift')}
    custom=inspect.getsourcefile(factory(config['adapter']))
    artifacts={str(p):__import__('hashlib').sha256(Path(p).read_bytes()).hexdigest() for p in config.get('artifacts',[])}
    if custom:artifacts['adapter_source']=__import__('hashlib').sha256(Path(custom).read_bytes()).hexdigest()
    return dict(tasks=tasks,config=config,code=code,artifacts=artifacts,version=2)


def _evaluate(tasks,config,out,client=None,system='agent',run_id='main',policy='strict'):
    if system not in ('agent','baseline'):raise ValueError('Unknown system')
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if config.get('mode')=='online' and (not config.get('cache_only') or not config.get('artifacts')):
        raise ValueError('Online evaluation requires cache_only=true and frozen PDF/index manifests in artifacts')
    # Provider model/settings are part of identity. Never store credentials or endpoint secrets.
    identity=dict(snapshot=snapshot(tasks,config),exact_policy=policy,
                  model=client.model if client else 'offline-example',max_output=client.max_tokens if client else None,
                  request_config=dict(timeout=getattr(client,'timeout',None),retries=getattr(client,'retries',None),thinking=False,temperature=.2,judge_temperature=0))
    version=digest(identity);manifest=out/'manifest.json'
    if manifest.exists():
        previous=read_json(manifest)
        if previous['hash']!=version or previous['system']!=system or previous['run_id']!=run_id:raise ValueError('Experiment version/config/run mismatch: use a new output directory')
    else:atomic_json(manifest,dict(hash=version,identity=identity,system=system,run_id=run_id))
    path=out/'records.jsonl';records=jsonl(path) if path.exists() else []
    if len({r['task_id'] for r in records})!=len(records) or any(r['version']!=version for r in records):raise ValueError('Mixed/duplicate records')
    finished={r['task_id'] for r in records}
    maker=factory(config['adapter']);grader=Grader(client,out/'judge-cache',policy)
    (out/'executions').mkdir(exist_ok=True)
    for task in tasks:
        if task['id'] in finished:continue
        checkpoint=out/'executions'/(digest(task['id'])+'.json')
        if checkpoint.exists():record=read_json(checkpoint)
        else:
            adapter=maker(dict(config,system=system),client)
            start=time.perf_counter()
            try:result=adapter.run(Input(task['question'],config.get('context','')))
            except TimeoutError:result=Result(status='timeout',latency_s=time.perf_counter()-start)
            except Exception:result=Result(status='adapter_error',latency_s=time.perf_counter()-start)
            record=redact(dict(task_id=task['id'],system=system,run_id=run_id,version=version,**result.to_dict()))
            record['total_tokens']=result.usage.get('total_tokens') if result.usage else None
            atomic_json(checkpoint,record)
        if record['version']!=version:raise ValueError('Checkpoint mismatch')
        record['grade']=redact(grader.grade(task,record));append_jsonl(path,record);records.append(record)
        atomic_json(out/'summary.json',aggregate(records,tasks))
        if record['status'] in ('provider_error','budget_exceeded') or record['grade'].get('reason')=='BudgetExceeded':break
    atomic_json(out/'summary.json',aggregate(records,tasks))
    return aggregate(records,tasks)


def evaluate(tasks,config,out,client=None,system='agent',run_id='main',policy='strict'):
    import sqlite3
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    with sqlite_db(out/'run-lock.sqlite3',timeout=1) as lock:
        lock.execute('CREATE TABLE IF NOT EXISTS guard (id INTEGER)')
        lock.execute('BEGIN IMMEDIATE')
        return _evaluate(tasks,config,out,client,system,run_id,policy)
