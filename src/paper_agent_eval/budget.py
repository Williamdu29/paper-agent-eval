"""Transactional, persistent reservations. Uncertain attempts never become free."""
from datetime import datetime,timezone,date
import os
from pathlib import Path
import sqlite3
import uuid
from .util import canonical,read_json,sqlite_db

PRICES=Path(__file__).parent/'data/pricing.json'


class BudgetExceeded(RuntimeError):pass


class Ledger:
    def __init__(self,path=None):
        self.path=Path(path or os.getenv('PAE_BUDGET_DB',str(Path.home()/'.local/state/paper-agent-eval/budget.sqlite3'))).expanduser()
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, model TEXT, reserved REAL, charged REAL, status TEXT, usage TEXT, created TEXT)')
    def connect(self):return sqlite_db(self.path,timeout=30)
    def reserve(self,model,amount):
        if amount<=0:raise ValueError('Positive reserve required')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            used=db.execute('SELECT COALESCE(SUM(charged),0) FROM requests').fetchone()[0]
            if used+amount>4.50:raise BudgetExceeded('Shared $4.50 stop threshold reached (hard project ceiling $5).')
            identifier=uuid.uuid4().hex
            db.execute('INSERT INTO requests VALUES (?,?,?,?,?,?,?)',(identifier,model,amount,amount,'reserved',None,datetime.now(timezone.utc).isoformat()))
        return identifier
    def settle(self,identifier,amount,status,usage=None):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT reserved,status FROM requests WHERE id=?',(identifier,)).fetchone()
            if not row or row[1]!='reserved':raise ValueError('Invalid or already settled reservation')
            db.execute('UPDATE requests SET charged=?,status=?,usage=? WHERE id=?',(amount,status,canonical(usage) if usage else None,identifier))
    def report(self):
        with self.connect() as db:
            count,exposure=db.execute('SELECT COUNT(*),COALESCE(SUM(charged),0) FROM requests').fetchone()
            uncertain=db.execute("SELECT COUNT(*) FROM requests WHERE status IN ('reserved','uncertain')").fetchone()[0]
            usage=[__import__('json').loads(r[0]) for r in db.execute('SELECT usage FROM requests WHERE usage IS NOT NULL')]
        return dict(request_groups=count,exposure_usd=exposure,uncertain_groups=uncertain,stop_threshold_usd=4.50,
                    ceiling_usd=5.0,usage_records=usage,basis='Conservative usage-based estimate + unresolved reservations, NOT provider invoice')


def rates(model):
    data=read_json(PRICES)
    if date.today()>date.fromisoformat(data['valid_until']):raise BudgetExceeded('Price verification expired; recheck official pricing before any paid request.')
    if model not in data['models']:raise BudgetExceeded('Unverified model price; paid request disabled')
    return data['models'][model]


def cost(model,prompt,completion):
    r=rates(model)
    return 1.25*(prompt*r['input_per_million']+completion*r['output_per_million'])/1_000_000


def reserve_bound(model,body,retries):
    # Byte-level tokenizers encode no more tokens than UTF-8 bytes for ordinary text.
    # 4x serialized JSON bytes + 8192 covers message/tool protocol framing conservatively.
    input_bound=4*len(canonical(body).encode())+8192
    return cost(model,input_bound,body['max_tokens'])*(retries+1),input_bound
