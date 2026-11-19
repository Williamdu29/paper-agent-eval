import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)


def append_jsonl(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as stream:
        stream.write(canonical(value)+'\n');stream.flush();os.fsync(stream.fileno())


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def load_env(path=None):
    # Explicit file only, no ancestor/home search. Never import an unrelated project's secrets.
    if path:
        for line in Path(path).read_text().splitlines():
            key,sep,value=line.partition('=')
            if sep and key.strip() in {'DEEPSEEK_API_KEY','DEEPSEEK_MODEL','PAE_BUDGET_DB'}:
                os.environ.setdefault(key.strip(),value.strip().strip('"').strip("'"))


def redact(value):
    if isinstance(value,dict):
        return {k:('[REDACTED]' if re.search(r'key|secret|token|authorization|password',k,re.I) and k not in {'prompt_tokens','completion_tokens','total_tokens','max_tokens','tokens'} else redact(v)) for k,v in value.items()}
    if isinstance(value,list):return [redact(v) for v in value]
    if isinstance(value,str):
        key=os.getenv('DEEPSEEK_API_KEY','')
        if key:value=value.replace(key,'[REDACTED]')
        return re.sub(r'(?i)Bearer\s+[^\s"\']+','Bearer [REDACTED]',value)
    return value


from contextlib import contextmanager
import sqlite3


@contextmanager
def sqlite_db(path,timeout=30):
    db=sqlite3.connect(path,timeout=timeout)
    try:
        with db:yield db
    finally:
        db.close()
