"""Non-paper deterministic fixture adapter. Not a model experiment."""
from .contracts import Result


class Reverse:
    def run(self,item):
        # No access to task type, expected, rubric, sources or grading config.
        return Result(answer=item.question[::-1],model_calls=0,usage=None)


def factory(config,client=None):return Reverse()
