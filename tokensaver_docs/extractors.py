"""구조화된 파일의 텍스트를 AI 호출 없이 추출한다."""

import zipfile
import re
import posixpath
import xml.etree.ElementTree as ET
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from openpyxl import load_workbook
from openpyxl.utils.cell import column_index_from_string, get_column_letter
from pypdf import PdfReader

from .media import image_frames


def text_unit(key: str, title: str, text: str, warning: str = '') -> dict:
    return {'id': key, 'title': title, 'text': text, 'warning': warning}


def image_unit(key: str, title: str, source: Path) -> dict:
    return {'id': key, 'title': title, 'kind': 'image', 'path': source}


def image_units(key: str, title: str, source: Path, folder: Path):
    for number, count, frame in image_frames(source, folder):
        if count > 1:
            unit = image_unit(f'{key}-frame-{number}', f'{title} / 프레임 {number}/{count}', frame)
        else:
            unit = image_unit(key, title, frame)
        if number == 1:
            unit['original_image'] = source
        yield unit


def cell_text(cell) -> str:
    parts = []
    for block in cell.iter_inner_content():
        if isinstance(block, Table):
            parts.extend(' | '.join(cell_text(c) for c in row.cells) for row in block.rows)
        else:
            parts.append(block.text)
    return '\n'.join(parts)


def table_markdown(table: Table) -> str:
    rows = [' | '.join(cell_text(c).replace('|', '\\|').replace('\n', '<br>') for c in row.cells) for row in table.rows]
    if rows:
        rows.insert(1, ' | '.join('---' for _ in table.rows[0].cells))
    return '\n'.join(rows)


def safe_zip(path: Path) -> None:
    with zipfile.ZipFile(path) as z:
        if sum(i.file_size for i in z.infolist()) > 200 * 1024 * 1024:
            raise ValueError('문서 압축 해제 크기가 200MiB를 초과합니다.')


def embedded_images(path: Path, prefix: str, folder: Path, positions=None):
    with zipfile.ZipFile(path) as z:
        for index, info in enumerate(z.infolist()):
            if not info.filename.startswith(prefix) or info.is_dir():
                continue
            suffix = Path(info.filename).suffix.lower()
            if suffix not in ('.png', '.jpeg', '.jpg', '.webp', '.bmp', '.tiff', '.gif'):
                yield text_unit(f'asset-{index}', '내장 개체', f'{Path(info.filename).name}: 지원하지 않는 이미지 형식', '내장 개체를 원본에서 확인하세요.')
                continue
            target = folder / f'asset-{index}{suffix}'
            target.write_bytes(z.read(info))
            titles = (positions or {}).get(info.filename, [f'내장 이미지 {Path(info.filename).name}'])
            for occurrence, title in enumerate(titles):
                yield from image_units(f'asset-{index}-{occurrence}', title, target, folder)


def xlsx_image_positions(path, sheets):
    """Keep known cell anchors; absolute and unsupported drawing positions remain unplaced."""
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
          'xdr': 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing',
          'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
    rid = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
    positions = {}
    with zipfile.ZipFile(path) as archive:
        def relationships(part):
            rels = posixpath.join(posixpath.dirname(part), '_rels', posixpath.basename(part) + '.rels')
            if rels not in archive.namelist():
                return {}
            result = {}
            try:
                entries = ET.fromstring(archive.read(rels))
            except ET.ParseError:
                return {}
            for rel in entries:
                if rel.get('TargetMode') == 'External':
                    continue
                target = rel.get('Target', '')
                target = posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join(posixpath.dirname(part), target))
                if target.startswith('xl/') and target in archive.namelist():
                    result[rel.get('Id')] = target
            return result

        for title, sheet_path in sheets:
            sheet_rels = relationships(sheet_path)
            for drawing in ET.fromstring(archive.read(sheet_path)).findall('s:drawing', ns):
                part = sheet_rels.get(drawing.get(rid + 'id'))
                if not part:
                    continue
                drawing_rels = relationships(part)
                try:
                    anchors = ET.fromstring(archive.read(part))
                except ET.ParseError:
                    continue
                for anchor in anchors:
                    origin = anchor.find('xdr:from', ns)
                    if origin is None:
                        continue
                    try:
                        row = int(origin.findtext('xdr:row', namespaces=ns)) + 1
                        col = int(origin.findtext('xdr:col', namespaces=ns)) + 1
                    except (TypeError, ValueError):
                        continue
                    if not 1 <= row <= 1048576 or not 1 <= col <= 16384:
                        continue
                    coordinate = get_column_letter(col) + str(row)
                    for blip in anchor.findall('.//a:blip', ns):
                        image = drawing_rels.get(blip.get(rid + 'embed'))
                        if image:
                            positions.setdefault(image, []).append(f'시트: {title} / 이미지 {coordinate}')
    return positions


