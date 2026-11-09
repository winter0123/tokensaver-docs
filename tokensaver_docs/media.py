# SPDX-License-Identifier: MIT
# Copyright (c) 2026 winter0123 and tokensaver-docs contributors
"""OCR 없이 AI 입력용 이미지와 오디오를 준비한다."""

import math
import shutil
import subprocess
import threading
import wave
from pathlib import Path

from PIL import Image, ImageOps

_pdf_lock = threading.Lock()


def run_command(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    if not shutil.which(args[0]):
        raise ValueError(f'필요한 명령이 설치되지 않았습니다: {args[0]}')
    try:
        return subprocess.run(args, capture_output=True, check=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ValueError('미디어 처리 제한 시간을 초과했습니다.') from None
    except subprocess.CalledProcessError:
        raise ValueError('미디어 처리에 실패했습니다. 파일 형식과 손상 여부를 확인하세요.') from None


def normalize_image(source: Path, target: Path) -> Path:
    with Image.open(source) as im:
        if getattr(im, 'n_frames', 1) > 1:
            raise ValueError('다중 프레임 이미지는 프레임별로 나누어 처리해야 합니다.')
        im = ImageOps.exif_transpose(im)
        if im.width * im.height > 40_000_000:
            raise ValueError('이미지가 너무 큽니다. 4천만 화소 이하로 나눠 주세요.')
        # shortcut: 원본 해상도를 유지한다. 축소가 필요하면 사용자가 원본을 분할한다.
        if im.mode in ('RGBA', 'LA') or 'transparency' in im.info:
            rgba = im.convert('RGBA')
            im = Image.alpha_composite(Image.new('RGBA', im.size, 'white'), rgba)
        im.convert('RGB').save(target, 'PNG')
    return target


def image_frames(source: Path, folder: Path):
    with Image.open(source) as im:
        count = getattr(im, 'n_frames', 1)
        if count == 1:
            yield 1, 1, source
            return
        for index in range(count):
            im.seek(index)
            frame = folder / f'{source.stem}-frame-{index + 1}.png'
            ImageOps.exif_transpose(im.copy()).save(frame, 'PNG')
            yield index + 1, count, frame


def pdf_image(source: Path, page: int, folder: Path) -> Path:
    # PDFium forbids concurrent calls even when threads use different documents.
    with _pdf_lock:
        import pypdfium2 as pdfium
        try:
            document = pdfium.PdfDocument(str(source))
            try:
                if not isinstance(page, int) or not 1 <= page <= len(document):
                    raise ValueError('PDF 페이지 범위가 잘못되었습니다.')
                selected = document[page - 1]
                try:
                    size = selected.get_size()
                    if any(not math.isfinite(v) or v <= 0 for v in size):
                        raise ValueError('PDF 페이지 크기가 올바르지 않습니다.')
                    bitmap = selected.render(scale=2400 / max(size))
                    try:
                        target = folder / f'page-{page}.png'
                        with bitmap.to_pil() as image:
                            image.save(target, 'PNG')
                    finally:
                        bitmap.close()
                finally:
                    selected.close()
            finally:
                document.close()
        except pdfium.PdfiumError:
            raise ValueError('PDF 페이지 렌더링에 실패했습니다. 원본의 손상·암호화를 확인하세요.') from None
    return target


def pcm_audio(source: Path, target: Path) -> Path:
    import imageio_ffmpeg
    try:
        with wave.open(str(source), 'rb') as audio:
            if audio.getnchannels() == 1 and audio.getsampwidth() == 2 and audio.getframerate() == 16000 and audio.getcomptype() == 'NONE':
                shutil.copyfile(source, target)
                return target
    except (wave.Error, EOFError):
        pass
    # 시스템 코덱 라이브러리 상태와 분리된 프로젝트 전용 바이너리를 사용한다.
    run_command([imageio_ffmpeg.get_ffmpeg_exe(), '-nostdin', '-v', 'error', '-y', '-i', str(source), '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(target)])
    return target


def duration(source: Path) -> float:
    with wave.open(str(source), 'rb') as audio:
        seconds = audio.getnframes() / audio.getframerate()
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('오디오 길이를 확인할 수 없습니다.')
    return seconds


def intervals(seconds: float, chunk: float = 60, overlap: float = 1):
    if not math.isfinite(seconds) or seconds <= 0 or chunk <= overlap or overlap < 0:
        raise ValueError('오디오 분할 길이와 겹침 설정을 확인하세요.')
    start = 0.0
    while start < seconds:
        end = min(start + chunk, seconds)
        yield start, end
        if end == seconds:
            break
        start = end - overlap


def audio_chunk(source: Path, start: float, end: float, target: Path) -> Path:
    with wave.open(str(source), 'rb') as audio:
        rate = audio.getframerate()
        audio.setpos(round(start * rate))
        with wave.open(str(target), 'wb') as chunk:
            chunk.setparams(audio.getparams())
            chunk.writeframes(audio.readframes(round((end - start) * rate)))
    return target
