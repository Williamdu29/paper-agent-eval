"""Only paid-request transport. No SDK implicit retries; no arbitrary provider URL."""
import os
import time
import urllib.request
import urllib.error
import json
from .budget import Ledger,cost,reserve_bound
from .util import redact


class ProviderError(RuntimeError):
    def __init__(self,kind,events):
        super().__init__(kind);self.events=events


class DeepSeek:
    def __init__(self,ledger=None,model=None,timeout=45,retries=1,max_tokens=1800):
        self._key=os.getenv('DEEPSEEK_API_KEY','')
        self.model=model or os.getenv('DEEPSEEK_MODEL','deepseek-v4-pro')
        self.ledger=ledger or Ledger();self.timeout=timeout;self.retries=retries;self.max_tokens=max_tokens
        if not 0<=retries<=2 or not 1<=max_tokens<=8192:raise ValueError('Invalid request limits')
    def __repr__(self):return 'DeepSeek(model='+self.model+', key=[REDACTED])'
    def call(self,messages,tools=None,judge=False):
        if not self._key:raise ProviderError('Missing DEEPSEEK_API_KEY',[])
        body=dict(model=self.model,messages=messages,max_tokens=self.max_tokens,temperature=0 if judge else .2,thinking={'type':'disabled'})
        if tools:body['tools']=tools
        if judge:body['response_format']={'type':'json_object'}
        amount,bound=reserve_bound(self.model,body,self.retries)
        reservation=self.ledger.reserve(self.model,amount)
        events=[];exposure=0.0;usages=[]
        per_attempt=amount/(self.retries+1)
        try:
            for attempt in range(self.retries+1):
                # Count attempt as uncertain BEFORE transport; a timeout may still be billed.
                exposure+=per_attempt
                start=time.perf_counter()
                try:
                    req=urllib.request.Request('https://api.deepseek.com/chat/completions',json.dumps(body).encode(),
                        {'Authorization':'Bearer '+self._key,'Content-Type':'application/json'})
                    # No redirects: credentials must never be forwarded to another host.
                    opener=urllib.request.build_opener(NoRedirect())
                    with opener.open(req,timeout=self.timeout) as response:
                        raw=response.read(4_000_001)
                    if len(raw)>4_000_000:raise ValueError('Response too large')
                    data=json.loads(raw);msg=data['choices'][0]['message'];usage=data.get('usage')
                    valid=bool(usage and all(type(usage.get(k)) is int and usage[k]>=0 for k in ('prompt_tokens','completion_tokens','total_tokens')))
                    if valid:
                        exposure+=cost(self.model,usage['prompt_tokens'],usage['completion_tokens'])-per_attempt
                        usages.append(usage)
                    events.append(dict(attempt=attempt+1,ok=True,latency_s=time.perf_counter()-start,usage=usage if valid else None))
                    self.ledger.settle(reservation,exposure,'estimated' if valid and all(e['ok'] for e in events) else 'uncertain',{'attempt_usages':usages,'attempts':events})
                    # Never persist returned hidden reasoning, and never ask the model for it.
                    return dict(message={k:v for k,v in msg.items() if k!='reasoning_content'},usage=usage if valid and all(e['ok'] for e in events) else None,
                                finish_reason=data['choices'][0].get('finish_reason'),attempts=redact(events))
                except (urllib.error.URLError,OSError,ValueError,KeyError,IndexError) as exc:
                    status=getattr(exc,'code',None)
                    events.append(dict(attempt=attempt+1,ok=False,status=status,error=type(exc).__name__,latency_s=time.perf_counter()-start))
                    if status and status not in (408,429) and status<500:break
                    if attempt<self.retries:time.sleep(min(2**attempt,4))
            self.ledger.settle(reservation,exposure,'uncertain',{'attempt_usages':usages,'attempts':events})
        except BaseException:
            # Leave the full durable reservation on interruptions or ambiguous failures.
            raise
        raise ProviderError('DeepSeek transport failed (details sanitized)',events)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None
