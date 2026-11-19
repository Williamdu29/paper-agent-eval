"""Authorized public release, once local auth/network and personal owner verify.
No force push, no global Git identity changes, no token printing.
"""
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def command(*args,capture=False):
    return subprocess.run(args,cwd=ROOT,check=True,text=True,stdout=subprocess.PIPE if capture else None,stderr=subprocess.PIPE if capture else None).stdout


def main():
    # Complete offline verification before any external mutation.
    command(sys.executable,'-m','unittest','discover','-s','tests','-v')
    command(sys.executable,'scripts/audit_release.py')
    try:user=json.loads(command('gh','api','user',capture=True))
    except subprocess.CalledProcessError:raise SystemExit('GitHub account could not be verified. Run gh auth login --hostname github.com in a network-enabled terminal, then retry. Never paste a token in chat.')
    login=user['login']
    if user.get('type')!='User' or not re.fullmatch('[A-Za-z0-9-]+',login):raise SystemExit('A verified personal GitHub account is required')
    if not (ROOT/'.git').exists():command('git','init','-b','main')
    remotes=command('git','remote',capture=True).splitlines()
    if remotes:raise SystemExit('Existing remote found; inspect it before releasing. No remote was changed.')
    # Name collisions, including existing repositories owned by this user, are never overwritten.
    selected=None
    for number in range(1,11):
        name='paper-agent-eval'+('' if number==1 else '-'+str(number))
        probe=subprocess.run(['gh','api','repos/'+login+'/'+name],cwd=ROOT,text=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        if probe.returncode and '404' in probe.stderr:selected=name;break
        if probe.returncode:raise SystemExit('Repository existence check failed; no repository created')
    if selected is None:raise SystemExit('No unused repository name found')
    for field,value in [('user.name',login),('user.email',str(user['id'])+'+'+login+'@users.noreply.github.com')]:
        existing=subprocess.run(['git','config','--get',field],cwd=ROOT,stdout=subprocess.PIPE,text=True)
        if not existing.stdout.strip():command('git','config','--local',field,value)
    # Explicit reviewed paths only; never git add .
    command('git','add','pyproject.toml','.gitignore','.env.example','README.md','NOTICE','src','tests','examples','docs','scripts','benchmarks','.github')
    command(sys.executable,'scripts/audit_release.py')
    staged=command('git','diff','--cached','--name-only',capture=True)
    if staged.strip():command('git','commit','-m','Build portable agent evaluation core and bounded arXiv research example')
    command(sys.executable,'scripts/audit_release.py')
    repository=login+'/'+selected
    command('gh','repo','create',repository,'--public','--source','.','--remote','origin','--description','Extensible agent evaluation with a budgeted arXiv/PDF research agent and reproducible benchmarks')
    command('git','push','-u','origin','main')
    command('gh','repo','edit',repository,'--default-branch','main','--add-topic','agent-evaluation','--add-topic','arxiv','--add-topic','tool-calling','--add-topic','llm')
    data=json.loads(command('gh','repo','view',repository,'--json','url,visibility,owner,defaultBranchRef',capture=True))
    local=command('git','rev-parse','HEAD',capture=True).strip()
    remote=command('git','ls-remote','origin','refs/heads/main',capture=True).split()[0]
    if data['visibility']!='PUBLIC' or data['owner']['login']!=login or data['defaultBranchRef']['name']!='main' or local!=remote:raise SystemExit('Post-push verification failed')
    print('Verified public repository:',data['url']);print('Verified commit:',local)
    command('gh','run','list','--repo',repository,'--limit','1','--json','status,conclusion,url')

if __name__=='__main__':main()
