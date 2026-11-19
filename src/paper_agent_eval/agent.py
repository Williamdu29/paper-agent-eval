"""Generic bounded tool-calling loop; no paper or grader dependency."""
import json
import time
from .contracts import Result
from .provider import ProviderError
from .budget import BudgetExceeded
from .util import canonical,redact


class ToolAgent:
    def __init__(self,client,tools,role,allow_tools=True,max_turns=8,max_context_chars=60000):
        self.client=client;self.tools=tools;self.role=role;self.allow_tools=allow_tools
        self.max_turns=max_turns;self.max_context_chars=max_context_chars
    def run(self,item):
        start=time.perf_counter();result=Result();messages=[dict(role='system',content=self.role),dict(role='user',content=item.context+'\n\nQuestion: '+item.question)]
        session=self.tools.new();usages=[]
        try:
            for _ in range(self.max_turns if self.allow_tools else 1):
                if len(canonical(messages))>self.max_context_chars:
                    result.status='context_limit';break
                try:data=self.client.call(messages,self.tools.schemas if self.allow_tools else None)
                except ProviderError as exc:
                    result.attempts.extend(exc.events);raise
                result.attempts.extend(data['attempts']);usages.append(data['usage'])
                message=data['message'];messages.append(message);result.messages.append(message)
                calls=message.get('tool_calls') or []
                if not calls:
                    result.answer=message.get('content') or ''
                    result.status='ok' if result.answer.strip() and data['finish_reason']=='stop' else 'incomplete'
                    break
                if not self.allow_tools:raise ValueError('Baseline returned a tool call')
                if len(calls)>10:raise ValueError('Too many calls in a single turn')
                for call in calls:
                    trace=dict(name=call['function']['name'],arguments=None,result=None,error=None)
                    result.calls.append(trace)
                    try:
                        trace['arguments']=json.loads(call['function']['arguments'])
                        if not isinstance(trace['arguments'],dict):raise ValueError('Arguments must be an object')
                        trace['result']=session.execute(trace['name'],trace['arguments'])
                    except Exception as exc:
                        trace['error']=redact(str(exc)) if type(exc).__name__ in ('PaperError','ValueError') else type(exc).__name__
                    messages.append(dict(role='tool',tool_call_id=call['id'],content=canonical(redact(trace))))
            else:result.status='max_turns'
        except BudgetExceeded:result.status='budget_exceeded'
        except ProviderError:result.status='provider_error'
        except TimeoutError:result.status='timeout'
        except Exception:result.status='error'
        result.model_calls=len(result.attempts)
        if usages and all(u is not None for u in usages) and all(e['ok'] for e in result.attempts):
            result.usage={k:sum(u[k] for u in usages) for k in ('prompt_tokens','completion_tokens','total_tokens')}
        result.latency_s=time.perf_counter()-start
        # Keep credential redaction at the persistence boundary as well.
        return Result(**redact(result.to_dict()))
