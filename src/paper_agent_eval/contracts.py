"""Adapters see ONLY an Input, never the Task's answer or grader fields."""
from dataclasses import dataclass,field,asdict
from typing import Optional,Protocol


@dataclass(frozen=True)
class Input:
    question: str
    context: str = ''


@dataclass
class Result:
    answer: str = ''
    status: str = 'ok'
    calls: list = field(default_factory=list)
    messages: list = field(default_factory=list)
    model_calls: int = 0
    latency_s: float = 0.0
    usage: Optional[dict] = None
    attempts: list = field(default_factory=list)
    def to_dict(self):return asdict(self)


class Adapter(Protocol):
    def run(self,item:Input)->Result:...
