"""Project-local research storage and bounded reuse."""
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import quote, urlsplit

from .engine import AUDIO, IMAGES, SUPPORTED, convert, output_lock
from .shared_cache import cache_root
from .storage import atomic_write, digest, file_hash, load_state, publish_new

STORE = Path('docs/tokensaver-docs')
INBOX = Path('docs/research/inbox')
LIMIT = 100 * 1024 * 1024
VERSION = re.compile(r'[0-9a-f]{64}')
REPORT_SUFFIX = '.research.json'
ROUTING = json.loads(Path(__file__).with_name('data').joinpath('research-routing.json').read_text(encoding='utf-8'))
RESEARCH = re.compile(ROUTING['new'], re.I)
FOLLOW_UP = re.compile(ROUTING['follow_up'], re.I)
SEARCH_GUIDANCE = ROUTING['search_guidance']
GUIDANCE = ROUTING['guidance']


def hook(event):
    cwd = event.get('cwd')
    if not isinstance(cwd, str) or not Path(cwd).is_absolute():
        return {}
    if event.get('hook_event_name') == 'UserPromptSubmit':
        prompt = event.get('prompt', '')
        if isinstance(prompt, str) and (RESEARCH.search(prompt) or FOLLOW_UP.search(prompt)) and (root := project_for(cwd)):
            guidance = GUIDANCE
            if FOLLOW_UP.search(prompt):
                fallback = cli_command('knowledge', 'search', str(root), 'FOCUSED KEYWORDS')
                guidance = (f'{SEARCH_GUIDANCE} Project: {root}. If MCP is unavailable, run '
                            f'`{fallback}` before opening source files. Replace FOCUSED KEYWORDS '
                            'and keep the search terms in one quoted argument.')
            return {'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit', 'additionalContext': guidance}}
    elif event.get('hook_event_name') == 'Stop':
        result = sync(cwd)
        if result['status'] in ('partial', 'pending'):
            return {'systemMessage': 'TokenSaver research has pending or failed files. See its index or run knowledge sync.'}
    return {}


def checked(root, relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or path.drive:
        raise ValueError('Path must stay inside the project.')
    current = root
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise ValueError('Symbolic links are not accepted by the research store.')
    return current


def read_json(path):
    if path.stat().st_size > LIMIT:
        raise ValueError('Research metadata exceeds the file limit.')
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, data):
    atomic_write(path, json.dumps(data, ensure_ascii=False, sort_keys=True))


def automation_receipt(root):
    # Keep opt-ins outside the checkout so copying project files cannot grant them.
    from .storage import config_path
    folder = config_path().parent / 'research-opt-ins'
    if any(path.is_symlink() for path in (folder, folder.parent)):
        raise ValueError('Research opt-in folder must not be a symbolic link.')
    return checked(folder, f'{digest(str(root).encode())}.json')


def project_settings(root):
    config = checked(root, STORE / 'config.json')
    return read_json(config) if config.is_file() else {}


def approved_automation(root, settings):
    project_id = settings.get('project_id')
    if not project_id:
        return {}
    receipt = automation_receipt(root)
    if receipt.is_file():
        policy = read_json(receipt)
        if policy.pop('project_id', None) == project_id:
            return policy
    return {}


def activate(project, *, codex_project_hooks=False, claude_project_hooks=False,
             snapshot_domains=None, auto_audio=False, auto_images=False, clear_automation=False):
    root = Path(project).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Choose a project directory.')
    store = checked(root, STORE)
    with output_lock(checked(store, '.state')):
        return _activate(root, store, codex_project_hooks, claude_project_hooks,
                         snapshot_domains, auto_audio, auto_images, clear_automation)


