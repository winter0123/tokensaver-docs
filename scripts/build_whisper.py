# SPDX-License-Identifier: MIT
# Copyright (c) 2026 winter0123 and tokensaver-docs contributors
"""Build a portable CPU whisper-cli from a pinned upstream source revision."""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

COMMIT='d1be6fde11ac6e0407606b4e42fe72d34add8037'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('output exists; choose a new directory')
    cmake=shutil.which('cmake') or str(Path(sys.executable).parent/('cmake.exe' if sys.platform=='win32' else 'cmake'))
    with tempfile.TemporaryDirectory(prefix='tokensaver-docs-whisper-build-') as tmp:
        source=Path(tmp)/'source';build=Path(tmp)/'build'
        subprocess.run(['git','clone','--depth','1','--branch','v1.9.5','https://github.com/ggml-org/whisper.cpp.git',str(source)],check=True)
        actual=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
        if actual!=COMMIT:raise ValueError('Unexpected whisper.cpp source revision')
        subprocess.run([cmake,'-S',str(source),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release','-DBUILD_SHARED_LIBS=OFF','-DGGML_NATIVE=OFF','-DGGML_OPENMP=OFF','-DGGML_METAL=OFF','-DGGML_ACCELERATE=OFF','-DWHISPER_BUILD_TESTS=OFF','-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded'],check=True)
        subprocess.run([cmake,'--build',str(build),'--config','Release','--target','whisper-cli','-j','2'],check=True)
        name='whisper-cli.exe' if sys.platform=='win32' else 'whisper-cli'
        binary=next(build.rglob(name))
        args.output.mkdir(parents=True)
        shutil.copy2(binary,args.output/name)
        shutil.copy2(source/'LICENSE',args.output/'WHISPER_LICENSE')
        print(args.output/name)

if __name__=='__main__':main()