def sheet_bounds(path: Path, sheet_path: str) -> tuple[int, int]:
    max_row = max_col = 0
    with zipfile.ZipFile(path) as z, z.open(sheet_path) as stream:
        sheet_data = None
        for event, element in ET.iterparse(stream, events=('start', 'end')):
            tag = element.tag.rsplit('}', 1)[-1]
            if event == 'start':
                if tag == 'sheetData':
                    sheet_data = element
                continue
            if tag == 'row' and element.get('r'):
                max_row = max(max_row, int(element.get('r')))
            elif tag == 'c':
                match = re.fullmatch(r'([A-Z]{1,3})([1-9][0-9]*)', element.get('r', ''))
                if not match:
                    raise ValueError('셀 좌표를 확인할 수 없습니다.')
                max_col = max(max_col, column_index_from_string(match.group(1)))
                max_row = max(max_row, int(match.group(2)))
            if max_row * max(1, max_col) > 2_000_000 or max_col > 16384:
                raise ValueError('시트 영역이 너무 큽니다. 필요한 범위만 별도 저장하세요.')
            if tag in ('row', 'c'):
                element.clear()
            if tag == 'row' and sheet_data is not None:
                sheet_data.clear()
    return max_row, max_col


def word_blocks(container, prefix, folder, seen_assets):
    for index, block in enumerate(container.iter_inner_content(), 1):
        key = f'{prefix}-{index}'
        if isinstance(block, Table):
            if not any(e.tag in (qn('w:drawing'), qn('w:pict')) for e in block._element.iter()):
                yield text_unit(key, f'{prefix} 표 {index}', table_markdown(block))
            else:
                seen_cells = set()
                for row_no, row in enumerate(block.rows, 1):
                    for col_no, cell in enumerate(row.cells, 1):
                        if cell._tc in seen_cells:
                            continue
                        seen_cells.add(cell._tc)
                        yield from word_blocks(cell, f'{key}-행{row_no}-셀{col_no}', folder, seen_assets)
            continue
        text, sequence = [], 0
        for element in block._element.iter():
            if element.tag == qn('w:t'):
                text.append(element.text or '')
            elif element.tag in (qn('w:tab'), qn('w:br')):
                text.append('\t' if element.tag == qn('w:tab') else '\n')
            elif element.tag == qn('a:blip'):
                sequence += 1
                if ''.join(text).strip():
                    yield text_unit(f'{key}-text-{sequence}', f'{prefix} 문단 {index}', ''.join(text))
                text = []
                rid = element.get(qn('r:embed'))
                rel = block.part.rels.get(rid) if rid else None
                if rel is None or rel.is_external:
                    yield text_unit(f'{key}-image-{sequence}', '확인 사항', '외부 또는 확인할 수 없는 이미지', '원본 이미지를 확인하세요.')
                    continue
                asset = rel.target_part
                seen_assets.add(str(asset.partname).lstrip('/'))
                suffix = Path(str(asset.partname)).suffix.lower()
                if suffix not in ('.png', '.jpeg', '.jpg', '.webp', '.bmp', '.tiff', '.tif', '.gif'):
                    yield text_unit(f'{key}-image-{sequence}', '확인 사항', '지원하지 않는 내장 이미지', '원본 이미지를 확인하세요.')
                    continue
                image = folder / f'{key}-image-{sequence}{suffix}'
                image.write_bytes(asset.blob)
                yield from image_units(f'{key}-image-{sequence}', f'{prefix} 이미지 {index}', image, folder)
            elif element.tag == qn('w:pict'):
                yield text_unit(f'{key}-legacy', '확인 사항', '구형 그림 또는 도형', '원본에서 해당 위치를 확인하세요.')
        if ''.join(text).strip():
            yield text_unit(f'{key}-text-end', f'{prefix} 문단 {index}', ''.join(text))
        if any(e.tag == qn('w:drawing') for e in block._element.iter()) and not any(e.tag == qn('a:blip') for e in block._element.iter()):
            yield text_unit(f'{key}-drawing', '확인 사항', '해석할 수 없는 그림 또는 도형', '원본에서 해당 위치를 확인하세요.')
        if any(e.tag in (qn('w:txbxContent'), qn('w:ins'), qn('w:del')) for e in block._element.iter()):
            yield text_unit(f'{key}-unsupported', '확인 사항', '텍스트 상자 또는 변경 추적이 포함되어 있습니다.', '해당 내용의 전체 추출은 보장되지 않습니다.')