def _activate(root, store, codex_project_hooks, claude_project_hooks,
              snapshot_domains, auto_audio, auto_images, clear_automation):
    inbox = checked(root, INBOX)
    current_settings = project_settings(root)
    previous_id = current_settings.get('project_id') if project_for(root) == root else None
    project_id = previous_id or uuid.uuid4().hex
    policy = {} if clear_automation else approved_automation(root, {'project_id': previous_id})
    if snapshot_domains is not None:
        from .research_web import normalize_domain
        policy['domains'] = sorted({normalize_domain(host) for host in snapshot_domains})
    if auto_audio:
        from .providers import whisper_paths
        from .storage import load_profiles
        audio = load_profiles().get('audio', {})
        if audio.get('provider') != 'whisper.cpp':
            raise ValueError('Configure a local whisper.cpp audio profile before enabling automatic transcription.')
        model, _ = whisper_paths(audio['model'])
        policy['audio'] = {'provider': 'whisper.cpp', 'model': str(model)}
    if auto_images:
        from .model_setup import load_model_selection
        image = load_model_selection()
        if not image:
            raise ValueError('Select an image provider and model before enabling automatic image analysis.')
        policy['image'] = image
    # Exclude the inbox too: it can contain raw research and drafts.
    ignore = checked(root, '.gitignore')
    current = ignore.read_text(encoding='utf-8') if ignore.exists() else ''
    patterns = [f'/{INBOX.as_posix()}/', f'/{STORE.as_posix()}/']
    missing = [pattern for pattern in patterns if pattern not in current.splitlines()]
    if missing:
        atomic_write(ignore, current.rstrip('\n') + ('\n' if current else '') + '\n'.join(missing) + '\n')
    inbox.mkdir(parents=True, exist_ok=True)
    store.mkdir(parents=True, exist_ok=True)
    receipt = automation_receipt(root)
    if policy:
        write_json(receipt, {**policy, 'project_id': project_id})
    else:
        receipt.unlink(missing_ok=True)
    write_json(checked(store, 'config.json'), {'version': 1, 'project': str(root), 'project_id': project_id})
    for host, requested in (('codex', codex_project_hooks), ('claude', claude_project_hooks)):
        if requested:
            configure_project_hooks(root, host, enabled=True)
    return {'status': 'enabled', 'inbox': INBOX.as_posix(), 'store': STORE.as_posix(), 'automation': policy}


def cli_command(*args):
    import shlex
    prefix = [sys.executable] if getattr(sys, 'frozen', False) else [sys.executable, '-m', 'tokensaver_docs']
    command = [*prefix, *args]
    return subprocess.list2cmdline(command) if os.name == 'nt' else shlex.join(command)


def configure_project_hooks(root, host, *, enabled):
    path = checked(root, '.codex/hooks.json' if host == 'codex' else '.claude/settings.local.json')
    if not enabled and not path.is_file():
        return
    settings = read_json(path) if path.is_file() else {}
    hooks = settings.setdefault('hooks', {})
    handler = {'type':'command', 'command':cli_command('knowledge', 'hook'), 'timeout':90, 'statusMessage':'TokenSaver research'}
    before = json.dumps(settings, sort_keys=True)
    for event in ('UserPromptSubmit', 'Stop'):
        groups = []
        for group in hooks.get(event, []):
            retained = [item for item in group['hooks'] if not (
                item.get('statusMessage') == 'TokenSaver research' and item.get('command', '').endswith(' knowledge hook'))]
            if retained:
                groups.append({**group, 'hooks': retained})
        if enabled:
            groups.append({'hooks':[handler]})
        if groups:
            hooks[event] = groups
        else:
            hooks.pop(event, None)
    if json.dumps(settings, sort_keys=True) != before:
        write_json(path, settings)


def project_for(directory, *, include_disabled=False):
    path = Path(directory).resolve()
    for root in (path, *path.parents):
        config = checked(root, STORE / 'config.json')
        if config.is_file():
            settings = read_json(config)
            if (settings.get('version') == 1 and settings.get('project') == str(root)
                    and (include_disabled or settings.get('enabled', True))):
                return root
            return None
        if (root / '.git').exists():
            break
    return None


def deactivate(project):
    root = project_for(project, include_disabled=True)
    if root is None:
        return {'status': 'disabled'}
    store = checked(root, STORE)
    with output_lock(checked(store, '.state')):
        if project_for(project, include_disabled=True) != root:
            return {'status': 'disabled'}
        write_json(checked(store, 'config.json'), {'version': 1, 'project': str(root), 'enabled': False})
        automation_receipt(root).unlink(missing_ok=True)
        for host in ('codex', 'claude'):
            configure_project_hooks(root, host, enabled=False)
    return {'status': 'disabled'}


