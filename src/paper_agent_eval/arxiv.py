"""arXiv-only network access; a shared cache and single-connection, 3s gate."""
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import urlsplit,urlencode
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime,timezone
from .util import atomic_json,digest,read_json,sqlite_db

IDENTIFIER=re.compile(r'\d{4}\.\d{4,5}(?:v[1-9]\d*)?')
HOSTS={'arxiv.org','export.arxiv.org'}


class PaperError(RuntimeError):pass


def identifier(value,versioned=False):
    if not isinstance(value,str):raise PaperError('Paper ID must be text')
    if value.startswith('https://'):
        u=urlsplit(value)
        if u.hostname not in HOSTS or u.username or u.password or u.port or u.query or u.fragment:
            raise PaperError('Only plain HTTPS arXiv paper links are supported')
        if not (u.path.startswith('/abs/') or u.path.startswith('/pdf/')):raise PaperError('Not an arXiv paper link')
        value=u.path[5:]
        if value.endswith('.pdf'):value=value[:-4]
    if not IDENTIFIER.fullmatch(value):raise PaperError('Only modern arXiv IDs, optionally versioned, are supported')
    if versioned and 'v' not in value:raise PaperError('Versioned paper ID required')
    return value


def safe_url(url):
    u=urlsplit(url)
    if u.scheme!='https' or u.hostname not in HOSTS or u.username or u.password or u.port or u.fragment:
        raise PaperError('Blocked URL')
    if u.hostname=='export.arxiv.org':
        if u.path!='/api/query':raise PaperError('Blocked API path')
    elif not u.path.startswith('/pdf/') or not IDENTIFIER.fullmatch(u.path[5:]):
        raise PaperError('Blocked PDF path')
    return url


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        safe_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def parse_atom(raw):
    if b'<!DOCTYPE' in raw or b'<!ENTITY' in raw:raise PaperError('XML entities are unsupported')
    ns={'a':'http://www.w3.org/2005/Atom'}
    try:root=ET.fromstring(raw)
    except ET.ParseError:raise PaperError('Malformed Atom response') from None
    papers=[]
    for e in root.findall('a:entry',ns):
        raw_id=e.findtext('a:id',default='',namespaces=ns).rsplit('/abs/',1)[-1]
        pid=identifier(raw_id,versioned=True)
        papers.append(dict(id=pid,title=' '.join(e.findtext('a:title',default='',namespaces=ns).split()),
                           authors=[a.findtext('a:name',default='',namespaces=ns) for a in e.findall('a:author',ns)],
                           published=e.findtext('a:published',default='',namespaces=ns),updated=e.findtext('a:updated',default='',namespaces=ns),
                           abstract=' '.join(e.findtext('a:summary',default='',namespaces=ns).split()),
                           source_url='https://arxiv.org/abs/'+pid,pdf_url='https://arxiv.org/pdf/'+pid))
    return papers