def extract(path: Path, folder: Path, vision_pages: set[int] | None = None):
    suffix = path.suffix.lower()
    if suffix == '.pdf':
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise ValueError('암호화된 PDF입니다. 암호를 해제한 사본을 사용하세요.')
        if vision_pages and (min(vision_pages) < 1 or max(vision_pages) > len(reader.pages)):
            raise ValueError('PDF 페이지 범위가 잘못되었습니다.')
        for n, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ''
            contents = page.get_contents()
            operators = {op for _, op in contents.operations} if contents is not None else set()
            has_visuals = bool(len(page.images)) or bool(operators & {b'S', b's', b'f', b'F', b'f*', b'B', b'B*', b'b', b'b*', b'Do', b'sh', b'INLINE IMAGE'})
            has_unreadable_text = not text.strip() and bool(operators & {b'Tj', b'TJ', b"'", b'"'})
            if n in (vision_pages or set()) or (not text.strip() and (has_visuals or has_unreadable_text)):
                yield {'id': f'page-{n}', 'title': f'페이지 {n}', 'kind': 'image', 'pdf_page': n, 'path': path}
            else:
                warning = '이 페이지의 그림·표 배치는 직접 추출만으로 확인되지 않았습니다. --vision-pages로 확인하세요.' if has_visuals else ''
                yield text_unit(f'page-{n}', f'페이지 {n}', text.strip() or '(빈 페이지)', warning)
    elif suffix == '.docx':
        safe_zip(path)
        doc = Document(path)
        seen_assets = set()
        yield from word_blocks(doc, '본문', folder, seen_assets)
        for i, section in enumerate(doc.sections, 1):
            for title, area in [('머리글', section.header), ('바닥글', section.footer)]:
                yield from word_blocks(area, f'{title}-{i}', folder, seen_assets)
        with zipfile.ZipFile(path) as z:
            xml = z.read('word/document.xml')
            if any(tag in xml for tag in (b'txbxContent', b'<w:ins', b'<w:del')):
                yield text_unit('unsupported', '확인 사항', '텍스트 상자 또는 변경 추적이 포함되어 있습니다.', '해당 내용의 전체 추출은 보장되지 않습니다.')
            missing = [n for n in z.namelist() if n.startswith('word/media/') and not n.endswith('/') and n not in seen_assets]
            if missing:
                yield text_unit('unplaced-media', '확인 사항', '위치를 확인하지 못한 내장 이미지: ' + ', '.join(Path(n).name for n in missing), '원본에서 이미지를 확인하세요.')
    elif suffix == '.xlsx':
        safe_zip(path)
        formulas = load_workbook(path, read_only=True, data_only=False)
        values = load_workbook(path, read_only=True, data_only=True)
        image_positions = xlsx_image_positions(path, [(sheet.title, sheet._worksheet_path) for sheet in formulas.worksheets])
        try:
            for i, sheet in enumerate(formulas.worksheets):
                max_row, max_col = sheet_bounds(path, sheet._worksheet_path)
                lines = ['| 셀 | 내용·수식 | 저장된 계산값 |', '| --- | --- | --- |']
                sheet.reset_dimensions()
                value_sheet = values[sheet.title]
                value_sheet.reset_dimensions()
                rows = sheet.iter_rows(max_row=max_row, max_col=max_col) if max_row and max_col else ()
                cached_rows = value_sheet.iter_rows(max_row=max_row, max_col=max_col) if max_row and max_col else ()
                for row, cached in zip(rows, cached_rows):
                    for cell, cached_cell in zip(row, cached):
                        if cell.value is None:
                            continue
                        text = str(cell.value).replace('|', '\\|').replace('\n', '<br>')
                        value = ''
                        if cell.data_type == 'f':
                            value = str(cached_cell.value) if cached_cell.value is not None else '계산값 없음'
                        lines.append(f'| {cell.coordinate} | {text} | {value} |')
                label = f'시트: {sheet.title}' + (' (숨김)' if sheet.sheet_state != 'visible' else '')
                yield text_unit(f'sheet-{i}', label, '\n'.join(lines))
        finally:
            formulas.close()
            values.close()
        with zipfile.ZipFile(path) as z:
            if any(n.startswith(('xl/charts/', 'xl/drawings/')) for n in z.namelist()):
                yield text_unit('drawings', '확인 사항', '차트·그림 또는 도형이 포함되어 있습니다.', '차트와 도형의 배치·의미는 원본에서 확인하세요.')
        yield from embedded_images(path, 'xl/media/', folder, image_positions)
    else:
        raise ValueError('지원하지 않는 문서 형식입니다.')