def signature(path):
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > LIMIT:
        raise ValueError('Only regular files up to 100 MiB can be archived.')
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def snapshot(root, path, staged):
    relative = path.relative_to(root)
    before = signature(path)
    target = staged / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    with checked(root, relative).open('rb') as src, target.open('wb') as dst:
        remaining = before[2] + 1
        while remaining and (chunk := src.read(min(remaining, 1024 * 1024))):
            dst.write(chunk)
            remaining -= len(chunk)
        dst.flush()
        os.fsync(dst.fileno())
    if signature(checked(root, relative)) != before or target.stat().st_size != before[2]:
        raise ValueError('A research file changed while being saved. Retry on the next turn.')
    return target, before


def capture(root, store, source, previous, *, source_url=None):
    with tempfile.TemporaryDirectory(prefix='capture-', dir=checked(store, '.state')) as tmp:
        stage = Path(tmp)
        main, original_signature = snapshot(root, source, stage)
        files = {source.relative_to(root).as_posix(): (main, original_signature)}
        missing = 0
        if source.suffix.lower() in ('.html', '.htm'):
            from bs4 import BeautifulSoup
            from .html_document import decode_html, local_image_path
            soup = BeautifulSoup(decode_html(main.read_bytes()), 'html.parser')
            base = soup.find('base')
            total = original_signature[2]
            for node in soup.find_all('img', src=True):
                ref = str(node['src'])
                if ref.lower().startswith('data:'):
                    continue
                try:
                    asset = local_image_path(source, ref, base.get('href', '') if base else '')
                except ValueError:
                    missing += 1
                    continue
                rel = asset.relative_to(root).as_posix()
                if rel not in files:
                    total += signature(asset)[2]
                    if total > LIMIT:
                        raise ValueError('Research document plus linked images exceeds 100 MiB.')
                    files[rel] = snapshot(root, asset, stage)
        checks = {rel: file_hash(value[0]) for rel, value in files.items()}
        stamps = {rel: value[1] for rel, value in files.items()}
        if any(signature(checked(root, rel)) != stamp for rel, stamp in stamps.items()):
            raise ValueError('A research source or asset changed during capture.')
        if previous and previous['files'] == checks and previous['missing_assets'] == missing:
            return previous, stamps
        prior = previous['id'] if previous else None
        relative = source.relative_to(root).as_posix()
        version = digest(json.dumps([relative, checks, missing, prior], sort_keys=True).encode())
        manifest = {'id': version, 'source': relative, 'previous': prior, 'files': checks,
                    'missing_assets': missing, 'status': 'archived', 'captured_ns': time.time_ns()}
        if source_url:
            manifest['source_url'] = source_url
        for rel, sha in checks.items():
            blob = checked(store, Path('raw/objects') / sha / Path(rel).name)
            # Retain an extension for opening original bytes. Aliases use the first published name.
            folder = blob.parent
            folder.mkdir(parents=True, exist_ok=True)
            originals = list(folder.iterdir())
            if originals:
                blob = originals[0]
                if blob.is_symlink() or file_hash(blob) != sha:
                    raise ValueError('Archived original is corrupt.')
            else:
                os.replace(files[rel][0], blob)
        write_json(checked(store, Path('raw/versions') / f'{version}.json'), manifest)
        return manifest, stamps


def versions(store):
    manifests = checked(store, 'raw/versions')
    for path in sorted(manifests.glob('*.json')):
        if VERSION.fullmatch(path.stem) and not path.is_symlink():
            record = read_json(path)
            if record['id'] != path.stem:
                raise ValueError('Research version manifest does not match its filename.')
            yield record


def active(records):
    latest = {}
    for record in sorted(records, key=lambda item: (item['captured_ns'], item['id'])):
        latest[record['source']] = record
    return latest


def original(store, sha):
    if not VERSION.fullmatch(sha):
        raise ValueError('Invalid archived file hash.')
    files = list(checked(store, Path('raw/objects') / sha).iterdir())
    if len(files) != 1 or files[0].is_symlink() or file_hash(files[0]) != sha:
        raise ValueError('Archived original is missing or corrupt.')
    return files[0]


def analysis_profile(source, policy):
    if source.suffix.lower() in AUDIO:
        audio = policy.get('audio', {})
        return 'audio', audio if audio.get('provider') == 'whisper.cpp' else None
    if source.suffix.lower() in IMAGES:
        return 'image', policy.get('image')
    return None, None


