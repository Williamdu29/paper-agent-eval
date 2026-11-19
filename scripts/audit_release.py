"""Read-only release scan, including staged files and all commit blobs.
Known secrets may be loaded in memory from an explicit --known-env-file.
No keys or private paths are printed. Never calls a paid service.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess

parser=argparse.ArgumentParser();parser.add_argument('--known-env-file');args=parser.parse_args()
root=Path(__file__).resolve().parents[1];secrets=[]
if os.getenv('DEEPSEEK_API_KEY'):secrets.append(os.environ['DEEPSEEK_API_KEY'].encode())
if args.known_env_file:
    for line in Path(args.known_env_file).read_text().splitlines():
        key,sep,value=line.partition('=')
        if sep and key.strip()=='DEEPSEEK_API_KEY' and value.strip():secrets.append(value.strip().strip('"').strip("'").encode())
# Split patterns so this scanner does not flag its own policy text.
private=re.compile(rb'/Users/'+rb'[^\s"\']+|/home/'+rb'[^\s"\']+')
course=re.compile(rb'EEP'+rb'500D|HW'+rb'6|Net'+rb'ID|submission'+rb'\.zip',re.I)
key_pattern=re.compile(rb'sk-'+rb'[A-Za-z0-9]{20,}')
findings=[]
def scan(label,data):
    for kind,pattern in [('private-path',private),('excluded-context',course),('credential-pattern',key_pattern)]:
        if pattern.search(data):findings.append((label,kind))
    if any(key in data for key in secrets):findings.append((label,'known-secret'))

ignored={'.git','.venv','.local-run','.cache','runs','__pycache__','build','dist'}
for p in root.rglob('*'):
    relative=p.relative_to(root)
    if any(part in ignored or part.endswith('.egg-info') for part in relative.parts) or p.name=='.env':continue
    if p.is_file():
        if p.suffix in ('.pdf','.zip','.key','.pem'):findings.append((str(relative),'excluded-file-type'))
        else:scan(str(relative),p.read_bytes())
if (root/'.git').exists():
    def git(*cmd):return subprocess.check_output(['git',*cmd],cwd=root,stderr=subprocess.DEVNULL)
    staged=git('diff','--cached','--name-only','--diff-filter=ACMR').decode().splitlines()
    for name in staged:
        if Path(name).name=='.env':findings.append((name,'staged-dotenv'))
        scan('staged:'+name,git('show',':'+name))
    try:commits=git('rev-list','--all').decode().splitlines()
    except subprocess.CalledProcessError:commits=[]
    for commit in commits:
        for name in git('ls-tree','-r','--name-only',commit).decode().splitlines():
            if Path(name).name=='.env' or Path(name).suffix in ('.pdf','.zip','.key','.pem'):findings.append(('history:'+name,'excluded-file-type'))
            scan('history:'+name,git('show',commit+':'+name))
    for remote in git('remote','-v').decode().splitlines():
        if re.search(r'https?://[^\s/]+@',remote):findings.append(('remote','credential-bearing-url'))
for label,kind in sorted(set(findings)):print(label+': '+kind)
if findings:raise SystemExit(1)
print('PASS: candidates, staged files, all accessible commit blobs and remotes scanned; no secret values printed.')
