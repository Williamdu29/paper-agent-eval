"""Download/index the two public references and freeze a LOCAL cache-only config.
No model calls. Do not publish the cache or complete extracted text.
"""
import hashlib
import json
from pathlib import Path
from paper_agent_eval.arxiv import Arxiv
from paper_agent_eval.retrieval import Index
from paper_agent_eval.util import atomic_json,read_json

cache=Path('.cache/arxiv')
files=[];sources=[]
for pid in ['2003.08934v2','2006.11239v2']:
    index=Index(Arxiv(cache)).build(pid)
    manifest=cache/pid/'manifest.json'
    sources.append(read_json(manifest))
    files += [str(manifest),str(cache/pid/'index.json'),str(cache/pid/'paper.pdf')]
config=dict(adapter='paper_agent_eval.papers:factory',mode='online',context='',cache=str(cache),cache_only=True,max_turns=8,max_context_chars=60000,artifacts=files)
output=Path('.local-run/online-config.json')
if output.exists() and read_json(output)!=config:raise SystemExit('Existing local config differs; use a fresh experiment version')
atomic_json(output,config)
atomic_json('.local-run/online-sources.json',sources)
print('Prepared local cache-only config:',output)