def prepare_snapshot(store, record, policy=None):
    from . import __version__
    source = Path(record['source'])
    kind, profile = analysis_profile(source, policy or {})
    analysis_key = digest(json.dumps(profile, sort_keys=True).encode()) if profile else None
    mode = 'analyze' if profile and kind == 'image' else 'preserve'
    key = digest(json.dumps([__version__, 'local-preserve-v1', analysis_key], sort_keys=True).encode())[:16]
    output = checked(store, Path('converted') / record['id'] / key)
    if kind == 'audio' and not profile:
        return {**record, 'status': 'needs_transcription'}
    with tempfile.TemporaryDirectory(prefix='prepare-', dir=checked(store, '.state')) as tmp:
        staged = Path(tmp)
        for rel, sha in record['files'].items():
            path = checked(staged, rel)
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original(store, sha), path)
        if source.suffix.lower() in ('.md', '.txt'):
            output.mkdir(parents=True, exist_ok=True)
            markdown = publish_new(output / source.with_suffix('.md').name, (staged / source).read_text(encoding='utf-8'))
            status = '완료'
        else:
            result, = convert(staged / source, output, cache_dir=cache_root(), image_mode=mode,
                              profiles={kind: profile} if profile else None)
            if result['status'] not in ('완료', '확인필요', '부분완료') or not result.get('output'):
                return {**record, 'status': 'conversion_failed'}
            markdown, status = Path(result['output']), result['status']
            text = markdown.read_text(encoding='utf-8')
            original_header = f'원본: {staged / source}\n'
            if original_header in text:
                atomic_write(markdown, text.replace(original_header, f'원본: {source.as_posix()}\n', 1))
    return {**record, 'status': 'ready' if status == '완료' else 'partial',
            **({'analysis_key': analysis_key} if profile else {}),
            'markdown': markdown.relative_to(store).as_posix(), 'markdown_sha256': file_hash(markdown)}


def checked_markdown(store, record):
    for sha in set(record['files'].values()):
        original(store, sha)
    path = checked(store, record['markdown'])
    if file_hash(path) != record['markdown_sha256']:
        raise ValueError('Archived Markdown has been edited.')
    return path


def conversion_manifest(store, version_id, conversion_id):
    if not VERSION.fullmatch(version_id) or not VERSION.fullmatch(conversion_id):
        raise ValueError('Pass a research version ID and conversion ID.')
    return checked(store, Path('raw/conversions') / version_id / f'{conversion_id}.json')


def adopt(project, source, output):
    """Attach a verified, previously completed conversion without running a model."""
    root = project_for(project)
    if root is None:
        raise ValueError('Enable project research first.')
    store = checked(root, STORE)
    relative = Path(source)
    original_source = checked(root, relative)
    output_root = checked(root, output)
    checked(output_root, '.tokensaver-docs/state.json')
    with output_lock(checked(store, '.state')):
        record = active(versions(store)).get(relative.as_posix())
        if record is None or file_hash(original_source) != record['files'][relative.as_posix()]:
            raise ValueError('Sync the current source version before attaching its conversion.')
        if len(record['files']) != 1 or record['missing_assets']:
            raise ValueError('Attach currently supports self-contained sources only.')
        original(store, record['files'][relative.as_posix()])
        entry = next((item for item in load_state(output_root)['records'].values()
                      if item.get('source') == str(original_source)
                      and item.get('source_hash') == record['files'][relative.as_posix()]
                      and item.get('status') in ('완료', '확인필요')), None)
        if not entry:
            raise ValueError('A completed conversion for these exact source bytes is required.')
        path = checked(output_root, entry['current_output'])
        body = path.read_bytes()
        sha = digest(body)
        if sha != entry.get('output_hash'):
            raise ValueError('The conversion has been edited.')
        target = checked(store, Path('converted') / record['id'] / sha / path.name)
        for match in re.finditer(r'!\[[^\n]*?\]\(([^)\n]+)\)', body.decode()):
            asset = Path(match[1])
            if asset.is_absolute() or asset.drive or '..' in asset.parts:
                raise ValueError('The conversion uses image links outside its Markdown directory.')
            data = checked(path.parent, asset).read_bytes()
            copy = checked(target.parent, asset)
            if not copy.exists():
                copy.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(checked(path.parent, asset), copy)
            if copy.read_bytes() != data:
                raise ValueError('An archived image differs from the conversion asset.')
        if not target.exists():
            publish_new(target, body.decode())
        if file_hash(target) != sha:
            raise ValueError('An archived conversion is corrupt.')
        if record.get('markdown_sha256'):
            old = conversion_manifest(store, record['id'], record['markdown_sha256'])
            if not old.exists():
                write_json(old, record)
        record.update(markdown=target.relative_to(store).as_posix(), markdown_sha256=sha, attached=True,
                      status='ready' if entry['status'] == '완료' else 'partial')
        saved = conversion_manifest(store, record['id'], sha)
        if not saved.exists():
            write_json(saved, record)
        write_json(checked(store, Path('raw/versions') / f'{record["id"]}.json'), record)
    return {'status': record['status'], 'version_id': record['id'], 'conversion_id': sha}


