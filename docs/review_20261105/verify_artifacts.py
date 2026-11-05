"""Read-only check of exported files, data provenance and local Markdown links."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from PIL import Image
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
manifest=json.loads((HERE/'figures/manifest.json').read_text(encoding='utf-8'))
checks=[]
for fig in manifest['figures']:
    for src,sha in fig['source_sha256'].items():
        assert hashlib.sha256((ROOT/src).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==sha,src
    for item in fig['outputs']:
        p=ROOT/item['path']
        assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],str(p)
        info={'path':item['path'],'bytes':p.stat().st_size,'sha256_verified':True}
        if p.suffix=='.png':
            with Image.open(p) as im: info.update(size=im.size,mode=im.mode)
        elif p.suffix=='.pdf':
            pdf=PdfReader(p);assert len(pdf.pages)==1
            info['pages']=len(pdf.pages)
        else:
            root=ET.parse(p).getroot()
            info['text_elements']=len(root.findall('.//{http://www.w3.org/2000/svg}text'))
            assert info['text_elements']>0
        checks.append(info)
links=[]
for doc in [HERE/'README.md',HERE/'FIGURES.md']:
    for target in re.findall(r'\]\(([^)]+)\)',doc.read_text(encoding='utf-8')):
        if target.startswith(('http:','https:','#')):continue
        p=doc.parent/target.split('#')[0]
        assert p.exists(),str(p)
        links.append({'doc':doc.name,'target':target})
baseline=manifest['reviewed_commit']
diff=subprocess.check_output(['git','diff','--name-only',baseline],cwd=ROOT,text=True).splitlines()
assert all(p=='README.md' or p.startswith('docs/review_20261105/') for p in diff),diff
report={'passed':True,'verified_exports':len(checks),'figures':len(manifest['figures']),
    'checks':checks,'relative_links_checked':len(links),
    'reviewed_commit':baseline,
    'original_tracked_files_modified':[p for p in diff if not p.startswith('docs/review_20261105/')],
    'original_figures_and_algorithms_unchanged':True,
    'visual_review':'All seven inspected; architecture redrawn in FAST-LIVO2 visual style, routing and text checked at full size.',
    'scope':'Artifact and provenance checks only; no scientific efficacy certification.'}
(HERE/'artifact_check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:report[k] for k in ['passed','verified_exports','figures','relative_links_checked','original_tracked_files_modified']},ensure_ascii=False))
