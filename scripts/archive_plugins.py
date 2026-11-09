"""Create release archives and a checksum list; never publish them."""
import argparse,hashlib,json,shutil
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--plugins',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False)
rows=[]
for agent in ('claude','codex','opencode'):
    bundle=a.plugins/agent
    metadata=json.loads((bundle/'platform.json').read_text())
    name=f"file-to-md-{agent}-{metadata['os']}-{metadata['cpu']}"
    archive=Path(shutil.make_archive(str(a.output/name),'zip',root_dir=bundle))
    rows.append(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name)
(a.output/'checksums.txt').write_text('\n'.join(rows)+'\n')
for name in ('install.sh','install.ps1'):
    shutil.copy2(Path(__file__).parent/name,a.output/name)
print(a.output)