def serialize_research(result):
    paths = list(result['sources'])
    excerpts = [{'source_index': paths.index(item['file']), **{k: v for k, v in item.items() if k != 'file'}}
                for item in result['excerpts']]
    continuation = result['next']
    if continuation and continuation['file'] in paths:
        continuation = {'source_index': paths.index(continuation['file']), 'start_line': continuation['start_line']}
    return json.dumps({**result, 'excerpts': excerpts, 'next': continuation}, ensure_ascii=False, separators=(',', ':'))


def search(project, query, *, version=None, conversion=None, max_tokens=500):
    from .context import context_records
    root = Path(project).resolve(strict=True)
    store = checked(root, STORE)
    if conversion is not None and version is None:
        raise ValueError('A conversion ID requires its research version ID.')
    if version is not None:
        if not VERSION.fullmatch(version):
            raise ValueError('Pass a research version ID.')
        manifest = checked(store, Path('raw/versions') / f'{version}.json')
        selected = [read_json(manifest)] if manifest.is_file() else []
        if conversion is not None:
            saved = conversion_manifest(store, version, conversion)
            if saved.is_file():
                selected = [read_json(saved)]
            elif not selected or selected[0].get('markdown_sha256') != conversion:
                selected = []
    else:
        selected = list(active(versions(store)).values())

    def records():
        for record in selected:
            path = None
            status = record['status']
            if record.get('markdown'):
                try:
                    path = checked_markdown(store, record)
                    status = '완료' if status == 'ready' and not record['missing_assets'] else '부분완료'
                except (OSError, ValueError):
                    status = 'integrity_error'
            yield {'file': record['source'], 'status': status, 'output': path, 'label': Path(record['source']).stem,
                   'display_path': path.relative_to(root).as_posix() if path else record['source']}
    return serialize_research(context_records(records(), query, max_tokens=max_tokens,
                                               serializer=serialize_research, clip_long_lines=True))


def safe_text(value):
    return re.sub(r'([\\`*_{}\[\]<>#|!])', r'\\\1', ' '.join(str(value).split()))


