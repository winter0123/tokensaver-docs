"""한국어 명령줄 인터페이스."""

import argparse
import json
import shutil
import sys
import subprocess
import os
from pathlib import Path

from . import __version__
from .engine import AUDIO, DOCUMENTS, IMAGES, convert, discover
from .providers import ConversionError, eligible, list_models, whisper_paths
from .storage import atomic_write, config_path, load_profiles, load_state, digest
from .shared_cache import cache_root


def positive(value):
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError('1 이상을 입력하세요.')
    return n


def token_encoder(name):
    bundled = Path(getattr(sys, '_MEIPASS', '')) / 'tiktoken-cache'
    if getattr(sys, 'frozen', False) and bundled.is_dir():
        os.environ.setdefault('TIKTOKEN_CACHE_DIR', str(bundled))
    try:
        import tiktoken
    except ImportError:
        raise ValueError('토큰 측정에는 file-to-md[tokens] 설치가 필요합니다.') from None
    try:
        return tiktoken.get_encoding(name)
    except ValueError:
        raise ValueError('알 수 없는 토큰 인코딩입니다.') from None


def page_set(value: str) -> set[int]:
    pages = set()
    try:
        for part in value.split(','):
            if '-' in part:
                a, b = map(int, part.split('-', 1))
                if a > b or b - a > 10000:
                    raise ValueError()
                pages.update(range(a, b + 1))
            else:
                pages.add(int(part))
        if not pages or min(pages) < 1:
            raise ValueError()
    except ValueError:
        raise argparse.ArgumentTypeError('페이지는 1,3-5처럼 지정하세요.') from None
    return pages


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='문서는 직접 추출하고 이미지·음성은 선택한 AI로 전사합니다.')
    p.add_argument('--version', action='version', version=__version__)
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('mcp', help='로컬 MCP 서버 실행')
    prepare = sub.add_parser('prepare', help='원본을 모델에 읽히지 않고 문서와 이미지를 준비; JSON 상태만 반환')
    prepare.add_argument('input', type=Path)
    prepare.add_argument('--output', type=Path, default=Path('converted'))
    choice = prepare.add_mutually_exclusive_group()
    choice.add_argument('--transcribe-images', action='store_true', dest='transcribe_images', default=None, help='선택한 모델로 이미지 속 글자와 설명을 MD에 포함')
    choice.add_argument('--skip-image-transcription', action='store_false', dest='transcribe_images', help='이미지만 저장하고 내용은 정리하지 않음')
    prepare.add_argument('--image-mode', choices=('analyze', 'preserve', 'placeholder'), help='이미지·글자·설명 / 이미지만 / [이미지] 위치 표시')
    prepare.add_argument('--model-provider', choices=('openrouter', 'codex', 'claude'))
    prepare.add_argument('--model', help='이번 변환에만 사용할 모델')
    prepare.add_argument('--allow-unverified-model', action='store_true', help='지원 여부가 확인되지 않은 모델 사용에 명시적 동의')
    model_setup = sub.add_parser('setup-model', help='최초 변환 모델 선택·확인·나중에 설정')
    model_setup.add_argument('--provider', choices=('openrouter', 'codex', 'claude'))
    model_setup.add_argument('--model')
    model_setup.add_argument('--defer', action='store_true')
    model_setup.add_argument('--save-as-default', action='store_true')
    model_setup.add_argument('--confirmed', action='store_true')
    setup = sub.add_parser('setup-audio',help='선택한 다국어 Whisper 모델 준비')
    setup.add_argument('--model',choices=('tiny','base','small'),required=True)
    setup.add_argument('--download',action='store_true',help='선택한 모델 다운로드·설정에 동의')
    install_plugin = sub.add_parser('install-plugin', help='검증된 로컬 플러그인 패키지를 설치하고 에이전트에 연결')
    install_plugin.add_argument('bundle',type=Path)
    install_plugin.add_argument('--agent',choices=('claude','codex','opencode'),required=True)
    install_plugin.add_argument('--destination',type=Path)
    install_plugin.add_argument('--config-dir',type=Path)
    install_plugin.add_argument('--expected-version', help='Release 설치기가 요청한 패키지 버전')
    context = sub.add_parser('context', help='변환 결과를 재사용하고 필요한 근거를 JSON으로 반환')
    context.add_argument('input', type=Path)
    context.add_argument('query')
    context.add_argument('--output', type=Path, default=Path('converted'))
    context.add_argument('--max-tokens', type=positive)
    context.add_argument('--max-chars', type=positive, default=6000)
    context.add_argument('--use-configured-providers', action='store_true')
    doctor = sub.add_parser('doctor', help='설치와 선택 기능 진단: 네트워크 호출 없음')
    install = sub.add_parser('install-skill', help='선택한 에이전트에 스킬 설치')
    install.add_argument('--agent', choices=('codex', 'claude'), required=True)
    install.add_argument('--destination', type=Path, help='스킬을 설치할 상위 디렉터리')
    inspect = sub.add_parser('inspect', help='처리 대상과 크기 확인: AI 호출 없음')
    inspect.add_argument('input', type=Path)
    inspect.add_argument('--output', type=Path, default=Path('converted'))
    inspect.add_argument('--limit', type=positive, default=50)
    c = sub.add_parser('convert', help='파일 또는 폴더를 변환')
    c.add_argument('input', type=Path)
    c.add_argument('--output', type=Path, default=Path('converted'))
    c.add_argument('--config', type=Path)
    c.add_argument('--no-configured-providers', action='store_true', help='설정된 외부 전사 제공자를 사용하지 않음')
    c.add_argument('--refresh', action='store_true', help='기존 결과를 보존하고 명시적으로 새로 변환')
    c.add_argument('--transcribe-images', action='store_true', default=None, help='이미지 속 글자와 설명을 선택한 모델로 정리 (음성 제외)')
    c.add_argument('--image-mode', choices=('analyze', 'preserve', 'placeholder'))
    c.add_argument('--use-configured-audio-provider', action='store_true', help='이미지 정리와 함께 설정된 음성 제공자도 사용')
    c.add_argument('--vision-pages', type=page_set, default=set(), help='AI로 전사할 PDF 페이지: 1,3-5')
    c.add_argument('--chunk-seconds', type=positive, default=60)
    cfg = sub.add_parser('configure', help='이미지·오디오 모델을 사람이 선택')
    cfg.add_argument('--kind', choices=('image', 'audio'))
    cfg.add_argument('--provider', choices=('openrouter', 'codex', 'claude', 'whisper.cpp'))
    cfg.add_argument('--model')
    cfg.add_argument('--config', type=Path)
    models = sub.add_parser('models', help='현재 무료 오픈라우터 모델 목록 조회: 추론 호출 없음')
    models.add_argument('--kind', choices=('image', 'audio'), default='image')
    models.add_argument('--limit', type=positive, default=50)
    status = sub.add_parser('status', help='변환 진행과 확인 사항 조회')
    status.add_argument('--output', type=Path, default=Path('converted'))
    status.add_argument('--limit', type=positive, default=50)
    search = sub.add_parser('search', help='변환한 문서에서 문자 그대로 검색')
    search.add_argument('query')
    search.add_argument('--output', type=Path, default=Path('converted'))
    search.add_argument('--limit', type=positive, default=10)
    search.add_argument('--max-chars', type=positive, default=4000)
    search.add_argument('--context', type=int, default=0, help='일치한 줄의 앞뒤 문맥 줄 수 (0~10)')
    search.add_argument('--all-versions', action='store_true', help='기록된 이전 결과도 검색')
    search.add_argument('--max-tokens', type=positive, help='검색 결과 본문 토큰 상한 (선택 패키지 tokens 필요)')
    search.add_argument('--encoding', default='cl100k_base', help='토큰 측정에 사용할 인코딩')
    outline = sub.add_parser('outline', help='변환된 문서의 제목과 위치 확인')
    outline.add_argument('file', type=Path)
    outline.add_argument('--limit', type=positive, default=50)
    outline.add_argument('--max-chars', type=positive, default=4000)
    count_tokens = sub.add_parser('count-tokens', help='지정한 토큰 인코딩으로 텍스트 파일 측정')
    count_tokens.add_argument('file', type=Path)
    count_tokens.add_argument('--encoding', default='cl100k_base')
    read = sub.add_parser('read', help='마크다운 일부 읽기')
    read.add_argument('file', type=Path)
    read.add_argument('--page', type=positive)
    read.add_argument('--start-line', type=positive, default=1)
    read.add_argument('--lines', type=positive, default=60)
    read.add_argument('--max-chars', type=positive, default=6000)
    read.add_argument('--max-tokens', type=positive, help='본문 토큰 상한 (선택 패키지 tokens 필요)')
    read.add_argument('--encoding', default='cl100k_base')
    return p



