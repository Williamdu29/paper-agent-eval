import argparse
import json
import os
from pathlib import Path
import sys
from .contracts import Input
from .util import load_env,atomic_json,jsonl,read_json,redact


def main(argv=None):
    parser=argparse.ArgumentParser(prog='pae')
    parser.add_argument('--env-file',help='Explicit local dotenv file; existing environment wins')
    sub=parser.add_subparsers(dest='command',required=True)
    def cache_arg(p):p.add_argument('--cache',default=str(Path.home()/'.cache/paper-agent-eval/arxiv'))
    p=sub.add_parser('ask');p.add_argument('question');p.add_argument('--mode',choices=['fixed','online'],default='fixed');p.add_argument('--baseline',action='store_true');cache_arg(p)
    p=sub.add_parser('search');p.add_argument('query');p.add_argument('--limit',type=int,default=5);cache_arg(p)
    p=sub.add_parser('index');p.add_argument('paper');cache_arg(p)
    p=sub.add_parser('retrieve');p.add_argument('paper');p.add_argument('query');p.add_argument('--top-k',type=int,default=4);cache_arg(p)
    p=sub.add_parser('eval');p.add_argument('--tasks',required=True);p.add_argument('--config',required=True);p.add_argument('--out',required=True);p.add_argument('--system',choices=['agent','baseline'],default='agent');p.add_argument('--run-id',default='main');p.add_argument('--exact',choices=['strict','contains'],default='strict');p.add_argument('--paid',action='store_true')
    p=sub.add_parser('report');p.add_argument('--tasks',required=True);p.add_argument('--records',required=True);p.add_argument('--output');p.add_argument('--stability-runs',nargs='+')
    p=sub.add_parser('history');p.add_argument('--directory',default='benchmarks/historical');p.add_argument('--output')
    sub.add_parser('budget')
    args=parser.parse_args(argv);load_env(args.env_file)
    try:
        if args.command=='budget':
            from .budget import Ledger
            value=Ledger().report()
        elif args.command=='history':
            from .history import report
            value=report(Path(args.directory))
        elif args.command=='report':
            from .metrics import aggregate,stable
            from .evaluation import load_tasks
            tasks=load_tasks(args.tasks);records=jsonl(args.records)
            if len({r['version'] for r in records})>1:raise ValueError('Mixed versions cannot be aggregated')
            groups=sorted({(r['system'],r['run_id']) for r in records})
            if len({(r['system'],r['run_id'],r['task_id']) for r in records})!=len(records):raise ValueError('Duplicate task executions')
            value={'runs':{s+':'+run:aggregate([r for r in records if r['system']==s and r['run_id']==run],tasks) for s,run in groups}}
            if args.stability_runs:value['stability']=stable([r for r in records if r['system']=='agent'],tasks,args.stability_runs)
        elif args.command=='eval':
            from .evaluation import evaluate,load_tasks
            from .provider import DeepSeek
            value=evaluate(load_tasks(args.tasks),read_json(args.config),args.out,DeepSeek() if args.paid else None,args.system,args.run_id,args.exact)
        elif args.command=='ask':
            from .papers import factory
            from .provider import DeepSeek
            result=factory(dict(mode=args.mode,cache=args.cache,system='baseline' if args.baseline else 'agent'),DeepSeek()).run(Input(args.question))
            value=result.to_dict()
        else:
            from .arxiv import Arxiv
            from .retrieval import Index,retrieve
            arxiv=Arxiv(args.cache)
            if args.command=='search':value=arxiv.search(args.query,args.limit)
            elif args.command=='index':
                index=Index(arxiv).build(args.paper);value={k:v for k,v in index.items() if k!='chunks'}
            else:value=retrieve(Index(arxiv).build(args.paper),args.query,args.top_k)
        value=redact(value)
        if getattr(args,'output',None):atomic_json(args.output,value)
        print(json.dumps(value,ensure_ascii=False,indent=2))
        if isinstance(value,dict) and value.get('status','ok')!='ok':return 1
        return 0
    except Exception as exc:
        # Never serialize arbitrary exception text, provider headers or response bodies.
        if type(exc).__name__ in ('BudgetExceeded','PaperError','ValueError'):message=redact(str(exc))
        else:message=type(exc).__name__
        print('Error: '+message,file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
