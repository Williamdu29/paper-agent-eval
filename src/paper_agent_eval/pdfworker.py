"""Isolated pypdf parser; no network, no credentials required."""
import json
import sys
try:
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(1_500_000_000,1_500_000_000))
    resource.setrlimit(resource.RLIMIT_CPU,(30,30))
except (ImportError,ValueError):pass
import pypdf
reader=pypdf.PdfReader(sys.argv[1],strict=True)
if reader.is_encrypted:
    print(json.dumps({'error':'encrypted_pdf'}));raise SystemExit(0)
if len(reader.pages)>200:
    print(json.dumps({'error':'page_limit_exceeded'}));raise SystemExit(0)
pages=[]
for page in reader.pages:
    content=page.get_contents()
    if content and len(content.get_data())>20_000_000:raise SystemExit(2)
    pages.append(page.extract_text() or '')
print(json.dumps(dict(pages=pages,parser='pypdf/'+pypdf.__version__)))