def search_matches(paths, query):
    phrase = query.casefold()
    terms = phrase.split()
    # 정확한 문구부터 반환하고, 여러 단어는 같은 줄에 모두 있는 결과를 뒤에 둔다.
    for phrase_pass in (True, False) if len(terms) > 1 else (True,):
        for path in paths:
            lines = path.read_text(encoding='utf-8').splitlines()
            for number, line in enumerate(lines, 1):
                folded = line.casefold()
                exact = phrase in folded
                match = exact if phrase_pass else not exact and all(term in folded for term in terms)
                if match:
                    yield path, number, lines


def configure(args) -> None:
    if not all((args.kind, args.provider, args.model)) and not sys.stdin.isatty():
        raise ValueError('비대화형 실행에서는 --kind, --provider, --model을 모두 지정하세요.')
    kind = args.kind or input('입력 종류 선택 (image=이미지 / audio=오디오): ').strip()
    provider = args.provider or input('제공자 선택 (openrouter / codex / claude / whisper.cpp): ').strip()
    if kind not in ('image', 'audio') or provider not in ('openrouter', 'codex', 'claude', 'whisper.cpp'):
        raise ValueError('입력 종류 또는 제공자를 확인하세요.')
    if provider == 'whisper.cpp' and kind != 'audio':
        raise ValueError('whisper.cpp는 오디오에만 사용할 수 있습니다.')
    if kind == 'audio' and provider in ('codex', 'claude'):
        raise ValueError('코덱스·클로드 코드의 오디오 직접 입력은 지원하지 않습니다.')
    model = args.model
    if not model:
        if provider == 'openrouter':
            available = [m for m in list_models() if eligible(m, kind)]
            for n, m in enumerate(available, 1):
                print(f"{n}. {m['id']}")
            if not available:
                raise ValueError('현재 확인 가능한 무료 지원 모델이 없습니다.')
            choice = input('사용할 모델 번호: ').strip()
            if not choice.isdigit() or not 1 <= int(choice) <= len(available):
                raise ValueError('목록의 번호를 선택하세요.')
            model = available[int(choice) - 1]['id']
        else:
            model = input('다국어 모델 파일 경로: ' if provider == 'whisper.cpp' else '현재 계정에서 사용할 정확한 모델 이름: ').strip()
    if not model or not model.strip():
        raise ValueError('모델 이름이 비어 있습니다.')
    if provider == 'openrouter' and not any(m.get('id') == model and eligible(m, kind) for m in list_models()):
        raise ValueError('무료 가격과 입력 형식이 확인된 모델만 선택할 수 있습니다.')
    if provider == 'whisper.cpp':
        model = str(whisper_paths(model)[0])
    path = args.config or config_path()
    profiles = load_profiles(path)
    profiles[kind] = {'provider': provider, 'model': model.strip()}
    atomic_write(path, json.dumps(profiles, ensure_ascii=False, indent=2))
    if kind == 'image' and args.config is None:
        from .model_setup import select_model
        select_model(provider, model, save_as_default=True, confirmed=True)
    print(f'설정 저장: {path}\n선택: {kind} / {provider} / {model}')
    if provider == 'whisper.cpp':
        print('로컬 실행: 음성을 외부로 전송하지 않으며 API 요금이 없습니다.')
    elif provider != 'openrouter':
        print('기존 CLI 로그인 계정의 구독 한도 또는 해당 계정 과금 조건이 적용됩니다.')


