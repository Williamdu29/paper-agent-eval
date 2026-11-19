# Add an adapter without changing the evaluator

`paper_agent_eval.example:factory` is a complete non-paper example. It reverses
strings deterministically, reports zero model calls and unknown usage, and is
clearly labeled as an offline fixture.

A developer adapter can be as small as:

```python
from paper_agent_eval.contracts import Result

class MyAgent:
    def run(self, item):
        # item.question and item.context only; no task answers or rubric fields.
        return Result(answer=item.question[::-1], status="ok")

def factory(config, client):
    return MyAgent()
```

Install that module in the active environment and select it in JSON config:

```json
{"adapter":"my_adapter:factory","context":"Public information only","artifacts":[]}
```

List helper source/data paths in artifacts, so edits invalidate run identity.
`client` is None for explicitly unpaid examples; with --paid it is the same
DeepSeek client used by the judge. Send every paid request through it. A custom
adapter that bypasses the client cannot inherit cost accounting automatically.
Implement bounded execution, fresh state and meaningful status/trace fields.
Do not put credentials in adapter config or Result. Redaction is defense in
depth, not permission to log arbitrary secret data.

Prepare tasks and run exactly the same loop as the paper agent:

```sh
pae eval --tasks examples/reverse.tasks.jsonl --config examples/reverse.json --out runs/reverse
pae report --tasks examples/reverse.tasks.jsonl --records runs/reverse/records.jsonl
```

Implementing a custom adapter does not require editing evaluation.py,
grading.py or metrics.py. Those modules import no paper tools.