def publish_report(store, data, draft_sha, latest):
    import posixpath
    topic = data['topic']
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', topic):
        raise ValueError('Use a short ASCII topic slug.')
    directory = checked(store, Path('reports') / topic)
    summary = checked(directory, 'summary.md')
    signature_file = checked(directory, '.published.json')
    last = read_json(signature_file) if signature_file.is_file() else {}
    same_draft = last.get('draft_sha') == draft_sha
    pins = last.get('citations', {}) if same_draft else {}
    items = data.get('evidence', [])[:20]
    web_ids = [latest[web_source(url)]['id'] for url in data.get('references', [])[:20]
               if web_source(url) in latest]
    if same_draft and len(pins) == len(items) and last.get('web_ids', []) == web_ids and summary.exists():
        return
    evidence = []
    cited = {}
    citations = {}
    for position, item in enumerate(items):
        key = str(position)
        if key in pins:
            citations[key] = pins[key]
            cited[item['source']] = pins[key]['version']
            evidence.append(pins[key]['line'])
            continue
        record = latest.get(item['source'])
        version = last.get('versions', {}).get(item['source']) if same_draft else None
        if version and (not record or record['id'] != version):
            manifest = checked(store, Path('raw/versions') / f'{version}.json')
            record = read_json(manifest) if manifest.is_file() else None
        citation = None
        if record and record.get('markdown') and item.get('quote'):
            lines = checked_markdown(store, record).read_text(encoding='utf-8').splitlines()
            excerpt = item['quote'].splitlines()
            for i, line in enumerate(lines):
                if line == excerpt[0] and lines[i:i + len(excerpt)] == excerpt:
                    url = quote(posixpath.relpath(record['markdown'], directory.relative_to(store).as_posix()))
                    raw = original(store, record['files'][record['source']])
                    raw_url = quote(posixpath.relpath(raw.relative_to(store).as_posix(), directory.relative_to(store).as_posix()))
                    citation = (f'[{i + 1}–{i + len(excerpt)}행]({url}#L{i + 1}) · [원본]({raw_url})'
                                f' · 버전 `{record["id"]}` · 변환본 `{record["markdown_sha256"]}`')
                    cited[item['source']] = record['id']
                    break
        line = f'- {safe_text(item["source"])} · {safe_text(item.get("quote", ""))} · {citation or "근거 확인 필요"}'
        if citation:
            citations[key] = {'version': record['id'], 'conversion': record['markdown_sha256'], 'line': line}
        evidence.append(line)
    for url in data.get('references', [])[:20]:
        parts = urlsplit(url)
        if parts.scheme in ('http', 'https') and parts.hostname and not (parts.username or parts.password or parts.query):
            saved = latest.get(web_source(url))
            if saved and saved.get('source_url') == url:
                raw = original(store, saved['files'][saved['source']])
                raw_url = quote(posixpath.relpath(raw.relative_to(store).as_posix(),
                                                directory.relative_to(store).as_posix()))
                evidence.append(f'- {safe_text(url)} · [원문 스냅샷]({raw_url})')
            else:
                evidence.append(f'- {safe_text(url)} · REFERENCE_ONLY')
    report = (f'# {safe_text(data.get("title", topic))}\n\n'
              f'## 결론 초안\n\n{safe_text(data["conclusion"])}\n\n'
              '## 근거\n\n' + ('\n'.join(evidence) or '- 근거 확인 필요') + '\n\n'
              f'## 개발 반영\n\n{safe_text(data.get("impact", "")) or "미정"}\n\n'
              f'## 미확인 사항\n\n{safe_text(data.get("unknowns", "")) or "검토 필요"}\n')
    sha = digest(report.encode())
    current = file_hash(summary) if summary.is_file() else None
    if current == sha:
        # Preserve ownership metadata if a human happened to write identical text.
        return
    if current and current != last.get('sha') and digest(summary.read_text(encoding='utf-8').encode()) != last.get('sha'):
        pending = checked(directory, f'summary.pending-{sha[:16]}.md')
        if not pending.exists():
            publish_new(pending, report)
        return
    if current:
        history = checked(directory, Path('history') / f'{current}.md')
        if not history.exists():
            publish_new(history, summary.read_text(encoding='utf-8'))
        if file_hash(summary) != current:
            return
    atomic_write(summary, report)
    write_json(signature_file, {'sha': sha, 'draft_sha': draft_sha, 'versions': cited, 'citations': citations, 'web_ids': web_ids})


def snapshot_references(store, data, latest, policy, started):
    import http.client
    from .research_web import fetch_html, public_target

    domains = policy.get('domains', [])
    if not domains:
        return 0, False
    saved = 0
    pending = False
    for url in data.get('references', [])[:20]:
        relative = web_source(url)
        try:
            host_path = public_target(url, domains)
            if host_path is None:
                continue
            record = latest.get(relative)
            if record and record['status'] not in ('archived', 'conversion_failed'):
                continue
            if not record:
                memo = checked(store, Path('.state/web') / (Path(relative).stem + '.json'))
                if memo.is_file() and time.time() - read_json(memo)['attempted'] < 3600:
                    continue
            if time.monotonic() - started >= 20:
                pending = True
                continue
            if not record:
                write_json(memo, {'attempted': time.time()})
                with tempfile.TemporaryDirectory(prefix='web-', dir=checked(store, '.state')) as tmp:
                    scratch = Path(tmp)
                    snapshot_path = scratch / relative
                    snapshot_path.parent.mkdir(parents=True)
                    snapshot_path.write_bytes(fetch_html(*host_path))
                    record, _ = capture(scratch, store, snapshot_path, None, source_url=url)
            record = prepare_snapshot(store, record)
            write_json(checked(store, Path('raw/versions') / f'{record["id"]}.json'), record)
            latest[relative] = record
            saved += 1
        except (OSError, ValueError, http.client.HTTPException):
            # A blocked or unavailable page remains a reference in the report.
            continue
    return saved, pending