def mcp_entry() -> None:
    try:
        from .mcp_server import run
    except ModuleNotFoundError as error:
        if error.name == 'mcp' or (error.name or '').startswith('mcp.'):
            print('MCP 서버에는 file-to-md[mcp] 설치가 필요합니다.', file=sys.stderr)
            raise SystemExit(2) from None
        raise
    run()


def main(argv=None) -> int:
    # Windows redirected output must preserve Korean prompts and UTF-8 Markdown paths.
    if sys.platform == 'win32':
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, 'reconfigure'):
                stream.reconfigure(encoding='utf-8')
    args = parser().parse_args(argv)
    try:
        if args.command == 'prepare':
            from .preparation import prepare_documents
            result = prepare_documents(args.input, args.output, transcribe_images=args.transcribe_images, image_mode=args.image_mode, model_provider=args.model_provider, model=args.model, allow_unverified_model=args.allow_unverified_model, onboarding=True)
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result['status'] in ('ready', 'needs_review') else 2
        elif args.command == 'setup-model':
            from .model_setup import select_model
            result = select_model(args.provider, args.model, defer=args.defer, save_as_default=args.save_as_default, confirmed=args.confirmed)
            print(json.dumps(result, ensure_ascii=False))
            return 2 if result['status'] in ('setup_required', 'confirmation_required') else 0
        elif args.command == 'setup-audio':
            from .audio_setup import setup_audio
            print(json.dumps(setup_audio(args.model,confirmed=args.download),ensure_ascii=False))
        elif args.command == 'install-plugin':
            from .installer import install_bundle
            print(install_bundle(args.bundle,args.agent,destination=args.destination,config_dir=args.config_dir,expected_version=args.expected_version))
        elif args.command == 'context':
            from .context import document_context
            print(json.dumps(document_context(args.input,args.query,args.output,max_tokens=args.max_tokens,max_chars=args.max_chars,use_configured_providers=args.use_configured_providers),ensure_ascii=False))
        elif args.command == 'mcp':
            mcp_entry()
        elif args.command == 'doctor':
            print(f'Python: {sys.version.split()[0]}')
            import pypdfium2
            print(f'PDF renderer: PDFium ({pypdfium2.PYPDFIUM_INFO.version})')
            for command in ('whisper-cli', 'codex', 'claude'):
                print(f'{command}: {shutil.which(command) or "없음 (선택 기능)"}')
            for kind, profile in load_profiles().items():
                print(f"{kind}: {profile['provider']} / {profile['model']}")
        elif args.command == 'install-skill':
            local = Path(__file__).resolve().parent.parent / 'skills' / 'file-to-md' / 'SKILL.md'
            packaged = Path(sys.prefix) / 'share' / 'file-to-md' / 'skills' / 'file-to-md' / 'SKILL.md'
            source = local if local.is_file() else packaged
            if not source.is_file():
                raise ValueError('배포 패키지에 스킬이 없습니다. 설치를 확인하세요.')
            base = args.destination or Path.home() / ('.codex' if args.agent == 'codex' else '.claude') / 'skills'
            target = base / 'file-to-md' / 'SKILL.md'
            if target.exists() or target.is_symlink():
                if target.is_file() and target.read_bytes() == source.read_bytes():
                    print(f'이미 설치됨: {target}')
                    return 0
                raise ValueError('기존 스킬을 보존했습니다. 다른 설치 위치를 선택하세요.')
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(source.read_bytes())
            print(f'설치됨: {target}')
        elif args.command == 'configure':
            configure(args)
        elif args.command == 'models':
            models = [m for m in list_models() if eligible(m, args.kind)]
            for m in models[:args.limit]:
                print(m['id'])
            print(f'무료 입력 지원 후보 {len(models)}개. 실제 계정 가용성은 요청 시 확인됩니다.')
        elif args.command == 'inspect':
            files = discover(args.input, args.output)
            for f in files[:args.limit]:
                kind = '문서 직접 추출·내장 이미지 확인' if f.suffix.lower() in DOCUMENTS else '이미지 AI' if f.suffix.lower() in IMAGES else '오디오 AI'
                print(f'{kind}\t{f.stat().st_size:,}바이트\t{f}')
            print(f'대상 {len(files)}개. AI 호출 없음. 스캔 페이지·내장 개체는 변환 시 판별합니다.')
        elif args.command == 'convert':
            profiles = {} if args.no_configured_providers else load_profiles(args.config)
            image_options = {}
            if not args.no_configured_providers and args.config is None:
                from .model_setup import load_model_selection
                selected = load_model_selection(legacy_profiles=profiles)
                if selected:
                    profiles = {**profiles, 'image': selected}
                    if load_model_selection(legacy_profiles={}):
                        image_options['image_model_key'] = digest(json.dumps(selected, sort_keys=True).encode())
            if (args.transcribe_images or args.vision_pages or args.image_mode) and not args.use_configured_audio_provider:
                profiles = {kind: profile for kind, profile in profiles.items() if kind != 'audio'}
            print(f'출력: {args.output.resolve()}')
            for kind, profile in profiles.items():
                location = '로컬 처리·외부 전송 없음' if profile['provider'] == 'whisper.cpp' else '해당 입력만 외부 전송'
                print(f"AI 선택: {kind} / {profile['provider']} / {profile['model']} ({location})")
            result = convert(args.input, args.output, profiles=profiles, vision_pages=args.vision_pages, chunk_seconds=args.chunk_seconds, cache_dir=cache_root(), refresh=args.refresh, transcribe_images=args.transcribe_images, **image_options, **({'image_mode': args.image_mode} if args.image_mode else {}))
            for r in result:
                print(f"{r['status']}\t{r['file']}\tAI 요청 {r.get('ai_calls', 0)}회" + ('\t캐시 재사용' if r.get('cached') else '') + ('\t결과: ' + r['output'] if r.get('output') else '') + ('\t' + r['detail'] if r.get('detail') else ''))
            print(f'파일 {len(result)}개 처리. 본문은 read 또는 search로 확인하세요.')
            if not result:
                print('지원하는 입력 파일이 없습니다.', file=sys.stderr)
                return 2
            return 2 if any(r['status'] in ('실패', '부분완료', '차단', '충돌') for r in result) else 0
        elif args.command == 'status':
            records = load_state(args.output)['records']
            for name, r in list(records.items())[:args.limit]:
                print(f"{r.get('status', '진행중')}\t{r.get('current_output', name)}\t완료 구간 {len(r.get('units', {}))}개")
                for warning in r.get('warnings', []):
                    print('  확인 필요: ' + warning)
            print(f'기록 {len(records)}개')
        elif args.command == 'search':
            if not args.query.strip():
                raise ValueError('검색어가 비어 있습니다.')
            if not 0 <= args.context <= 10:
                raise ValueError('문맥 줄 수는 0~10이어야 합니다.')
            used, count = 0, 0
            selected = ''
            encoding = None
            if args.max_tokens:
                encoding = token_encoder(args.encoding)
            old_paths = set()
            statuses = {}
            for name, record in load_state(args.output)['records'].items():
                current = record.get('current_output', name)
                statuses[str(current)] = record.get('status', '진행중')
                if not args.all_versions:
                    for old in [name, *record.get('output_history', [])]:
                        if old != current:
                            old_paths.add(str(old))
            paths = [p for p in sorted(args.output.rglob('*.md'))
                     if not p.is_symlink() and '.file-to-md' not in p.parts
                     and str(p.relative_to(args.output)) not in old_paths]
            for p, n, lines in search_matches(paths, args.query):
                start, end = max(0, n - 1 - args.context), min(len(lines), n + args.context)
                item = f'{p}:{start + 1}: {lines[start]}'
                item += ''.join(f'\n  {i + 1}: {lines[i]}' for i in range(start + 1, end))
                heading = next((line for line in reversed(lines[:n]) if line.startswith('## ')), '')
                status = statuses.get(str(p.relative_to(args.output)))
                if (heading and heading not in lines[start:end]) or status:
                    item = f'[구간: {heading or "없음"} / 상태: {status or "기록 없음"}]\n' + item
                if encoding and len(encoding.encode(selected + item + '\n', disallowed_special=())) > args.max_tokens:
                    print('토큰 제한에 도달했습니다. 더 구체적인 검색어나 큰 예산을 사용하세요.')
                    return 0
                remaining = args.max_chars - used
                if remaining <= 0 or count >= args.limit:
                    print('출력 제한에 도달했습니다. read로 해당 위치를 확인하세요.')
                    return 0
                print(item[:remaining])
                selected += item[:remaining] + '\n'
                used += len(item[:remaining])
                count += 1
            print(f'검색 결과 {count}개')
        elif args.command == 'count-tokens':
            tokenizer = token_encoder(args.encoding)
            text = args.file.read_text(encoding='utf-8')
            print(f'인코딩: {args.encoding}\n토큰: {len(tokenizer.encode(text, disallowed_special=()))}\n문자: {len(text)}')
        elif args.command == 'outline':
            if args.file.suffix.lower() != '.md':
                raise ValueError('outline은 변환된 .md 파일을 읽습니다.')
            used = count = 0
            for number, line in enumerate(args.file.read_text(encoding='utf-8').splitlines(), 1):
                if not line.startswith('#') or not line.lstrip('#').startswith(' '):
                    continue
                item = f'{args.file}:{number}: {line}'
                if count >= args.limit or used + len(item) > args.max_chars:
                    print('출력 제한에 도달했습니다.')
                    break
                print(item)
                used += len(item)
                count += 1
            print(f'제목 {count}개')
        elif args.command == 'read':
            if args.file.suffix.lower() != '.md':
                raise ValueError('read는 변환된 .md 파일을 읽습니다.')
            lines = args.file.read_text(encoding='utf-8').splitlines()
            start, end = args.start_line - 1, len(lines)
            if args.page:
                marker = f'## 페이지 {args.page}'
                start = next((i for i, line in enumerate(lines) if line == marker), -1)
                if start == -1:
                    raise ValueError('해당 페이지가 없습니다.')
                end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith('## 페이지 ')), len(lines))
            end = min(end, start + args.lines)
            if args.max_tokens:
                encoding = token_encoder(args.encoding)
                chosen = []
                for i in range(start, end):
                    candidate = '\n'.join([*chosen, f'{i + 1}: {lines[i]}'])
                    if len(encoding.encode(candidate, disallowed_special=())) > args.max_tokens:
                        break
                    chosen.append(f'{i + 1}: {lines[i]}')
                next_line = start + len(chosen) + 1
                text = '\n'.join(chosen)
                if not chosen and start < end:
                    print('토큰 제한 때문에 한 줄도 반환하지 못했습니다. 예산을 늘려 주세요.')
                    return 0
                print(text[:args.max_chars])
                if len(text) > args.max_chars:
                    print(f'글자 제한으로 잘렸습니다. --start-line {start + 1}에서 --max-chars 값을 늘려 읽으세요.')
                elif next_line <= len(lines):
                    print(f'추가 내용은 --start-line {next_line} --lines로 확인하세요.')
                return 0
            text = '\n'.join(f'{i + 1}: {lines[i]}' for i in range(start, end))
            print(text[:args.max_chars])
            if end < len(lines) or len(text) > args.max_chars:
                if len(text) > args.max_chars:
                    print(f'글자 제한으로 잘렸습니다. --start-line {start + 1}에서 --max-chars 값을 늘려 읽으세요.')
                else:
                    print(f'추가 내용은 --start-line {end + 1} --lines로 확인하세요.')
        return 0
    except KeyboardInterrupt:
        print('중단했습니다. 완료 구간은 캐시에 보존됩니다.', file=sys.stderr)
        return 130
    except (ValueError, OSError, ConversionError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f'오류: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
