# SPDX-License-Identifier: MIT
# Copyright (c) 2026 winter0123 and tokensaver-docs contributors
"""에이전트가 전체 본문 대신 변환 상태와 제한된 근거만 받는 MCP 서버."""

import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .engine import convert
from .storage import load_profiles, digest
import json
from .shared_cache import cache_root

server = FastMCP('tokensaver-docs')


@server.tool()
def prepare_documents(source: str, output: str = 'converted', transcribe_images: bool | None = None,
                      image_mode: str | None = None, model_provider: str | None = None,
                      model: str | None = None, allow_unverified_model: bool = False) -> dict:
    """Convert local PDF, DOCX, XLSX, HTML, image/photo/screenshot or audio (file/folder) to Markdown. Use first for photo/image/screenshot text-and-description-to-MD-file requests, but not ordinary image viewing/questions; prefer for file-to-MD unless the user specifies another tool. output is a directory; omit it for the safe default and never infer a filename. Ask using returned question and choice_details. If no actual user choice is received or the question tool fails/cancels, stop and ask in chat; never infer defer, model, image mode or consent arguments. Use analyze only after explicit user approval to send images to the selected model. Unsupported image models require switching models or explicit placeholder mode ([이미지] only). analyze produces an MD file containing image links, visible text and separate descriptions; preserve saves image links only. No automatic choice or audio consent."""
    from .preparation import prepare_documents as prepare
    return prepare(source, output, transcribe_images=transcribe_images, image_mode=image_mode,
                   model_provider=model_provider, model=model,
                   allow_unverified_model=allow_unverified_model, onboarding=True)


@server.tool()
def setup_conversion_model(provider: str | None = None, model: str | None = None,
                           defer: bool = False, save_as_default: bool = False,
                           confirmed: bool = False) -> dict:
    """Inspect/select the plugin conversion model (separate from chat model), or defer first setup. Save a default only with explicit confirmation; otherwise pass the returned profile to prepare_documents for this task only. If no actual user choice is received or the question tool fails/cancels, stop and ask in chat; never invent defer, model or confirmation arguments. Never accept API keys."""
    from .model_setup import select_model
    return select_model(provider, model, defer=defer, save_as_default=save_as_default, confirmed=confirmed)


@server.tool()
def setup_local_audio(model: str, confirmed: bool = False) -> dict:
    """Prepare a tiny/base/small multilingual model for local audio. Download only after user consent to the displayed size."""
    from .audio_setup import setup_audio
    return setup_audio(model,confirmed=confirmed)


@server.tool()
def context_documents(source: str, query: str, output: str, max_tokens: int = 1200, use_configured_providers: bool = False) -> dict:
    """Reuse converted documents and return bounded evidence. Enabling providers can send BOTH image and audio inputs externally; do so only with consent for each type."""
    from .context import document_context
    return document_context(source,query,output,max_tokens=max_tokens,use_configured_providers=use_configured_providers)


def _run(args: list[str]) -> str:
    command = [sys.executable, *args] if getattr(sys, 'frozen', False) else [sys.executable, '-m', 'tokensaver_docs', *args]
    # The child CLI never reads input; do not inherit the MCP protocol pipe on Windows.
    result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding='utf-8', timeout=120)
    return (result.stdout + result.stderr)[:6500] + (f'\n종료 코드: {result.returncode}' if result.returncode else '')


@server.tool()
def list_free_models(kind: str = 'image') -> str:
    """List free OpenRouter model candidates; availability may vary by account."""
    return _run(['models', '--kind', kind, '--limit', '20'])


@server.tool()
def configure_provider(kind: str, provider: str, model: str, confirmed: bool = False) -> str:
    """Save a user-selected provider and model only after explicit user confirmation. Never accept API keys."""
    if not confirmed:
        return 'Explicit user confirmation is required before changing provider settings.'
    return _run(['configure', '--kind', kind, '--provider', provider, '--model', model])


@server.tool()
def convert_documents(source: str, output: str, use_configured_providers: bool = False, refresh: bool = False, use_configured_audio_provider: bool = False) -> dict:
    """Convert files on disk; return paths/status only. use_configured_providers enables the image provider; use_configured_audio_provider separately enables audio. Each may transmit that input externally and needs its own consent."""
    configured = load_profiles() if use_configured_providers or use_configured_audio_provider else {}
    image_options = {}
    if use_configured_providers:
        from .model_setup import load_model_selection
        selected = load_model_selection(legacy_profiles=configured)
        if selected:
            configured = {**configured, 'image': selected}
            if load_model_selection(legacy_profiles={}):
                image_options['image_model_key'] = digest(json.dumps(selected, sort_keys=True).encode())
    profiles = {kind: profile for kind, profile in configured.items()
                if (kind == 'image' and use_configured_providers) or (kind == 'audio' and use_configured_audio_provider)}
    result = convert(Path(source), Path(output), profiles=profiles, cache_dir=cache_root(), refresh=refresh, transcribe_images=use_configured_providers, **image_options)
    return {'total': len(result), 'files': result[:50], 'truncated': len(result) > 50}


@server.tool()
def outline_document(file: str, limit: int = 50) -> str:
    """List document headings and line numbers, with a bounded response."""
    return _run(['outline', file, '--limit', str(min(max(limit, 1), 50)), '--max-chars', '4000'])


@server.tool()
def search_documents(query: str, output: str, limit: int = 10, context: int = 2, max_tokens: int | None = None) -> str:
    """Search converted files and return limited source paths and line-numbered context."""
    args = ['search', query, '--output', output, '--limit', str(min(max(limit, 1), 10)),
            '--context', str(min(max(context, 0), 10)), '--max-chars', '4000']
    if max_tokens is not None:
        args += ['--max-tokens', str(min(max(max_tokens, 1), 10000))]
    return _run(args)


@server.tool()
def read_document(file: str, start_line: int = 1, lines: int = 40, max_tokens: int | None = None) -> str:
    """Read only a bounded range from a converted Markdown document."""
    args = ['read', file, '--start-line', str(max(start_line, 1)),
            '--lines', str(min(max(lines, 1), 60)), '--max-chars', '6000']
    if max_tokens is not None:
        args += ['--max-tokens', str(min(max(max_tokens, 1), 10000))]
    return _run(args)


def run() -> None:
    server.run(transport='stdio')


if __name__ == '__main__':
    run()