class Arxiv:
    def __init__(self,cache,timeout=30,max_bytes=50_000_000,cache_only=False):
        self.cache=Path(cache);self.cache.mkdir(parents=True,exist_ok=True)
        self.timeout=timeout;self.max_bytes=max_bytes;self.cache_only=cache_only
        with sqlite_db(self.cache/'network.sqlite3') as db:
            db.execute('CREATE TABLE IF NOT EXISTS gate (id INTEGER PRIMARY KEY,last REAL)')
            db.execute('INSERT OR IGNORE INTO gate VALUES (1,0)')
    def fetch(self,url,max_bytes=None):
        if self.cache_only:raise PaperError("Frozen-cache mode: network disabled")
        safe_url(url);limit=max_bytes or self.max_bytes
        for attempt in range(2):
            try:
                # Hold transaction for full network lifetime: all local clients sharing this cache serialize.
                with sqlite_db(self.cache/'network.sqlite3',timeout=120) as db:
                    db.execute('BEGIN IMMEDIATE')
                    last=db.execute('SELECT last FROM gate WHERE id=1').fetchone()[0]
                    time.sleep(max(0,min(3.1,3.1-(time.time()-last))))
                    failure=None
                    try:
                        req=urllib.request.Request(url,headers={'User-Agent':'PaperAgentEval/0.2 (+https://arxiv.org/help/api)'})
                        with urllib.request.build_opener(SafeRedirect()).open(req,timeout=self.timeout) as response:
                            length=response.headers.get('Content-Length')
                            if length and int(length)>limit:raise PaperError('Download exceeds size limit')
                            raw=response.read(limit+1)
                            if len(raw)>limit:raise PaperError('Download exceeds size limit')
                    except Exception as exc:
                        failure=exc
                    finally:
                        db.execute('UPDATE gate SET last=? WHERE id=1',(time.time(),))
                if failure is not None:raise failure
                return raw
            except urllib.error.HTTPError as exc:
                if exc.code==429:
                    raise PaperError('arXiv rate limited the request; stop and retry later, do not switch endpoints') from None
                if exc.code<500 or attempt==1:raise PaperError('arXiv HTTP status '+str(exc.code)) from None
            except (urllib.error.URLError,OSError,TimeoutError):
                if attempt==1:raise PaperError('arXiv transport unavailable (DNS/TLS/timeout); no credentials were sent') from None
        raise PaperError('arXiv request failed')
    def search(self,query,limit=5):
        if not isinstance(query,str) or not query.strip() or len(query)>300:raise PaperError('Search query must contain 1–300 characters')
        if type(limit) is not int or not 1<=limit<=10:raise PaperError('Search limit must be 1–10')
        # Treat words as search data; do not accept arbitrary query-language operators.
        words=re.findall(r'\w+',query)
        if not words:raise PaperError('Query needs searchable words')
        if self.cache_only:
            papers=[read_json(p)['paper'] for p in self.cache.glob('*/manifest.json')]
            return [p for p in papers if all(w.casefold() in (p['title']+' '+p['abstract']).casefold() for w in words)][:limit]
        params={'search_query':' AND '.join('all:'+w for w in words),'max_results':limit,'sortBy':'relevance'}
        return self._query(params)
    def _query(self,params):
        path=self.cache/('query-'+digest(params)+'.json')
        if path.exists():return read_json(path)['papers']
        url='https://export.arxiv.org/api/query?'+urlencode(params)
        raw=self.fetch(url,2_000_000);papers=parse_atom(raw)
        atomic_json(path,dict(papers=papers,source=url,retrieved_utc=datetime.now(timezone.utc).isoformat(),sha256=hashlib.sha256(raw).hexdigest()))
        return papers
    def resolve(self,locator):
        pid=identifier(locator)
        if 'v' in pid and (self.cache/pid/'manifest.json').exists():
            return read_json(self.cache/pid/'manifest.json')['paper']
        if self.cache_only:raise PaperError('Frozen-cache mode requires an available versioned ID')
        papers=self._query({'id_list':pid,'max_results':1})
        if len(papers)!=1:raise PaperError('Paper not returned by arXiv; existence is not established')
        actual=identifier(papers[0]['id'],versioned=True)
        if actual.split('v')[0]!=pid.split('v')[0] or ('v' in pid and actual!=pid):raise PaperError('arXiv ID/version mismatch')
        return papers[0]
    def download(self,locator):
        paper=self.resolve(locator);pid=paper['id']
        directory=self.cache/pid;directory.mkdir(exist_ok=True)
        pdf=directory/'paper.pdf';manifest=directory/'manifest.json'
        if manifest.exists() and pdf.exists():
            data=read_json(manifest)
            if hashlib.sha256(pdf.read_bytes()).hexdigest()!=data['pdf_sha256']:raise PaperError('PDF cache hash mismatch')
            return directory,data
        raw=self.fetch('https://arxiv.org/pdf/'+pid)
        if not raw.startswith(b'%PDF-'):raise PaperError('arXiv response is not a PDF')
        temp=directory/'download.tmp';temp.write_bytes(raw);temp.replace(pdf)
        data=dict(paper=paper,source='https://arxiv.org/pdf/'+pid,downloaded_utc=datetime.now(timezone.utc).isoformat(),pdf_sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
        atomic_json(manifest,data)
        return directory,data