def web_source(url):
    return (INBOX / '.web' / f'{digest(url.encode())}.html').as_posix()


def sync(project):
    root = project_for(project)
    if root is None:
        return {'status': 'disabled'}
    store, inbox = checked(root, STORE), checked(root, INBOX)
    errors = 0
    updated = 0
    with output_lock(checked(store, '.state')):
        if project_for(project) != root:
            return {'status': 'disabled'}
        policy = approved_automation(root, project_settings(root))
        state_path = checked(store, '.state/scanned.json')
        scanned = read_json(state_path) if state_path.is_file() else {}
        latest = active(versions(store))
        for record in latest.values():
            if record.get('analysis_state') == 'running':
                record['analysis_state'] = 'interrupted'
                write_json(checked(store, Path('raw/versions') / f'{record["id"]}.json'), record)
        drafts = []
        changed = False
        # shortcut: Scan only the approved inbox, switch to a paged catalog if this scope grows.
        started = time.monotonic()
        attempted_media = False
        pending_media = False
        pending_web = False
        for directory, dirs, names in os.walk(inbox, followlinks=False):
            dirs[:] = sorted(name for name in dirs if not name.startswith('.') and not (Path(directory)/name).is_symlink())
            for name in sorted(names):
                candidate = Path(directory) / name
                if name.startswith('.') or candidate.is_symlink():
                    continue
                if name.endswith(REPORT_SUFFIX):
                    drafts.append(candidate)
                    continue
                if candidate.suffix.lower() not in SUPPORTED | {'.md', '.txt'}:
                    continue
                rel = candidate.relative_to(root).as_posix()
                try:
                    known = scanned.get(rel, {})
                    previous = latest.get(rel, {})
                    kind, profile = analysis_profile(candidate, policy)
                    requested = digest(json.dumps(profile, sort_keys=True).encode()) if profile else None
                    retry_audio = (kind == 'audio' and requested == previous.get('analysis_attempt')
                                   and previous.get('analysis_state') == 'interrupted'
                                   and not previous.get('analysis_retried'))
                    needs_analysis = bool(requested and (requested != previous.get('analysis_attempt') or retry_audio)
                                          and not previous.get('attached'))
                    analyze = needs_analysis and not attempted_media
                    pending_media |= needs_analysis and attempted_media
                    if known and not analyze and previous.get('status') not in ('archived', 'conversion_failed') and not previous.get('missing_assets'):
                        try:
                            if all(signature(checked(root, path)) == mark for path, mark in known.items()):
                                continue
                        except (OSError, ValueError):
                            # A removed or replaced asset should produce a new snapshot.
                            pass
                    if time.monotonic() - started >= 20:
                        return {'status': 'pending', 'updated': updated, 'errors': errors}
                    record, stamps = capture(root, store, candidate, latest.get(rel))
                    if record['id'] != previous.get('id') and requested:
                        retry_audio = False
                        analyze = not attempted_media
                        pending_media |= attempted_media
                    if record['status'] in ('archived', 'conversion_failed') or analyze:
                        if analyze:
                            attempted_media = True
                            record = {**record, 'analysis_attempt': requested, 'analysis_state': 'running',
                                      'analysis_retried': bool(retry_audio)}
                            write_json(checked(store, Path('raw/versions') / f'{record["id"]}.json'), record)
                            latest[rel] = record
                        converted = prepare_snapshot(store, record, policy if analyze else None)
                        if analyze:
                            if converted['status'] == 'conversion_failed':
                                # Keep local evidence and require a deliberate retry after failed analysis.
                                converted = (record if record.get('markdown') else prepare_snapshot(store, record))
                                converted = {**converted, 'analysis_state': 'review'}
                            else:
                                converted['analysis_state'] = 'complete'
                        if record.get('markdown_sha256') and converted.get('markdown_sha256') != record['markdown_sha256']:
                            old = conversion_manifest(store, record['id'], record['markdown_sha256'])
                            if not old.exists():
                                write_json(old, record)
                        record = converted
                        write_json(checked(store, Path('raw/versions') / f'{record["id"]}.json'), record)
                        if record['status'] == 'conversion_failed':
                            errors += 1
                        else:
                            updated += 1
                            changed = True
                    if not known or latest.get(rel, {}).get('id') != record['id']:
                        changed = True
                    latest[rel], scanned[rel] = record, stamps
                    write_json(state_path, scanned)
                except (OSError, ValueError, KeyError):
                    scanned.pop(rel, None)
                    errors += 1
        for draft in drafts:
            try:
                body = draft.read_bytes() if draft.stat().st_size <= 64 * 1024 else b''
                data = json.loads(body)
                if draft.name != data['topic'] + REPORT_SUFFIX or data['topic'] == 'inbox':
                    raise ValueError('The draft filename must match its topic slug; inbox is reserved.')
                saved, pending = snapshot_references(store, data, latest, policy, started)
                updated += saved
                changed |= bool(saved)
                pending_web |= pending
                publish_report(store, data, digest(body), latest)
            except (OSError, ValueError, KeyError, TypeError):
                errors += 1
        # A save still produces a useful handoff if the host did not write a research draft.
        if changed or (latest and not checked(store, 'reports/inbox/summary.md').exists()):
            evidence = []
            recent = sorted(latest.values(), key=lambda item: item['captured_ns'], reverse=True)[:5]
            for record in recent:
                try:
                    if not record.get('markdown'):
                        continue
                    lines = checked_markdown(store, record).read_text(encoding='utf-8').splitlines()
                    excerpt = next((line for line in lines if 5 <= len(line) <= 280 and
                                    not line.startswith(('#', '>', '![', '원본:', '상태:', '선택 설정:'))), '')
                    if excerpt:
                        evidence.append({'source': record['source'], 'quote': excerpt})
                except (OSError, ValueError):
                    errors += 1
            data = {'topic':'inbox', 'title':'최근에 보관한 조사 자료',
                    'conclusion':f'{len(latest)}개 자료를 보관했습니다. 아래는 원본에서 추출한 미검토 발췌입니다.',
                    'evidence':evidence}
            seal = digest(json.dumps([data, [record['id'] for record in recent]], sort_keys=True).encode())
            publish_report(store, data, seal, latest)
        index = ['# 보관 자료', '']
        for name, record in sorted(latest.items()):
            state = record.get('analysis_state')
            if not state and record.get('analysis_attempt') != record.get('analysis_key'):
                state = 'review'
            suffix = f' · analysis_{state}' if state in ('interrupted', 'review', 'running') and not record.get('attached') else ''
            index.append(f'- {safe_text(name)} · {record["status"]}{suffix} · `{record["id"]}`')
            if suffix and analysis_profile(Path(name), policy)[1] and not pending_media:
                errors += 1
        for summary in sorted(checked(store, 'reports').glob('*/summary.md')):
            if not (summary.is_symlink() or summary.parent.is_symlink()):
                published = checked(summary.parent, '.published.json')
                receipt = read_json(published) if published.is_file() else {}
                cited = receipt.get('versions', {})
                stale = any(latest.get(source, {}).get('id') != version for source, version in cited.items())
                if not stale:
                    current_conversions = {latest[source]['id']: latest[source].get('markdown_sha256') for source in cited}
                    stale = any(current_conversions.get(pin['version']) != pin['conversion']
                                for pin in receipt.get('citations', {}).values())
                suffix = ' · 새 원본 버전 확인 필요' if stale else ''
                index.append(f'- [요약 {safe_text(summary.parent.name)}]({quote(summary.relative_to(store).as_posix())}){suffix}')
        index_path = checked(store, 'index.md')
        body = '\n'.join(index) + '\n'
        if not index_path.is_file() or index_path.read_text(encoding='utf-8') != body:
            atomic_write(index_path, body)
    return {'status': 'partial' if errors else 'pending' if pending_media or pending_web else 'ready',
            'updated': updated, 'errors': errors}
