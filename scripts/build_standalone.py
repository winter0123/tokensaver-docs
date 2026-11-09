"""Build one self-contained executable for the current OS and CPU."""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import hashlib
import urllib.request
from pathlib import Path
from importlib.metadata import distribution

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True, help='New directory for the executable')
    parser.add_argument('--whisper',type=Path,help='Directory built by build_whisper.py')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists; choose a new directory')
    with tempfile.TemporaryDirectory(prefix='tokensaver-docs-build-') as temporary:
        temp = Path(temporary)
        # python-docx resolves templates through docx/parts/../templates on disk.
        marker = temp / '.bundle-marker'
        marker.write_text('', encoding='utf-8')
        vocabulary=temp/'tiktoken-cache'
        vocabulary.mkdir()
        url='https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken'
        with urllib.request.urlopen(url,timeout=30) as response:data=response.read()
        if hashlib.sha256(data).hexdigest()!='223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7':
            raise ValueError('Unexpected tokenizer vocabulary')
        (vocabulary/hashlib.sha1(url.encode()).hexdigest()).write_bytes(data)
        notices=temp/'third-party'
        notices.mkdir()
        pdfium_dist=distribution('pypdfium2')
        for package in ('pypdfium2','markdownify','beautifulsoup4','soupsieve','six'):
            installed=distribution(package)
            license_files=[p for p in installed.files if '.dist-info/licenses/' in p.as_posix() or p.name.lower().startswith(('license','copying'))]
            if not license_files:
                raise ValueError('Redistribution licenses are missing: '+package)
            for item in license_files:
                target=notices/package/item
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(installed.locate_file(item),target)
        if args.whisper:
            shutil.copy2(args.whisper/'WHISPER_LICENSE',notices/'WHISPER_LICENSE')
        (notices/'README.txt').write_text('PDF rendering uses pypdfium2 '+pdfium_dist.version+' and PDFium. Upstream license texts, including PDFium dependency notices, are included here.\n',encoding='utf-8')
        command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onefile',
                   '--name', 'tokensaver-docs', '--distpath', str(temp / 'dist'),
                   '--workpath', str(temp / 'work'), '--specpath', str(temp),
                   '--collect-all', 'tiktoken', '--collect-data', 'docx', '--hidden-import', 'tiktoken_ext.openai_public',
                   '--collect-all', 'pypdfium2_raw', '--collect-data', 'pypdfium2',
                   '--add-data', str(notices)+os.pathsep+'third-party',
                   '--add-data', str(vocabulary)+os.pathsep+'tiktoken-cache',
                   '--add-data', str(ROOT/'tokensaver_docs/data') + os.pathsep + 'tokensaver_docs/data',
                   '--add-data', str(ROOT / 'skills/tokensaver-docs/SKILL.md') + os.pathsep + 'skills/tokensaver-docs',
                   '--add-data', str(marker) + os.pathsep + 'docx/parts',
                   str(ROOT / 'scripts/standalone.py')]
        if args.whisper:
            name='whisper-cli.exe' if os.name=='nt' else 'whisper-cli'
            command[3:3]=['--add-binary',str(args.whisper.resolve()/name)+os.pathsep+'whisper','--add-data',str(args.whisper.resolve()/'WHISPER_LICENSE')+os.pathsep+'whisper']
        subprocess.run(command, check=True, cwd=ROOT)
        args.output.mkdir(parents=True)
        name = 'tokensaver-docs.exe' if os.name == 'nt' else 'tokensaver-docs'
        shutil.copy2(temp / 'dist' / name, args.output / name)
        shutil.copytree(notices,args.output/'third-party')
        print(args.output / name)


if __name__ == '__main__':
    main()
