"""Page-preserving lexical chunks. PDF page numbers are 1-based file indices."""
from collections import Counter
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from .arxiv import PaperError,identifier
from .util import atomic_json,read_json


def extract_pdf(path):
    path=Path(path)
    if not path.is_file() or path.stat().st_size>50_000_000 or not path.read_bytes().startswith(b'%PDF-'):
        raise PaperError('Invalid or oversized PDF')
    env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ('KEY','TOKEN','SECRET','PASSWORD','AUTH'))}
    if importlib.util.find_spec('pypdf'):
        command=[sys.executable,'-m','paper_agent_eval.pdfworker',str(path)]
    elif sys.platform=='darwin':
        command=['/usr/bin/swift','-module-cache-path','/tmp/pae-swift-modules',str(Path(__file__).with_name('pdfkit.swift')),str(path)]
    else:
        raise PaperError('Install paper-agent-eval[pdf] for PDF parsing')
    try:
        process=subprocess.run(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=50,check=True)
        if len(process.stdout)>16_000_000:raise PaperError('Extracted text exceeds limit')
        data=json.loads(process.stdout)
    except (subprocess.SubprocessError,ValueError,OSError):
        raise PaperError('PDF parsing failed: encrypted, corrupt, unsupported or resource limit; no OCR') from None
    if data.get('error'):raise PaperError('PDF parsing error: '+data['error'])
    if not data.get('pages') or not any(p.strip() for p in data['pages']):
        raise PaperError('No text layer found; scanned PDFs require OCR, which is not supported')
    return data


def chunks(pages,size=1200,overlap=150):
    if not 200<=size<=4000 or not 0<=overlap<size:raise ValueError('Invalid chunk bounds')
    output=[]
    for page_number,text in enumerate(pages,1):
        for start in range(0,len(text),size-overlap):
            part=text[start:start+size]
            if part.strip():output.append(dict(chunk_id=str(page_number)+':'+str(start),pdf_page=page_number,start=start,text=part))
    return output


def tokenize(text):return re.findall(r'[a-z0-9]+',text.casefold())


def retrieve(index,query,top_k=4,max_chars=6000):
    if not isinstance(query,str) or not query.strip() or len(query)>1000:raise ValueError('Invalid retrieval query')
    if type(top_k) is not int or not 1<=top_k<=8 or not 500<=max_chars<=16000:raise ValueError('Invalid retrieval bounds')
    docs=index['chunks'];terms=set(tokenize(query));counts=[Counter(tokenize(d['text'])) for d in docs]
    avg=sum(sum(c.values()) for c in counts)/max(1,len(counts));ranked=[]
    for doc,c in zip(docs,counts):
        score=0.0
        for term in terms:
            tf=c[term];df=sum(term in other for other in counts)
            idf=math.log(1+(len(docs)-df+.5)/(df+.5))
            if tf:score+=idf*(tf*2.2)/(tf+1.2*(.25+.75*sum(c.values())/max(1,avg)))
        if score:ranked.append(dict(doc,score=score))
    ranked.sort(key=lambda d:(-d['score'],d['pdf_page'],d['start']))
    selected=[];used=0
    for doc in ranked[:top_k]:
        remaining=max_chars-used
        if remaining<=0:break
        part=dict(doc,text=doc['text'][:remaining]);used+=len(part['text']);selected.append(part)
    return dict(paper_id=index['paper_id'],evidence=selected,scope='Retrieved chunks only; PDF page indices, not printed page labels')


class Index:
    def __init__(self,arxiv,size=1200,overlap=150):self.arxiv=arxiv;self.size=size;self.overlap=overlap
    def build(self,locator):
        directory,manifest=self.arxiv.download(locator)
        pid=identifier(manifest['paper']['id'],versioned=True);path=directory/'index.json'
        if path.exists():
            if manifest.get('index_sha256')!=hashlib.sha256(path.read_bytes()).hexdigest():raise PaperError('Index cache hash mismatch')
            saved=read_json(path)
            if saved['pdf_sha256']!=manifest['pdf_sha256'] or saved['chunk_size']!=self.size or saved['overlap']!=self.overlap:
                raise PaperError('Index version/config changed: use a fresh cache')
            return saved
        data=extract_pdf(directory/'paper.pdf')
        saved=dict(paper_id=pid,pdf_sha256=manifest['pdf_sha256'],parser=data['parser'],page_count=len(data['pages']),
                   chunk_size=self.size,overlap=self.overlap,chunks=chunks(data['pages'],self.size,self.overlap))
        atomic_json(path,saved)
        manifest.update(parser=data['parser'],index_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),page_count=saved['page_count'])
        atomic_json(directory/'manifest.json',manifest)
        return saved
