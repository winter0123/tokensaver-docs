// SPDX-License-Identifier: MIT
// Copyright (c) 2026 winter0123 and tokensaver-docs contributors
import { tool } from '@opencode-ai/plugin';
import { ensureTokenSaverExecutable, findTokenSaverExecutable } from './runtime.js';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { basename, join, dirname, extname, resolve, relative, isAbsolute } from 'node:path';
import { readFile, stat, lstat, realpath, readdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { homedir } from 'node:os';
import researchRouting from './research-routing.json' with { type: 'json' };

// Resolve document names inside the OpenCode session project, not in the
// server's process.cwd(). Never scan the user's home or other projects.
const SOURCE_SEARCH_MAX_ENTRIES = 2000;
const SOURCE_SEARCH_MAX_DEPTH = 5;
const SOURCE_SEARCH_EXCLUDED = new Set(['.git', '.venv', '.worker-context',
  '__pycache__', '.tokensaver-docs', 'node_modules']);

function sourceLookupError(status, project, source, extra = {}) {
  const messages = {
    project_required: 'OpenCode did not provide a project directory. Please supply the full path to the document.',
    source_not_found: 'The document was not found in the current project. Provide its full path or explicitly select another folder; do not search outside this project automatically.',
    source_ambiguous: 'Several files have this name in the current project. Choose the intended full path.',
    source_search_limited: 'The project search limit was reached. Give the document path or a narrower subfolder.',
    source_permission_required: 'OpenCode cannot access part of the requested project. Grant OpenCode access to the folder in macOS privacy settings (or choose a permitted folder), then retry.',
    source_outside_project: 'A relative path must stay inside the current project. Provide the explicit absolute path if you want to access a file outside it.',
    source_invalid: 'The document path is not a normal file or directory. Provide the original file rather than a symbolic link.'
  };
  return { status, source, project, question: messages[status],
    next: 'Ask the user to resolve this path issue. Do not use agent glob/read/shell or search outside the project without permission.', ...extra };
}

// Direct paths win. For a basename, search only bounded non-symlink project
// directories, preserving Unicode names (macOS often uses decomposed forms).
export async function resolveProjectSource(source, project) {
  if (typeof source !== 'string' || !source.trim())
    return sourceLookupError('source_invalid', project, source);
  const projectRoot = typeof project === 'string' && project.trim() ? resolve(project) : null;
  if (!projectRoot && !isAbsolute(source))
    return sourceLookupError('project_required', project, source);
  const candidate = isAbsolute(source) ? resolve(source) : resolve(projectRoot, source);
  if (!isAbsolute(source) && (relative(projectRoot, candidate) === '..' ||
      relative(projectRoot, candidate).startsWith('..' + (process.platform === 'win32' ? '\\' : '/'))))
    return sourceLookupError('source_outside_project', projectRoot, source);
  const inspect = async path => {
    try {
      const info = await lstat(path);
      return info.isSymbolicLink() ? 'symlink'
        : info.isFile() || info.isDirectory() ? 'ready' : 'invalid';
    } catch (error) {
      if (['EACCES', 'EPERM'].includes(error.code)) return 'permission';
      if (['ENOENT', 'ENOTDIR'].includes(error.code)) return 'missing';
      throw error;
    }
  };
  const direct = await inspect(candidate);
  if (direct === 'ready') return {status:'ready', source:candidate};
  if (direct === 'permission')
    return sourceLookupError('source_permission_required', projectRoot, source);
  if (direct !== 'missing')
    return sourceLookupError('source_invalid', projectRoot, source);
  if (isAbsolute(source) || basename(source) !== source || !projectRoot)
    return sourceLookupError('source_not_found', projectRoot, source);

  const matches = [];
  let count = 0;
  let permissionDenied = false;
  const stack = [{path:projectRoot,depth:0}];
  const normalized = source.normalize('NFC');
  while (stack.length > 0) {
    const next = stack.pop();
    let entries;
    try { entries = await readdir(next.path, {withFileTypes:true}); }
    catch (error) {
      if (['EACCES','EPERM'].includes(error.code)) { permissionDenied = true; continue; }
      if (['ENOENT','ENOTDIR'].includes(error.code)) continue;
      throw error;
    }
    // Deterministic ordering for predictable ambiguity reports.
    entries.sort((a,b) => a.name.localeCompare(b.name,'en'));
    for (const entry of entries) {
      if (++count > SOURCE_SEARCH_MAX_ENTRIES)
        return sourceLookupError('source_search_limited', projectRoot, source);
      if (entry.isSymbolicLink()) continue;
      const entryPath = join(next.path, entry.name);
      if (entry.name.normalize('NFC') === normalized && (entry.isFile() || entry.isDirectory()))
        matches.push(entryPath);
      if (entry.isDirectory() && next.depth < SOURCE_SEARCH_MAX_DEPTH &&
          !entry.name.startsWith('.') && !SOURCE_SEARCH_EXCLUDED.has(entry.name))
        stack.push({path:entryPath,depth:next.depth+1});
    }
  }
  if (permissionDenied)
    return sourceLookupError('source_permission_required', projectRoot, source,
      {candidates:matches.slice(0,10)});
  if (matches.length > 1)
    return sourceLookupError('source_ambiguous', projectRoot, source,
      {candidates:matches.slice(0,10),total:matches.length});
  if (matches.length === 1) return {status:'ready',source:matches[0]};
  return sourceLookupError('source_not_found', projectRoot, source);
}

let executable = join(dirname(fileURLToPath(import.meta.url)), 'bin', process.platform === 'win32' ? 'tokensaver-docs.exe' : 'tokensaver-docs');
// shortcut: request text remains in memory until a newer real prompt; add verified V2 session-final cleanup if long-lived servers accumulate entries.
const requestBySession = new Map();

const conversionInstruction = 'For this explicit conversion request only, call tokensaver_docs_prepare immediately as your first tool, before glob, listing, reading originals, or writing conversion commands. The preparation engine reads saved global image preferences automatically, so if configured, NEVER ask for image mode, platform, model or transmission consent again. If the first prepare call returns choice_required, inspect tokensaver_docs_preferences once and ask for a choice only if setup_required; save the actual selected image mode and, for analysis, platform/model/network policy using tokensaver_docs_preferences, then retry original prepare call. For unanswered choices, never infer a model, defer, image mode, or provider consent. Never invent selections, persist external-transfer consent without explicit user permission, or switch platforms after errors. Pass the named source directly to tokensaver_docs_prepare: its bounded resolver checks the current project and subfolders without agent file-search tools. If it reports a missing, ambiguous or inaccessible path, ask only the reported question; never search outside the project without the user explicitly providing an authorized path. Omit output unless the user names an output directory; output is a directory, never infer a filename. Respect an explicitly chosen alternative converter. For conversion-only, report returned Markdown paths and status without rereading.';
const audioConversionInstruction = 'For this explicit local audio conversion request, use tokensaver_docs_setup_audio to ask the user to select tiny, base, or small, then show the returned exact download size and wait for the user’s explicit download confirmation. After setup, call tokensaver_docs_convert_audio to ask for separate explicit local transcription consent. Convert only the single audio file the user named, with the configured local whisper.cpp profile; never use an external provider or process folders. If any question is unanswered, declined, or canceled, stop without downloading or transcribing.';
const selectedModelApprovalInstruction = 'An image model is already configured or selected for this session. If the current real user message explicitly approves image analysis, immediately call tokensaver_docs_prepare for the original source with image_mode analyze and this model. Otherwise use OpenCode question UI for the explicit approval: the actual UI answer is remembered by the plugin. NEVER ask the user to copy it into chat. The question must identify the exact provider and model, clearly say that document images will be transmitted externally, and offer consent and decline options. Once the user selects consent, immediately retry tokensaver_docs_prepare for the same source and model. Neither model selection nor agent-written prose nor tool arguments grants consent.';
const completedConversionInstruction = 'Preparation is complete. Return the reported Markdown paths and status to the user. Do not call any more tools or reread the result.';
const documentQuestionInstruction = 'Call tokensaver_docs_context first for this local document question. Pass the named path and literal search keywords. For a non-English question on a document of unknown language, include English equivalents in the same query. This tool handles unconverted documents without model setup. Cite the returned Markdown lines and use tokensaver_docs_read for any needed continuation.';
const retryDocumentSearchInstruction = 'The search found no matching terms. Retry tokensaver_docs_context once with shorter literal keywords from the likely document language. Include English equivalents if the previous query had only non-English words.';
const documentSearchExhausted = 'The search limit for this document question has been reached. Report any evidence already returned or state that no matching evidence was found.';

function documentQuestionGuidance(request) {
  if (request.documentSearchStatus !== 'no_match') return documentQuestionInstruction;
  return request.documentSearches >= 2 ? documentSearchExhausted : retryDocumentSearchInstruction;
}

const researchTurn = new RegExp(researchRouting.new, 'i');
const researchFollowUp = new RegExp(researchRouting.follow_up, 'i');

async function researchProject(directory) {
  for (let root = directory; root; root = dirname(root)) {
    const config = join(root, 'docs','tokensaver-docs','config.json');
    try {
      if (await realpath(config) !== config) return null;
      const settings = JSON.parse(await readFile(config, 'utf8'));
      return settings.version === 1 && settings.project === root && settings.enabled !== false ? root : null;
    } catch (error) {
      if (error.code !== 'ENOENT') return null;
    }
    if (await lstat(join(root, '.git')).catch(() => null) || dirname(root) === root) return null;
  }
  return null;
}

function isMarkdownConversionRequest(prompt) {
  const text = prompt?.text ?? '';
  const files = prompt?.files ?? [];
  const source = files.length > 0 || /\b(?:image|photo|picture|screenshot|document|file|folder|pdf|docx?|xlsx?|html|htm|pptx?)\b|\.(?:png|jpe?g|gif|webp|bmp|tiff?|svg|pdf|docx?|xlsx?|html|htm|pptx?)\b|이미지|사진|스크린샷|캡처|문서|파일|폴더|ファイル|画像|文件|图片/i.test(text);
  const target = /\b(?:to|into|as)\s+(?:an?\s+)?(?:markdown|md)(?:\s+(?:file|document))?|\b(?:markdown|md)\s+file\b|(?:마크다운|markdown)(?:으로|\s*파일)|md\s*파일(?:로)?|md로|markdown\s*(?:に|へ)|(?:转成|整理成)\s*markdown/i.test(text);
  const alternative = /\b(?:pandoc|libreoffice|obsidian)\b|\b(?:another|different|external|my)\s+(?:converter|tool|command|script)\b|(?:다른|별도|직접 지정한)\s*(?:변환기|도구|명령|스크립트)|\buse\s+(?!tokensaver\b)(?:the\s+)?[a-z][\w.@/-]*\s+to\s+(?:convert|turn|make|write|save)/i.test(text);
  const convert = /\b(?:convert|turn|transform|export)\b|변환|바꿔|정리해|(?:変換して|まとめて|markdown\s*にして|转成|整理成)|(?:md|markdown|마크다운)\s*(?:파일\s*)?(?:로|으로)\s*만들/i.test(text);
  return source && target && convert && !alternative;
}

function isAudioMarkdownRequest(prompt) {
  const text = prompt?.text ?? '';
  const files = prompt?.files ?? [];
  const source = /\.(?:wav|mp3|m4a|ogg|flac|aac|mp4)\b/i.test(text) || files.some(file => /\.(?:wav|mp3|m4a|ogg|flac|aac|mp4)$/i.test(typeof file === 'string' ? file : file?.name ?? file?.path ?? ''));
  return source && /\b(?:convert|transcribe|turn|export)\b|변환|음성을\s*글자로|음성.*글자/i.test(text) && /\b(?:to|into|as)\s+(?:a\s+)?(?:markdown|md)\b|(?:마크다운|markdown)(?:으로|로)?|md로/i.test(text);
}

function documentQuestionSource(text) {
  const localDocument = /(?:^|[\s"'`(])((?![a-z][\w+.-]*:\/\/)[^\s"'`<>]+?\.(?:pdf|docx|xlsx|html?|md))(?=$|[\s"'`),.!?:;]|에서|의|을|를|에)/gi;
  const question = /\b(?:find|what|when|where|which|summari[sz]e|cite|evidence|line numbers?)\b|찾아|알려|보여|뭐|요약|근거|줄\s*번호/i;
  const otherTask = /\b(?:edit|rewrite|patch|rename|delete)\b|(?:수정|편집|고쳐|삭제|바꿔)(?:해|줘|주세요)|\b(?:use|with)\s+(?:the\s+)?(?:cat|read|grep|rg|sed|python3?|pandoc|libreoffice|obsidian)\b|(?:cat|read|grep|rg|sed|python3?|pandoc|libreoffice|obsidian)(?:으로|로)/i;
  if (!question.test(text) || otherTask.test(text)) return null;
  const sources = [...new Set(Array.from(text.matchAll(localDocument), match => match[1]))];
  return sources.length === 1 ? sources[0] : null;
}

function audioChoice(text) {
  const value = text.trim().toLowerCase().replace(/[.!?]$/, '');
  const choices = {
    audio_tiny: ['tiny','select tiny','use tiny','tiny 모델 선택','tiny 모델을 선택합니다'],
    audio_base: ['base','select base','use base','base 모델 선택','base 모델을 선택합니다'],
    audio_small: ['small','select small','use small','small 모델 선택','small 모델을 선택합니다'],
    audio_download_tiny: ['download tiny (77,691,713 bytes)','tiny 모델 다운로드 확인 (77,691,713바이트)'],
    audio_download_base: ['download base (147,951,465 bytes)','base 모델 다운로드 확인 (147,951,465바이트)'],
    audio_download_small: ['download small (487,601,967 bytes)','small 모델 다운로드 확인 (487,601,967바이트)'],
    audio_transcribe: ['transcribe this audio locally','transcribe locally','이 음성을 로컬에서 글자로 바꿉니다','음성 내용을 글자로 저장합니다'],
    audio_decline: ['no','cancel','do not transcribe','아니요','취소','음성 내용을 글자로 바꾸지 않습니다'],
  };
  for (const [choice, values] of Object.entries(choices)) if (values.includes(value)) return choice;
  return null;
}

function audioChoiceForStage(choice, stage) {
  return stage === 'model' ? /^audio_(?:tiny|base|small)$/.test(choice ?? '') :
    stage === 'download' ? /^audio_download_(?:tiny|base|small)$/.test(choice ?? '') :
    stage === 'consent' ? ['audio_transcribe','audio_decline'].includes(choice) : false;
}

function audioDataRoot() {
  if (process.env.XDG_CONFIG_HOME) return join(process.env.XDG_CONFIG_HOME,'tokensaver-docs','opencode');
  const base = process.platform === 'win32' ? (process.env.LOCALAPPDATA || join(homedir(),'AppData','Local')) :
    process.platform === 'darwin' ? join(homedir(),'Library','Application Support') :
    (process.env.XDG_DATA_HOME || join(homedir(),'.local','share'));
  return join(base,'tokensaver-docs','opencode');
}

function audioEnvironment() {
  const root = audioDataRoot();
  return { ...process.env, XDG_CONFIG_HOME: join(root,'config'), TOKENSAVER_DOCS_CACHE_DIR: process.env.TOKENSAVER_DOCS_CACHE_DIR || join(root,'cache') };
}

function audioConfigPath() { return join(audioDataRoot(),'config','tokensaver-docs','config.json'); }

function exactChoice(text) {
  const value = text.trim().toLowerCase().replace(/\s*\(recommended\)$/i, '').replace(/[.!]$/, '');
  const labels = {
    defer: ['later','defer','not now','나중에','나중에 선택하기'],
    select_model: ['모델 선택하기','모델 바꾸기'],
    preserve: ['preserve','images only','image links only','이미지 링크만','보존(preserve)','이미지만 넣기','이미지 넣기','이미지 링크만 넣기','이미지만 넣기로 변환','이미지 링크만 넣고, 이미지 속 글자나 설명은 넣지 마','only include the image links in the markdown, with no extracted image text and no descriptions'], 
    placeholder: ['placeholder','[이미지]','플레이스홀더(placeholder)','현재 모델로 계속하기'],
    analyze: ['이미지·글자·설명 넣기','이미지 분석에 동의합니다'],
    decline: ['no','no, do not analyze the image','no, do not analyze it','cancel','아니요','취소'],
    confirm: ['yes','confirm','네','예','확인','승인','분석 동의','외부 전송 및 분석 동의','분석 진행','이번에만 허용','이번 한 번만 허용','이번 작업만 허용','한 번 허용','이번에만 동의','항상 허용','계속 허용','허용'], 
  };
  for (const [choice, values] of Object.entries(labels))
    if (values.includes(value)) return choice;
  if (/^(?:yes,?\s+(?:please\s+)?analy[sz]e it|i (?:explicitly )?approve image analysis(?: with (?:openrouter|codex|claude) \S+)?|(?:네|예),?\s*분석해\s*(?:주세요|줘요))$/i.test(value)) return 'analyze';
  return null;
}

function choiceReply(text, previous) {
  if (previous?.audio) return audioChoiceForStage(audioChoice(text), previous.audioStage);
  const choice = exactChoice(text);
  return Boolean(choice && (choice !== 'confirm' || previous?.defaultConfirmation)) ||
    /^(?:i (?:choose|select) )?(?:openrouter|codex|claude) \S+(?: and save this model as default)?[.!]?$/i.test(text.trim());
}

function matchesModelChoice(text, provider, model) {
  const choice = text.trim().replace(/[.!]$/, '').replace(/^Convert \S+ to Markdown(?:\. | with )/i, '').toLowerCase();
  const pair = `${provider} ${model}`.toLowerCase();
  return [pair, `i choose ${pair}`, `i select ${pair}`, `${pair} and save this model as default`].includes(choice);
}

// OpenCode question UI replies are tool results, not new chat messages. Only
// trust answers from an actually completed question tool call; model-supplied
// prepare arguments and quoted conversation text are never consent evidence.
// The form is the user's answer. No chat retyping, additional model-name
// entry or repeated per-turn transmission confirmation is required.
function chosenRuntime(label) {
  const choice = label.toLowerCase().replace(/\s+/g,' ').trim();
  if (/^(?:codex|gpt(?:\s*\/\s*codex|\s*\(codex\))?|codex\s*\/\s*gpt)/.test(choice))
    return {runtime:'codex',provider:'codex'};
  if (/^(?:claude code|claude\s*\(claude code\)|클로드 코드)/.test(choice))
    return {runtime:'claude',provider:'claude'};
  if (/^(?:opencode|오픈코드)/.test(choice))
    return {runtime:'opencode'};
  if (/^(?:api|openrouter|직접 api)/.test(choice))
    return {runtime:'api',provider:'openrouter'};
  if (/^(?:local llm|local|로컬 llm|로컬 모델|로컬 분석)/.test(choice))
    return {runtime:'local'};
  return null;
}

function chosenLocalProvider(label) {
  const value = label.trim().toLowerCase();
  if (/^ollama(?:\s|$)/.test(value)) return 'ollama';
  if (/^lm studio(?:\s|$)/.test(value)) return 'lmstudio';
  if (/^(?:openai-compatible|openai 호환|사설망 서버)/.test(value)) return 'openai_compatible';
  return null;
}

function actualCatalogSelection(label, request) {
  const options = Array.isArray(request.catalogModels) ? request.catalogModels : [];
  const normalized = label.trim().replace(/\s*\(recommended\)$/i,'');
  const matches = options.filter(item => {
    const candidates = [item.id, item.provider + '/' + item.id];
    return candidates.some(id => normalized === id ||
      normalized.startsWith(id+' ') || normalized.startsWith(id+' —') ||
      normalized.startsWith(id+' ('));
  });
  return matches.length === 1 ? matches[0] : null;
}

export function recordQuestionAnswers(event, request) {
  if (event.tool !== 'question' || event.status !== 'completed' || !request?.conversion) return;
  const questions = event.input?.questions;
  const answers = event.result?.output?.answers ?? event.result?.metadata?.answers;
  if (!Array.isArray(questions) || !Array.isArray(answers)) return;
  for (let i = 0; i < questions.length && i < answers.length; i++) {
    const question = questions[i];
    const answer = answers[i];
    if (!question || !Array.isArray(answer) || answer.length !== 1 || typeof answer[0] !== 'string') continue;
    const selected = answer[0].trim();
    // Reject agent-invented options; only recognize an actual selected UI label.
    if (!Array.isArray(question.options) || !question.options.some(opt => opt?.label === selected)) continue;
    const prompt = String(question.question ?? '') + ' ' + String(question.header ?? '');
    const choice = exactChoice(selected);
    if (/(?:이미지|사진|image|photo)/i.test(prompt) &&
        /(?:어떻게|처리 방식|포함|mode|how.*(?:handle|include)|which.*(?:mode|format))/i.test(prompt) &&
        ['analyze','preserve','placeholder'].includes(choice)) {
      request.uiMode = choice;
      request.uiModel = null;
      request.uiConsent = null;
      request.uiPersistentConsent = null;
      request.uiRuntime = null;
      request.catalogModels = null;
      continue;
    }
    // Service first, then its real model catalog. Never force OpenRouter.
    if (/(?:플랫폼|서비스|실행 환경|provider|runtime|where.*(?:analy[sz]e|run))/i.test(prompt)) {
      const runtime = chosenRuntime(selected);
      if (runtime) {
        request.uiRuntime = runtime;
        request.uiModel = null;
        request.uiConsent = null;
        request.catalogModels = null;
        continue;
      }
    }
    if (request.uiRuntime?.runtime === 'local' &&
        /(?:제공자|서버|local|로컬|provider)/i.test(prompt)) {
      const provider = chosenLocalProvider(selected);
      if (provider) {
        request.uiRuntime = {runtime:'local',provider};
        request.catalogModels = null;
        continue;
      }
    }
    if (/(?:모델|model)/i.test(prompt) && request.uiMode === 'analyze') {
      const hit = actualCatalogSelection(selected,request);
      if (hit) {
        const runtime = request.uiRuntime?.runtime ??
          (['openrouter'].includes(hit.provider) ? 'api'
            : ['ollama','lmstudio','openai_compatible'].includes(hit.provider) ? 'local'
            : ['codex','claude'].includes(hit.provider) ? hit.provider : 'opencode');
        const hostProvider = runtime === 'opencode' ? hit.provider :
          runtime === 'local' ? request.uiRuntime?.provider || hit.provider :
          runtime === 'api' ? 'openrouter' : runtime;
        request.uiRuntime = {runtime,provider:hostProvider};
        request.uiModel = {provider:runtime === 'local' ? 'local' :
          runtime === 'opencode' ? 'opencode' : hostProvider,
          model:runtime === 'opencode' ? hostProvider+'/'+hit.id : hit.id,
          ...(runtime === 'local' ? {network_policy:request.catalogNetworkPolicy || 'local_only',
            endpoint:request.catalogEndpoint} : {})};
        const external = runtime !== 'local';
        // The model-selection question itself can provide informed consent:
        // disclose the service/image transfer and future default in that
        // SAME question, rather than showing a second approval form.
        const disclosure = /(?:외부|전송|업로드|제공자|send|upload|external)/i.test(prompt) &&
          /(?:이미지|사진|image|photo)/i.test(prompt);
        if (external && disclosure) {
          request.uiConsent = {...request.uiModel};
          if (/(?:향후|이후|앞으로|매번|항상|기본값|future|default|subsequent|remember)/i.test(prompt))
            request.uiPersistentConsent = {...request.uiModel};
        }
        if (!external) request.uiConsent = {...request.uiModel};
        continue;
      }
      // Older OpenRouter UI (prior to catalog paging) remains compatible.
      if (/(?:openrouter|외부 전송|external transfer)/i.test(prompt)) {
        const match = selected.match(/^([\w.-]+\/[\w.:-]+)(?:\s|$)/);
        if (match && (/(?:openrouter)/i.test(prompt) ||
                      /:free$/.test(match[1]) || match[1] === 'openrouter/free')) {
          request.uiRuntime = {runtime:'api',provider:'openrouter'};
          request.uiModel = {provider:'openrouter',model:match[1]};
          request.uiConsent = null;
          request.uiPersistentConsent = null;
          continue;
        }
      }
    }
    // Compatibility: "이번에만 허용" in the existing permission question
    // is a FULL approval for this conversion, not another question.
    const chosen = request.uiModel;
    if (request.uiMode === 'analyze' && chosen &&
        /(?:외부|전송|upload|send|external|share|허용|동의)/i.test(prompt) &&
        (prompt.toLowerCase().includes(chosen.provider) ||
         prompt.toLowerCase().includes(chosen.model.toLowerCase()) ||
         /(?:이미지|사진|image|photo)/i.test(prompt)) &&
        choice === 'confirm') {
      request.uiConsent = {...chosen};
      if (/^(?:항상 허용|계속 허용)$/.test(selected) ||
          /(?:앞으로|향후|매번|계속|항상|영구|future|always|persist|remember|default)/i.test(prompt) &&
           !/(?:이번에만|이번 작업|one.time|only this)/i.test(selected))
        request.uiPersistentConsent = {...chosen};
      continue;
    }
  }
}

// OpenCode's own catalog, including models configured by user and local
// OpenCode providers. This is the host's live model inventory (not the
// conversion engine's model catalog). Do not assume all entries can accept
// image files or can be invoked by TokenSaver's Python subprocess.
export function pagedOpenCodeModels(response, {query='',limit=20,offset=0} = {}) {
  const models = Array.isArray(response?.data) ? response.data : [];
  const safeQuery = typeof query === 'string' ? query.slice(0,100).toLowerCase() : '';
  const size = Number.isInteger(limit) ? Math.min(40,Math.max(1,limit)) : 20;
  const start = Number.isInteger(offset) ? Math.max(0,offset) : 0;
  const entries = models.filter(m =>
    m && m.enabled !== false && (!m.type || m.type === 'chat') &&
    typeof m.providerID === 'string' && typeof m.id === 'string' &&
    Array.isArray(m.capabilities?.input) && m.capabilities.input.includes('image'))
    .map(m => ({
      provider: m.providerID,
      id: m.id,
      name: typeof m.name === 'string' ? m.name : m.id,
      vision: 'supported',
      runtime: 'opencode',
      // Actual model output cost/provider privacy depends on the host settings.
      // The model list alone is NOT a grant to send images.
      network_policy: 'unknown',
      conversion_available: true,
      requires_installed_cli: true,
      experimental: true,
    }))
    .filter(m => !safeQuery || (m.provider + '/' + m.id + ' ' + m.name).toLowerCase().includes(safeQuery))
    .sort((a,b)=>(a.provider+'/'+a.id).localeCompare(b.provider+'/'+b.id));
  return {status:'ready', provider:'opencode', total:entries.length,
    offset:start, has_more:start+size<entries.length, models:entries.slice(start,start+size)};
}

function choiceError(choice) {
  return JSON.stringify({status:'choice_required',question:choice,
    next:'Ask using OpenCode question UI, then continue in the same turn after its actual completed answer. If the question UI fails or is cancelled, stop. Do not invent a user choice.'});
}

function parseResult(result) {
  try { return JSON.parse(result); } catch { return null; }
}

async function configuredImageProfile() {
  const pref = parseResult(await run(['preferences']));
  const saved = pref?.preferences;
  if (pref?.status === 'configured' && saved?.image_mode === 'analyze') {
    return {provider: saved.runtime === 'local' ? 'local' : saved.runtime === 'opencode' ? 'opencode' : saved.provider,
      model: saved.runtime === 'opencode' ? saved.provider + '/' + saved.model : saved.model,
      ...(saved.runtime === 'local' ? {endpoint:saved.endpoint,network_policy:saved.network_policy} : {}),
      persistentConsent: saved.runtime !== 'local' && saved.allow_external_images === true};
  }
  const state = parseResult(await run(['setup-model']));
  return state?.status === 'configured' ? state.model : null;
}

function explicitChoiceError(name, input, request) {
  const text = request?.text ?? '';
  const choice = exactChoice(text);
  if (name === 'tokensaver_docs_setup_model') {
    if (input.defer && choice !== 'defer')
      return choiceError('Ask whether the user wants to choose a model now or defer setup.');
    const confirmingDefault = input.save_as_default && input.confirmed && request?.defaultConfirmation;
    if (input.provider || input.model) {
      if (confirmingDefault && (input.provider !== confirmingDefault.provider || input.model !== confirmingDefault.model))
        return choiceError('Use the model awaiting default-save confirmation.');
      if (!confirmingDefault && (!input.provider || !input.model ||
          !matchesModelChoice(text,input.provider,input.model) &&
          !(request?.uiModel?.provider === input.provider && request?.uiModel?.model === input.model)))
        return choiceError('Ask the user to name the provider and model they selected.');
    }
    if (request?.defaultConfirmation && input.save_as_default &&
        /\b(?:no|cancel|decline|do not|don't)\b|^(?:아니요|아니|취소)/i.test(text))
      return JSON.stringify({status:'save_declined',next:'The user declined saving a default. Stop without changing settings.'});
    if (input.save_as_default && !confirmingDefault && !/\b(?:save|set)\b.{0,30}\bdefault\b|기본(?:값)?으로\s*저장/i.test(text))
      return choiceError('Ask whether the user wants this model saved as the default.');
    if (input.save_as_default && input.confirmed && (!request?.defaultConfirmation ||
        choice !== 'confirm'))
      return choiceError('Ask for a separate confirmation before saving the selected model as the default.');
  }
  if (name !== 'tokensaver_docs_prepare') return null;
  const mode = input.image_mode ?? (input.transcribe_images === true ? 'analyze' : input.transcribe_images === false ? 'preserve' : null);
  if (mode === 'analyze') {
    const denied = /\b(?:no|do not|don't|dont|never|refuse(?:d)? to|decline(?:d)? to|cancel)\b.{0,100}\b(?:approve|authorize|consent|allow|permit|analy[sz]e|image|photo)\b|\b(?:approve|authorize|consent|allow|permit)\b.{0,100}\b(?:not|never|without|unless)\b|(?:동의|승인|허용|분석)하지\s*않|(?:이미지|사진).{0,50}(?:보내지\s*않|분석하지\s*않)|^(?:아니요|아니|취소)/i.test(text.trim());
    if (denied)
      return JSON.stringify({status:'consent_declined',next:'The user declined image analysis. Stop this conversion; do not retry or send the image.'});
    const consent = request?.uiConsent;
    const selected = request?.profile ?? request?.uiModel;
    const approvedByQuestion = request?.uiMode === 'analyze' && selected &&
      consent?.provider === selected.provider && consent?.model === selected.model &&
      (!input.model_provider || input.model_provider === consent.provider) &&
      (!input.model || input.model === consent.model);
    const local = selected?.provider === 'local' &&
      ['local_only','internal_only'].includes(selected.network_policy);
    const approved = choice === 'analyze' || approvedByQuestion ||
      local || selected?.persistentConsent === true;
    const hasModelChoice = Boolean(input.model && input.model_provider &&
      text.toLowerCase().includes(input.model.toLowerCase()) && text.toLowerCase().includes(input.model_provider.toLowerCase()));
    const mismatch = selected && ((input.model && input.model !== selected.model) ||
      (input.model_provider && input.model_provider !== selected.provider));
    if (!approved || mismatch || (!selected && !hasModelChoice && !approvedByQuestion))
      return choiceError(selected && !mismatch
        ? 'The image model is already selected. Ask only for explicit image-analysis approval; use this same model after the user approves.'
        : 'Ask the user to choose an image model and explicitly approve image analysis for this request.');
  }
  // preserve and placeholder are entirely local and send no images to any AI
  // provider. A real tool call with these explicit modes can proceed without
  // additional approval gates. Consent is required only for external analysis.
  return null;
}

async function run(args, env = process.env) {
  try { executable = await ensureTokenSaverExecutable(dirname(fileURLToPath(import.meta.url))); }
  catch (error) { return 'Unable to start bundled tokensaver-docs: ' + error.message; }
  return new Promise((resolve) => {
    const child = spawn(executable, args, { shell: false, windowsHide: true, env, detached: process.platform !== 'win32' });
    const isContext = args[0] === 'context' || (args[0] === 'knowledge' && args[1] === 'search');
    // Python's 6000 character cap can occupy twice as many UTF-16 code units.
    const limit = isContext ? 12002 : 6500;
    let output = '';
    let diagnostics = '';
    let truncated = false;
    let timedOut = false;
    const analyzing = args.includes('--transcribe-images') || args[args.indexOf('--image-mode') + 1] === 'analyze' || args.includes('--use-configured-audio-provider');
    const timeout = analyzing ? 7200000 : 300000;
    const timer = setTimeout(() => {
      timedOut = true;
      if (process.platform === 'win32') {
        const killer = spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], {shell:false,windowsHide:true,stdio:'ignore'});
        killer.on('error', () => child.kill());
      } else {
        try { process.kill(-child.pid, 'SIGKILL'); } catch (error) { if (error.code !== 'ESRCH') child.kill('SIGKILL'); }
      }
    }, timeout);
    const append = text => {
      if (output.length + text.length > limit) truncated = true;
      output += text.slice(0, Math.max(0, limit - output.length));
    };
    child.stdout.setEncoding('utf8');
    child.stderr.setEncoding('utf8');
    child.stdout.on('data', append);
    child.stderr.on('data', text => {
      if (isContext) diagnostics += text.slice(0, Math.max(0, 6500 - diagnostics.length));
      else append(text);
    });
    child.on('error', error => { clearTimeout(timer); resolve(`Unable to start bundled tokensaver-docs: ${error.message}`); });
    child.on('close', code => {
      clearTimeout(timer);
      if (isContext && code === 0 && !truncated && !timedOut) return resolve(output.trimEnd());
      if (isContext && diagnostics) append(diagnostics);
      if (['prepare','setup-model','setup-audio'].includes(args[0]) && !truncated && !timedOut) {
        try {
          if (typeof JSON.parse(output).status === 'string') return resolve(output);
        } catch { /* retain process errors below */ }
      }
      resolve(output + (truncated ? '\n[Output truncated]' : '') + (timedOut ? '\n[Timed out; completed results remain cached. Retry the same request to resume.]' : code ? `\n[Exit code: ${code}]` : ''));
    });
  });
}

async function setupAudio(request, input) {
  if (!input.model) {
    request.pending = true;
    return choiceError('Ask the user to choose one local multilingual Whisper model: tiny, base, or small (tiny/base/small 모델 중 하나를 선택해 주세요).');
  }
  const modelChoice = audioChoice(request.text);
  if (request.audioStage === 'model') {
    if (input.confirmed || modelChoice !== `audio_${input.model}`)
      return choiceError('Ask the user to choose tiny, base, or small; do not download yet.');
    const result = await run(['setup-audio','--model',input.model],audioEnvironment());
    const preview = parseResult(result);
    if (preview?.status !== 'confirmation_required') return result;
    request.audioStage = 'download';
    request.audioModel = input.model;
    request.pending = true;
    return JSON.stringify({...preview,question:`Download ${input.model} (${preview.bytes.toLocaleString('en-US')} bytes) for local transcription? Reply exactly: “Download ${input.model} (${preview.bytes.toLocaleString('en-US')} bytes)” or “No”. / ${input.model} 모델(${preview.bytes.toLocaleString('en-US')}바이트)을 내려받을까요? “${input.model} 모델 다운로드 확인 (${preview.bytes.toLocaleString('en-US')}바이트)” 또는 “아니요”라고 답해 주세요.`});
  }
  if (request.audioStage !== 'download' || input.model !== request.audioModel || input.confirmed !== true ||
      modelChoice !== `audio_download_${request.audioModel}`)
    return choiceError('Ask for a separate confirmation of the displayed model download size before downloading.');
  request.audioStage = 'setup_failed';
  request.pending = false;
  const result = await run(['setup-audio','--model',request.audioModel,'--download'],audioEnvironment());
  const ready = parseResult(result);
  if (ready?.status !== 'ready' || ready.local_processing !== true || !ready.path) return result;
  request.audioModelPath = ready.path;
  request.audioStage = 'transcribe';
  request.pending = true;
  return result;
}

async function requestedAudioSource(prompt) {
  const pattern = /"([^"\n]+\.(?:wav|mp3|m4a|ogg|flac|aac|mp4))"|'([^'\n]+\.(?:wav|mp3|m4a|ogg|flac|aac|mp4))'|`([^`\n]+\.(?:wav|mp3|m4a|ogg|flac|aac|mp4))`|([^\s"'`]+?\.(?:wav|mp3|m4a|ogg|flac|aac|mp4))(?=$|[\s.,!?을를이가])/gi;
  const names = [...(prompt.text ?? '').matchAll(pattern)].map(match => match.slice(1).find(Boolean));
  for (const file of prompt.files ?? []) {
    const name = typeof file === 'string' ? file : file?.path ?? file?.name;
    if (typeof name === 'string' && /\.(?:wav|mp3|m4a|ogg|flac|aac|mp4)$/i.test(name)) names.push(name);
  }
  const paths = [...new Set(names.map(name => resolve(name)))];
  if (paths.length !== 1) return null;
  try {
    const path = paths[0];
    const canonical = await realpath(path);
    const root = await realpath(process.cwd());
    const outside = relative(root, canonical);
    if (names.some(name => !isAbsolute(name)) && (outside === '..' || outside.startsWith(`..${process.platform === 'win32' ? '\\' : '/'}`) || isAbsolute(outside))) return null;
    return {path, canonical};
  } catch { return null; }
}

async function convertAudio(request, input) {
  if (!request.audio || !request.messageID || !request.audioModelPath || !['transcribe','consent'].includes(request.audioStage))
    return choiceError('A current user request and confirmed local Whisper setup are required.');
  const source = resolve(input.source);
  const extension = extname(source).toLowerCase();
  if (!['.wav','.mp3','.m4a','.ogg','.flac','.aac','.mp4'].includes(extension))
    return JSON.stringify({status:'invalid_audio_source',question:'Provide one supported audio file (.wav, .mp3, .m4a, .ogg, .flac, .aac, or audio .mp4). Folders and mixed inputs are not accepted.'});
  if (!request.audioRequestedSource)
    return JSON.stringify({status:'invalid_audio_source',question:'Ask the user for the exact audio file path; do not substitute another file with the same name.'});
  try {
    const info = await lstat(source);
    if (!info.isFile() || info.isSymbolicLink() || await realpath(source) !== request.audioRequestedSource.canonical) return JSON.stringify({status:'invalid_audio_source',question:'Only the originally requested regular, non-symlink audio file is accepted.'});
  } catch { return JSON.stringify({status:'invalid_audio_source',question:'The named local audio file is unavailable.'}); }
  if (request.audioStage === 'transcribe') {
    if (input.confirmed) return choiceError('Ask separately for explicit local transcription consent before converting.');
    request.audioSource = source;
    request.audioStage = 'consent';
    request.pending = true;
    return choiceError(`Ask: “Transcribe this audio locally” to use only the configured whisper.cpp profile for ${source.split(/[\\/]/).at(-1)}. This does not send audio externally. / ${source.split(/[\\/]/).at(-1)}의 음성 내용을 로컬에서 글자로 저장할까요? “음성 내용을 글자로 저장합니다” 또는 “음성 내용을 글자로 바꾸지 않습니다”라고 답해 주세요.`);
  }
  const choice = audioChoice(request.text);
  if (choice === 'audio_decline') {
    request.audioDeclined = true;
    request.pending = false;
    return JSON.stringify({status:'consent_declined',next:'The user declined local audio transcription. Stop without converting.'});
  }
  if (input.confirmed !== true || choice !== 'audio_transcribe' || request.audioSource !== source)
    return choiceError('Ask for the separate displayed local-transcription choice; do not infer consent from the conversion request.');
  try {
    const profiles = JSON.parse(await readFile(audioConfigPath(),'utf8'));
    if (Object.keys(profiles).some(key => key !== 'audio') || profiles.audio?.provider !== 'whisper.cpp' || profiles.audio.model !== request.audioModelPath)
      return JSON.stringify({status:'local_audio_profile_required',next:'Only the selected local whisper.cpp profile is allowed; stop without conversion.'});
  } catch { return JSON.stringify({status:'local_audio_profile_required',next:'The selected local whisper.cpp profile is unavailable; stop without conversion.'}); }
  request.audioStage = 'conversion_failed';
  request.pending = false;
  const result = await run(['convert',source,'--output',input.output ?? 'converted','--config',audioConfigPath(),'--use-configured-audio-provider'],audioEnvironment());
  if (!result.startsWith('Unable to start bundled tokensaver-docs:') && !result.includes('[Exit code:') && !result.includes('[Timed out;')) {
    request.audioStage = 'done';
    request.completed = true;
  }
  return result;
}

function insideResearchInbox(root, cwd, path) {
  return relative(root, resolve(cwd, path)).split(/[\\/]/).join('/').startsWith('docs/research/inbox/');
}

function researchGuidance(root, text) {
  if (researchFollowUp.test(text)) {
    return `${researchRouting.search_guidance.replace('search_research','tokensaver_docs_search_research')} Project: ${root}`;
  }
  return researchTurn.test(text) ? researchRouting.guidance.replace('search_research','tokensaver_docs_search_research') : '';
}

export const TokenSaverDocsPlugin = async (ctx = {}) => {
  const sessions = new Map();
  return {
    'chat.message': async ({sessionID}, {message, parts}) => {
      sessions.delete(sessionID);
      if (message.role !== 'user' || !ctx.directory) return;
      const cwd = await realpath(ctx.directory).catch(() => null);
      const root = cwd && await researchProject(cwd);
      if (root) {
        const text = parts.filter(part => part.type === 'text' && !part.synthetic).map(part => part.text).join(' ');
        sessions.set(sessionID, {cwd, root, guidance:researchGuidance(root, text)});
      }
    },
    'experimental.chat.system.transform': async ({sessionID}, {system}) => {
      const research = sessions.get(sessionID);
      if (research?.guidance && !research.guided) {
        system.push(research.guidance);
        research.guided = true;
      }
    },
    'tool.execute.after': async ({sessionID,tool,args}) => {
      const research = sessions.get(sessionID);
      if (!research) return;
      if (['bash','shell'].includes(tool)) research.synced = false;
      const path = args?.filePath ?? args?.path;
      if (['write','edit'].includes(tool) && typeof path === 'string' &&
          insideResearchInbox(research.root, research.cwd, path)) {
        research.synced = parseResult(await run(['knowledge','sync',research.root]))?.status === 'ready';
      }
    },
    event: async ({event}) => {
      const id = event.properties?.sessionID;
      const research = sessions.get(id);
      if (event.type !== 'session.idle' || !research) return;
      sessions.delete(id);
      if (!research.synced) await run(['knowledge','sync',research.root]);
    },
  'tool.execute.before': async (input, output) => {
    // Embedded-image HTML is expensive raw context. Prepare it locally before a native read.
    if (input.tool !== 'read') return;
    const pathKey = typeof output.args.filePath === 'string' ? 'filePath' : 'path';
    if (typeof output.args[pathKey] !== 'string') return;
    const source = resolve(output.args[pathKey]);
    if (!['.html','.htm'].includes(extname(source).toLowerCase())) return;
    if ((await stat(source)).size > 100 * 1024 * 1024) throw new Error('HTML exceeds 100 MiB. Use tokensaver_docs_prepare on a smaller file.');
    const bytes = await readFile(source);
    const encoding = bytes[0] === 0xff && bytes[1] === 0xfe ? 'utf-16le' :
      bytes[0] === 0xfe && bytes[1] === 0xff ? 'utf-16be' : 'utf-8';
    if (!/data:image\//i.test(new TextDecoder(encoding).decode(bytes))) return;
    const base = process.env.TOKENSAVER_DOCS_CACHE_DIR || join(
      process.platform === 'win32' ? (process.env.LOCALAPPDATA || join(homedir(), 'AppData', 'Local')) :
      process.platform === 'darwin' ? join(homedir(), 'Library', 'Application Support') :
      (process.env.XDG_DATA_HOME || join(homedir(), '.local', 'share')), 'tokensaver-docs', 'cache');
    const outputDir = join(base, 'opencode-prepared', createHash('sha256').update(source).digest('hex'));
    const prepared = JSON.parse(await run(['prepare',source,'--output',outputDir]));
    const file = prepared.files?.[0];
    if (!file?.output || !['완료','확인필요'].includes(file.status)) {
      throw new Error(`${prepared.question || 'HTML preparation needs attention.'} Use tokensaver_docs_prepare and ask the user before choosing a model or image mode. Do not read the raw Base64.`);
    }
    output.args[pathKey] = file.output;
    output.args.offset = 0;
    output.args.limit = 40;
  },
  tool: {
    tokensaver_docs_prepare: tool({
      description: 'Convert supported local PDF, DOCX, XLSX, HTML, image/photo/screenshot or audio files/folders to Markdown. For requests to turn image/photo/screenshot text and description into an MD file, use this tool first; ordinary image viewing or questions remain normal image tasks. Use first for file-to-Markdown requests unless the user specifies another converter; not for editing originals or existing Markdown. output is a directory, not an output filename; omit it to use the safe default and never infer a filename. For conversion-only requests, return output paths and status without extra search or reading. Ask the returned first-use/model/image question; never choose for the user. If a question fails or is cancelled, stop and ask the user; never infer a model or image mode. Use analyze only after the user explicitly approves image analysis with the chosen model. Analyze produces an MD file with an image link, visible text and a separate image description; preserve includes image links only; placeholder writes [이미지] at their positions with no image text, description or link. Unsupported models require switching models or explicitly continuing with placeholder. One-time model parameters do not change defaults. Image analysis may send images externally; audio is separate. Never read raw HTML/Base64. If preparation fails, report the failure instead of automatically writing a fallback conversion script.',
      args: { source: tool.schema.string(), output: tool.schema.string().optional(), transcribe_images: tool.schema.boolean().optional(), image_mode: tool.schema.enum(['analyze','preserve','placeholder']).optional(), model_provider: tool.schema.enum(['openrouter','codex','claude']).optional(), model: tool.schema.string().optional(), allow_unverified_model: tool.schema.boolean().optional() },
      execute: ({source,output,transcribe_images,image_mode,model_provider,model,allow_unverified_model}) => run(['prepare',source,'--output',output ?? 'converted',...(transcribe_images === undefined ? [] : [transcribe_images ? '--transcribe-images' : '--skip-image-transcription']),...(image_mode ? ['--image-mode',image_mode] : []),...(model_provider ? ['--model-provider',model_provider] : []),...(model ? ['--model',model] : []),...(allow_unverified_model ? ['--allow-unverified-model'] : [])]),
    }),
    tokensaver_docs_preferences: tool({
      description: 'Read shared persistent first-use image settings or save the option explicitly selected by the user. Reuse settings automatically for later conversions; prompt only on first use or when the user asks to change. Do not set allow_external_images without explicit consent to persistent external transmission.',
      args: {set_mode:tool.schema.enum(['analyze','preserve','placeholder']).optional(),
        runtime:tool.schema.enum(['opencode','codex','claude','api','local']).optional(),
        provider:tool.schema.string().optional(),
        model:tool.schema.string().optional(),endpoint:tool.schema.string().optional(),
        network_policy:tool.schema.enum(['local_only','internal_only','external_allowed']).optional(),
        allow_external_images:tool.schema.boolean().optional()},
      execute: ({set_mode,runtime,provider,model,endpoint,network_policy,allow_external_images}) => run([
        'preferences',...(set_mode?['--set-mode',set_mode]:[]),
        ...(runtime?['--runtime',runtime]:[]),...(provider?['--provider',provider]:[]),
        ...(model?['--model',model]:[]),...(endpoint?['--endpoint',endpoint]:[]),
        ...(network_policy?['--network-policy',network_policy]:[]),
        ...(allow_external_images?['--allow-external-images']:[])]),
    }),
    tokensaver_docs_list_image_models: tool({
      description: 'List image model IDs on a selected local/OpenRouter provider. A catalog entry does not guarantee vision capability; do not invent support.',
      args: {provider:tool.schema.enum(['openrouter','codex','claude','ollama','lmstudio','openai_compatible']),
        endpoint:tool.schema.string().optional(),
        query:tool.schema.string().optional(),
        limit:tool.schema.number().int().min(1).max(40).optional(),
        offset:tool.schema.number().int().min(0).optional(),
        network_policy:tool.schema.enum(['local_only','internal_only']).optional()},
      execute: ({provider,endpoint,network_policy,query,limit,offset}) => run([
        'list-image-models','--provider',provider,
        ...(endpoint?['--endpoint',endpoint]:[]),
        ...(network_policy?['--network-policy',network_policy]:[]),
        ...(query?['--query',query]:[]),
        ...(limit!==undefined?['--limit',String(limit)]:[]),
        ...(offset!==undefined?['--offset',String(offset)]:[])]),
    }),
    tokensaver_docs_setup_model: tool({
      description: 'Inspect first-use setup or a user-selected conversion model. Defer only when the user chooses later. If a question fails or is cancelled, stop and ask the user; never infer defer, model or confirmation arguments. A one-time selection does not save defaults; save_as_default requires explicit confirmation. Never request API keys in chat or assume the host chat model is the conversion model.',
      args: { provider: tool.schema.enum(['openrouter','codex','claude']).optional(), model: tool.schema.string().optional(), defer: tool.schema.boolean().optional(), save_as_default: tool.schema.boolean().optional(), confirmed: tool.schema.boolean().optional() },
      execute: ({provider,model,defer,save_as_default,confirmed}) => run(['setup-model',...(provider ? ['--provider',provider] : []),...(model ? ['--model',model] : []),...(defer ? ['--defer'] : []),...(save_as_default ? ['--save-as-default'] : []),...(confirmed ? ['--confirmed'] : [])]),
    }),
    tokensaver_docs_setup_audio: tool({
      description: 'Offer tiny, base, and small local Whisper models. Preview the selected model size first, then download only after a separate explicit user confirmation.',
      args: { model: tool.schema.enum(['tiny','base','small']).optional(), confirmed: tool.schema.boolean().optional() },
      execute: ({model,confirmed}) => model ? run(['setup-audio','--model',model,...(confirmed ? ['--download'] : [])],audioEnvironment()) : choiceError('Choose tiny, base, or small.'),
    }),
    tokensaver_docs_convert_audio: tool({
      description: 'Convert one user-named local audio file using only the configured local whisper.cpp profile, after separate explicit transcription consent. Folders and external profiles are blocked.',
      args: { source: tool.schema.string(), output: tool.schema.string().optional(), confirmed: tool.schema.boolean().optional() },
      execute: ({source,output}) => run(['convert',source,'--output',output ?? 'converted','--config',audioConfigPath(),'--use-configured-audio-provider'],audioEnvironment()),
    }),
    tokensaver_docs_context: tool({
      description: 'First tool for questions about local PDF, DOCX, XLSX, HTML or Markdown. Pass the original path and focused search terms to get relevant passages with Markdown line numbers in one call. Works on unconverted files without model setup. Use prepare for requests to create a Markdown file.',
      args: { source: tool.schema.string(), query: tool.schema.string(), output: tool.schema.string().optional(), max_tokens: tool.schema.number().int().min(1).max(10000).optional() },
      execute: ({source,query,output,max_tokens}) => run(['context',source,query,'--output',output ?? 'converted','--max-tokens',String(max_tokens ?? 1200)]),
    }),
    tokensaver_docs_search_research: tool({
      description: 'Search prior research already archived in this project. Pass the absolute project path and focused keywords. Each source_index points to a Markdown path in sources.',
      args: {project:tool.schema.string(),query:tool.schema.string(),max_tokens:tool.schema.number().int().min(1).max(10000).optional(),
        version_id:tool.schema.string().optional(), conversion_id:tool.schema.string().optional()},
      execute: ({project,query,max_tokens,version_id,conversion_id}) => run([
        'knowledge','search',project,query,'--max-tokens',String(max_tokens ?? 500),
        ...(version_id ? ['--version-id',version_id] : []),
        ...(conversion_id ? ['--conversion-id',conversion_id] : []),
      ]),
    }),
    tokensaver_docs_convert: tool({
      description: 'Convert local documents without using configured external providers. Returns status and output paths.',
      args: { source: tool.schema.string(), output: tool.schema.string(), refresh: tool.schema.boolean().optional() },
      execute: ({source, output, refresh}) => run(['convert', source, '--output', output, '--no-configured-providers',...(refresh ? ['--refresh'] : [])]),
    }),
    tokensaver_docs_free_models: tool({
      description: 'List free OpenRouter model candidates; account availability may vary.',
      args: { kind: tool.schema.enum(['image', 'audio']) },
      execute: ({kind}) => run(['models', '--kind', kind, '--limit', '20']),
    }),
    tokensaver_docs_configure_provider: tool({
      description: 'Save a provider and model chosen by the user. Never accept or request an API key in chat.',
      args: { kind: tool.schema.enum(['image', 'audio']), provider: tool.schema.enum(['openrouter', 'codex', 'claude', 'whisper.cpp']), model: tool.schema.string(), confirmed: tool.schema.boolean() },
      execute: ({kind, provider, model, confirmed}) => confirmed ? run(['configure', '--kind', kind, '--provider', provider, '--model', model]) : 'Explicit user confirmation is required.',
    }),
    tokensaver_docs_convert_with_provider: tool({
      description: 'Include image text and descriptions with the selected image provider, only after the user explicitly allows the images to be sent. Audio is not sent.',
      args: { source: tool.schema.string(), output: tool.schema.string(), confirmed: tool.schema.boolean() },
      execute: ({source, output, confirmed}) => confirmed ? run(['prepare', source, '--output', output, '--transcribe-images']) : 'Explicit user confirmation is required.',
    }),
    tokensaver_docs_outline: tool({
      description: 'List headings and line numbers in a converted document.',
      args: { file: tool.schema.string() },
      execute: ({file}) => run(['outline', file, '--limit', '50', '--max-chars', '4000']),
    }),
    tokensaver_docs_search: tool({
      description: 'Search for evidence in converted documents, with bounded surrounding context.',
      args: { query: tool.schema.string(), output: tool.schema.string() },
      execute: ({query, output}) => run(['search', query, '--output', output, '--context', '2', '--limit', '10', '--max-chars', '4000']),
    }),
    tokensaver_docs_read: tool({
      description: 'Read a bounded range of lines from converted Markdown.',
      args: { file: tool.schema.string(), start_line: tool.schema.number().int().min(1).optional() },
      execute: ({file, start_line}) => run(['read', file, '--start-line', String(start_line ?? 1), '--lines', '40', '--max-chars', '6000']),
    }),
  },
  };
};

// V2 uses a default plugin definition; V1 keeps the named function above.
export default {
  id: 'tokensaver-docs',
  async setup(ctx) {
    const legacy = await TokenSaverDocsPlugin();
    // Do not download the native runtime while OpenCode activates plugins.
    // Built-in V2 tools bootstrap it only when they are first executed.
    const installedExecutable = await findTokenSaverExecutable(dirname(fileURLToPath(import.meta.url)));
    if (installedExecutable) executable = installedExecutable;
    const researchSessions = new Map();
    const researchEvents = new AbortController();
    if (ctx.event?.subscribe) {
      void (async () => {
        try {
          for await (const event of ctx.event.subscribe({types:['session.idle','session.execution.succeeded'],signal:researchEvents.signal})) {
            if (!['session.idle','session.execution.succeeded'].includes(event.type)) continue;
            const id = event.data?.sessionID ?? event.properties?.sessionID ?? event.sessionID;
            const research = researchSessions.get(id);
            if (research) {
              researchSessions.delete(id);
              if (!research.synced) await run(['knowledge','sync',research.directory]);
            }
          }
        } catch (error) {
          if (!researchEvents.signal.aborted) console.error('TokenSaver research event subscription failed:', error.message);
        }
      })();
    }
    const pluginDirectory = dirname(fileURLToPath(import.meta.url));
    let skillDirectory = join(pluginDirectory,'skills','tokensaver-docs');
    try { await stat(skillDirectory); }
    catch { skillDirectory = resolve(pluginDirectory,'../../skills/tokensaver-docs'); await stat(skillDirectory); }
    // First-use tools must be available before the background MCP connection is ready.
    await ctx.tool.transform(editor => {
      const string = { type: 'string' }, boolean = { type: 'boolean' };
      const add = (name, properties, required, execute) => editor.add({
        name, description: legacy.tool[name].description,
        input: { type: 'object', properties, required, additionalProperties: false },
        options: { codemode: false },
        execute: async (input, context) => {
          const sessionID = context.sessionID;
          const request = (sessionID && requestBySession.get(sessionID)) ?? { text: '' };
          const searchingDocument = name === 'tokensaver_docs_context' && request.documentQuestion &&
            typeof input.source === 'string' && resolve(input.source) === resolve(request.documentQuestion);
          if (searchingDocument) {
            if (request.documentSearches >= 2 || request.documentSearchStatus === 'ready') {
              throw new Error(request.documentSearchStatus === 'no_match'
                ? documentSearchExhausted : 'Use the evidence already returned for this document or read its Markdown continuation.');
            }
            request.documentSearches += 1;
          }
          if ((name === 'tokensaver_docs_list_image_models' ||
               name === 'tokensaver_docs_preferences') && typeof input.endpoint === 'string') {
            // A private-network address is not permission to probe arbitrary
            // internal services. Accept only the real user's supplied endpoint
            // or an already saved one, not an agent-invented address.
            const known = parseResult(await run(['preferences']))?.preferences?.endpoint;
            if (known !== input.endpoint && !String(request.text || '').includes(input.endpoint))
              return { content: choiceError('Ask the user to provide the exact local/internal model endpoint before querying or storing it.') };
          }
          if (name === 'tokensaver_docs_preferences' && input.allow_external_images === true) {
            // Persistence is stronger than consent for a one-off operation.
            // A model-generated argument alone must never silently authorize
            // ongoing image uploads across future projects/sessions.
            const prompt = String(request.text || '');
            const explicitlyPersistent = /(?:앞으로|향후|매번|계속|항상|저장|기본값|future|always|persist|remember|default)/i.test(prompt);
            const explicitlyExternal = /(?:이미지.{0,25}(?:외부|전송|제공자)|(?:외부|전송).{0,25}이미지|send images|upload images|image transmission)/i.test(prompt);
            const named = typeof input.provider === 'string' &&
              typeof input.model === 'string' && prompt.toLowerCase().includes(input.provider.toLowerCase()) &&
              prompt.toLowerCase().includes(input.model.toLowerCase());
            const actualQuestion = request.uiPersistentConsent &&
              request.uiPersistentConsent.provider === input.provider &&
              request.uiPersistentConsent.model === input.model;
            if ((!explicitlyPersistent || !explicitlyExternal || !named) && !actualQuestion)
              return { content: choiceError('Persistent external image transfer must be explicitly authorized by the user with the exact provider/model; a model choice alone is not consent.') };
          }
          if (name === 'tokensaver_docs_setup_audio') {
            if (request.audioDeclined || request.completed)
              return { content: JSON.stringify({status:'stopped',next:'Do not make further audio setup calls for this request.'}) };
            if (!sessionID || !request.audio || !request.messageID)
              return { content: choiceError('A current explicit audio-to-Markdown request is required before local model setup.') };
            return { content: await setupAudio(request,input) };
          }
          if (name === 'tokensaver_docs_convert_audio') {
            if (request.audioDeclined || request.completed)
              return { content: JSON.stringify({status:'consent_declined',next:'Stop without further audio tools.'}) };
            return { content: await convertAudio(request,input) };
          }
          let selected = request.profile;
          let callInput = input;
          if (name === 'tokensaver_docs_prepare' && (input.image_mode === 'analyze' || input.transcribe_images === true)) {
            if (!sessionID || !request.messageID)
              return { content: choiceError('A real user request is required before image analysis.') };
            selected ??= request.uiModel ?? await configuredImageProfile();
            if (selected && ((input.model && input.model !== selected.model) ||
                (input.model_provider && input.model_provider !== selected.provider))) {
              request.profile = selected;
              request.pending = Boolean(request.conversion);
              if (sessionID) requestBySession.set(sessionID,request);
              return { content: choiceError('Use the selected image model or ask the user to select another model first.') };
            }
            request.profile = selected;
            if (selected) callInput = ['local', 'opencode'].includes(selected.provider)
              // These runtime profiles include a persistent trusted transport
              // policy and cannot be represented by legacy bare model flags.
              ? { ...input, model_provider: undefined, model: undefined }
              : { ...input, model_provider: selected.provider, model: selected.model };
          }
          if (name === 'tokensaver_docs_setup_model' && input.confirmed && request.defaultConfirmation) {
            if ((input.model && input.model !== request.defaultConfirmation.model) ||
                (input.provider && input.provider !== request.defaultConfirmation.provider))
              return { content: choiceError('Use the model awaiting default-save confirmation.') };
            callInput = { ...input, provider: request.defaultConfirmation.provider, model: request.defaultConfirmation.model };
          }
          const blocked = explicitChoiceError(name,callInput,{...request,profile:selected});
          if (blocked) {
            if (name === 'tokensaver_docs_prepare' && request.conversion) request.pending = true;
            if (name === 'tokensaver_docs_setup_model' && request.conversion && input.save_as_default && input.confirmed &&
                !request.defaultConfirmation && input.provider && input.model &&
                matchesModelChoice(request.text,input.provider,input.model) &&
                /and save this model as default[.!]?$/i.test(request.text) &&
                !/\b(?:no|do not|don't|decline|cancel)\b|^(?:아니요|아니|취소)/i.test(request.text)) {
              request.defaultConfirmation = { provider: input.provider, model: input.model };
              request.pending = true;
            }
            if (parseResult(blocked)?.status === 'save_declined') {
              request.pending = false;
              delete request.defaultConfirmation;
            }
            if (sessionID) requestBySession.set(sessionID,request);
            return { content: blocked };
          }
          if ((name === 'tokensaver_docs_prepare' || name === 'tokensaver_docs_context') &&
              typeof callInput.source === 'string') {
            const session = sessionID && ctx.session?.get
              ? await ctx.session.get({sessionID}).catch(() => null) : null;
            const project = context?.directory ?? session?.location?.directory ??
              session?.directory ?? ctx.location?.directory;
            const found = await resolveProjectSource(callInput.source, project);
            if (found.status !== 'ready' && found.status !== 'source_not_found' &&
                found.status !== 'project_required')
              return { content: JSON.stringify(found) };
            if (found.status === 'ready') {
              // The native binary runs in the service's cwd. Use the exact
              // project-resolved path; do not move results to another project.
              callInput = {...callInput, source:found.source,
                output:resolve(project || dirname(found.source),callInput.output ?? 'converted')};
            }
            // For an absent file, preserve the existing native CLI's explicit
            // missing-file error (and compatibility with virtual/mock CLI
            // inputs). Never substitute a similarly named file outside scope.
          }
          const result = await execute(callInput);
          const research = researchSessions.get(sessionID);
          if (name === 'tokensaver_docs_search_research' && research &&
              resolve(input.project) === resolve(research.directory)) research.searched = true;
          const parsed = parseResult(result);
          if (name === 'tokensaver_docs_list_image_models' && request?.conversion && Array.isArray(parsed?.models)) {
            request.catalogModels=parsed.models.map(model=>({...model,provider:input.provider}));
            request.catalogEndpoint=parsed.endpoint || input.endpoint || null;
            request.catalogNetworkPolicy=input.network_policy || 'local_only';
          }
          if (searchingDocument) {
            request.documentSearchStatus = parsed?.status;
          }
          if (name === 'tokensaver_docs_prepare' && request.conversion) {
            if (['ready','needs_review'].includes(parsed?.status)) {
              request.pending = false;
              request.completed = true;
              delete request.profile;
              delete request.defaultConfirmation;
            } else {
              request.pending = true;
              request.completed = false;
            }
          }
          if (name === 'tokensaver_docs_setup_model') {
            if (parsed?.status === 'selection_ready') {
              request.profile = parsed.profile;
              request.pending = true;
            } else if (parsed?.status === 'confirmation_required') {
              request.defaultConfirmation = parsed.profile;
              request.pending = true;
            } else if (request.conversion && ['setup_required','choice_required'].includes(parsed?.status)) {
              request.pending = true;
            } else if (parsed?.status === 'configured' && parsed.model) {
              request.profile = parsed.model;
              request.pending = exactChoice(request.text) === 'select_model';
              delete request.defaultConfirmation;
            } else if (parsed?.status === 'deferred' || parsed?.status === 'save_declined') {
              request.pending = false;
              delete request.profile;
              delete request.defaultConfirmation;
            }
          }
          if (sessionID) requestBySession.set(sessionID,request);
          return { content: result };
        },
      });
      add('tokensaver_docs_prepare', {source:string,output:string,transcribe_images:boolean,
        image_mode:{type:'string',enum:['analyze','preserve','placeholder']},
        model_provider:{type:'string',enum:['openrouter','codex','claude']},model:string,
        allow_unverified_model:boolean}, ['source'], legacy.tool.tokensaver_docs_prepare.execute);
      add('tokensaver_docs_setup_model', {provider:{type:'string',enum:['openrouter','codex','claude']},
        model:string,defer:boolean,save_as_default:boolean,confirmed:boolean}, [], legacy.tool.tokensaver_docs_setup_model.execute);
      add('tokensaver_docs_preferences', {
        set_mode:{type:'string',enum:['analyze','preserve','placeholder']},
        runtime:{type:'string',enum:['opencode','codex','claude','api','local']},
        provider:{type:'string'},
        model:string,endpoint:string,
        network_policy:{type:'string',enum:['local_only','internal_only','external_allowed']},
        allow_external_images:boolean
      }, [], legacy.tool.tokensaver_docs_preferences.execute);
      add('tokensaver_docs_list_image_models', {
        provider:{type:'string',enum:['openrouter','codex','claude','ollama','lmstudio','openai_compatible']},
        endpoint:string,query:string,limit:{type:'integer',minimum:1,maximum:40},
        offset:{type:'integer',minimum:0},
        network_policy:{type:'string',enum:['local_only','internal_only']}
      }, ['provider'], legacy.tool.tokensaver_docs_list_image_models.execute);
      // The host catalog is accessible even when the pinned native runtime
      // hasn't been downloaded. It does not activate image analysis by itself.
      editor.add({
        name:'tokensaver_docs_opencode_models',
        description:'Show actual image-input models currently configured in OpenCode, with provider IDs. Model discovery does not imply native image-conversion availability or external data-transfer approval.',
        input:{type:'object',additionalProperties:false,properties:{
          query:{type:'string'},limit:{type:'integer',minimum:1,maximum:40},
          offset:{type:'integer',minimum:0}},required:[]},
        options:{codemode:false},
        execute:async (input,context) => {
          if (!ctx.model?.list) return {content:JSON.stringify({status:'unavailable',reason:'OpenCode model catalog API unavailable'})};
          try {
            const response=await ctx.model.list();
            const page=pagedOpenCodeModels(response,input);
            const request=context?.sessionID && requestBySession.get(context.sessionID);
            if (request?.conversion && page.status === 'ready') {
              request.catalogModels=page.models;
              request.catalogEndpoint=null;
              request.uiRuntime={runtime:'opencode'};
              requestBySession.set(context.sessionID,request);
            }
            return {content:JSON.stringify(page)};
          } catch (error) {
            return {content:JSON.stringify({status:'unavailable',reason:'Model catalog lookup failed; no network fallback was used'})};
          }
        }
      });
      add('tokensaver_docs_setup_audio', {model:{type:'string',enum:['tiny','base','small']},confirmed:boolean}, [], legacy.tool.tokensaver_docs_setup_audio.execute);
      add('tokensaver_docs_convert_audio', {source:string,output:string,confirmed:boolean}, ['source'], legacy.tool.tokensaver_docs_convert_audio.execute);
      add('tokensaver_docs_read', {file:string,start_line:{type:'integer',minimum:1}}, ['file'], legacy.tool.tokensaver_docs_read.execute);
      add('tokensaver_docs_context', {source:string,query:{type:'string',description:'Search keywords as they appear in the document. For a Korean question and unknown document language, include English equivalents, e.g. "환불 기한 refund deadline".'},output:string,max_tokens:{type:'integer',minimum:1,maximum:10000}}, ['source','query'], legacy.tool.tokensaver_docs_context.execute);
      add('tokensaver_docs_search_research', {project:string,query:string,version_id:string,conversion_id:string,max_tokens:{type:'integer',minimum:1,maximum:10000}}, ['project','query'], legacy.tool.tokensaver_docs_search_research.execute);
    });
    const skillPath = join(skillDirectory,'SKILL.md');
    const skillContent = await readFile(skillPath,'utf8');
    await ctx.skill.transform(editor => editor.add({
      id:'tokensaver-docs-opencode',name:'TokenSaver Docs for OpenCode',
      description:'Answer questions about local PDF, DOCX, XLSX, HTML or Markdown with evidence and Markdown line numbers. Also convert local documents and media to Markdown.',
      path:skillPath,content:skillContent,
    }));
    await ctx.session.hook('context', event => {
      const request = requestBySession.get(event.sessionID);
      const research = researchSessions.get(event.sessionID);
      if (research?.guidance && !research.guided) {
        event.system.push({type:'text',text:research.guidance});
        research.guided = true;
      }
      if (request?.documentQuestion && (!request.documentSearches || request.documentSearchStatus === 'no_match')) {
        event.system.push({type:'text',text:documentQuestionGuidance(request)});
      }
      if (request?.conversion) {
        if (request.audioDeclined) {
          event.system.push({type:'text',text:'The user declined local audio transcription. Stop without converting or invoking audio tools.'});
          return;
        }
        if (request.completed) {
          event.system.push({type:'text',text:completedConversionInstruction});
          return;
        }
        event.system.push({type:'text',text:request.audio ? audioConversionInstruction : conversionInstruction});
        if (request.pending && request.profile)
          event.system.push({type:'text',text:selectedModelApprovalInstruction});
      }
    });
    await ctx.session.hook('prompt', async event => {
      const sessionID = event.sessionID;
      if (typeof sessionID !== 'string' || !sessionID.trim() ||
          typeof event.messageID !== 'string' || !event.messageID.trim()) {
        if (sessionID) requestBySession.delete(sessionID);
        return;
      }
      const previous = requestBySession.get(sessionID);
      const text = event.prompt?.text ?? '';
      const directory = ctx.location?.directory;
      researchSessions.delete(sessionID);
      if (ctx.event?.subscribe && directory) {
        const canonical = await realpath(directory).catch(() => null);
        const root = canonical && await researchProject(canonical);
        if (root) {
          const session = await ctx.session.get({sessionID}).catch(() => null);
          const location = session?.location?.directory ?? session?.directory;
          if (typeof location === 'string' && await realpath(location).catch(() => null) === canonical) {
            const followUp = researchFollowUp.test(text);
            researchSessions.set(sessionID,{directory:root,cwd:canonical,followUp,guidance:researchGuidance(root, text)});
          }
        }
      }
      const audio = isAudioMarkdownRequest(event.prompt);
      const conversion = audio || isMarkdownConversionRequest(event.prompt);
      const continuing = previous?.pending && !conversion && choiceReply(text,previous);
      const active = conversion || continuing;
      const documentQuestion = !active && documentQuestionSource(text);
      if (active) requestBySession.set(sessionID,{
        text,messageID:event.messageID,conversion:true,pending:continuing || conversion,
        audio:audio || Boolean(continuing && previous?.audio),
        audioStage:audio ? 'model' : continuing ? previous?.audioStage : undefined,
        audioModel:continuing ? previous?.audioModel : undefined,
        audioModelPath:continuing ? previous?.audioModelPath : undefined,
        audioSource:continuing ? previous?.audioSource : undefined,
        audioDeclined:continuing ? previous?.audioDeclined : undefined,
        audioRequestedSource:audio ? await requestedAudioSource(event.prompt) : continuing ? previous?.audioRequestedSource : undefined,
        files:event.prompt?.files ?? [],
        profile:continuing ? previous?.profile : undefined,
        uiMode:continuing ? previous?.uiMode : undefined,
        uiModel:continuing ? previous?.uiModel : undefined,
        uiConsent:continuing ? previous?.uiConsent : undefined,
        uiPersistentConsent:continuing ? previous?.uiPersistentConsent : undefined,
        uiRuntime:continuing ? previous?.uiRuntime : undefined,
        catalogModels:continuing ? previous?.catalogModels : undefined,
        catalogEndpoint:continuing ? previous?.catalogEndpoint : undefined,
        catalogNetworkPolicy:continuing ? previous?.catalogNetworkPolicy : undefined,
        preferencesSaved:continuing ? previous?.preferencesSaved : undefined,
        defaultConfirmation:continuing ? previous?.defaultConfirmation : undefined,
      });
      else if (documentQuestion) requestBySession.set(sessionID,{text,messageID:event.messageID,documentQuestion,documentSearches:0});
      else requestBySession.delete(sessionID);
    });
    // Completed question UI options are the user's answer, not a request to
    // type it again. Persist the first-run choice immediately and reuse it.
    await ctx.tool.hook('execute.after', async event => {
      const request = requestBySession.get(event.sessionID);
      if (!request?.conversion) return;
      recordQuestionAnswers(event, request);
      if (event.tool === 'question' && event.status === 'completed' && !request.preferencesSaved) {
        let args=null;
        if (['preserve','placeholder'].includes(request.uiMode)) {
          args=['preferences','--set-mode',request.uiMode];
        } else if (request.uiMode === 'analyze' && request.uiModel && request.uiRuntime) {
          const {runtime,provider} = request.uiRuntime;
          const model = runtime === 'opencode'
            ? request.uiModel.model.slice((provider+'/').length)
            : request.uiModel.model;
          const local = runtime === 'local';
          if (local || (request.uiPersistentConsent?.provider === request.uiModel.provider &&
                        request.uiPersistentConsent?.model === request.uiModel.model)) {
            args=['preferences','--set-mode','analyze',
              '--runtime',runtime,'--provider',provider,'--model',model,
              '--network-policy',local ? request.catalogNetworkPolicy || 'local_only' : 'external_allowed',
              ...(local && request.catalogEndpoint ? ['--endpoint',request.catalogEndpoint] : []),
              ...(!local ? ['--allow-external-images'] : [])];
          }
        }
        if (args) {
          const saved=parseResult(await run(args));
          if (saved?.status === 'configured') {
            request.preferencesSaved=true;
            request.pending=true;
          } else if (saved?.status) {
            request.preferenceError=saved;
          }
        }
      }
      requestBySession.set(event.sessionID, request);
    });
    // Register the optional internal MCP bridge only when its binary is ready.
    // Native V2 document tools work without it and can bootstrap on first use.
    if (installedExecutable) {
      await ctx.mcp.transform(editor => {
        editor.set('tokensaver-docs', { type: 'local', command: [installedExecutable, 'mcp'], codemode: false });
      });
    }
    if (ctx.event?.subscribe) {
      // Save before short-lived CLI clients tear down the server's idle event stream.
      await ctx.tool.hook('execute.after', async event => {
        const research = researchSessions.get(event.sessionID);
        const path = event.input?.path ?? event.input?.filePath;
        if (!research) return;
        if (['bash','shell'].includes(event.tool)) research.synced = false;
        if (event.status !== 'completed' || !['write','edit'].includes(event.tool) || typeof path !== 'string') return;
        if (insideResearchInbox(research.directory, research.cwd, path)) {
          research.synced = parseResult(await run(['knowledge','sync',research.directory]))?.status === 'ready';
        }
      });
    }
    await ctx.tool.hook('execute.before', async event => {
      // MCP read-only names come from mcp_server.py; conversion/settings use guarded native tools only.
      const safeMcp = new Set(['list_free_models','outline_document','search_documents','read_document','search_research']);
      const mcpName = event.tool.startsWith('tokensaver-docs_') ? event.tool.slice('tokensaver-docs_'.length) : null;
      const nativeName = event.tool.startsWith('tokensaver_docs_') ? event.tool.slice('tokensaver_docs_'.length) : null;
      if ((mcpName !== null && !safeMcp.has(mcpName)) ||
          (nativeName !== null && !['prepare','preferences','list_image_models','opencode_models','setup_model','setup_audio','convert_audio','read','context',...safeMcp].includes(nativeName)))
        throw new Error('Use guarded native tokensaver_docs_prepare, tokensaver_docs_setup_audio, or tokensaver_docs_convert_audio; duplicate MCP conversion/settings routes are disabled.');
      const request = requestBySession.get(event.sessionID);
      if (event.tool === 'tokensaver_docs_prepare' && request?.documentQuestion &&
          typeof event.input?.source === 'string' && resolve(event.input.source) === resolve(request.documentQuestion)) {
        throw new Error(documentQuestionGuidance(request));
      }
      const readPath = event.input?.path ?? event.input?.filePath ?? event.input?.file;
      const research = researchSessions.get(event.sessionID);
      if (research?.guidance && research.followUp && !research.searched &&
          ['read','grep','tokensaver_docs_read'].includes(event.tool) && typeof readPath === 'string') {
        const local = relative(research.directory, resolve(research.cwd, readPath)).split(/[\\/]/).join('/');
        if (['docs/research/inbox','docs/tokensaver-docs'].some(prefix => local === prefix || local.startsWith(prefix + '/'))) {
          throw new Error('Use tokensaver_docs_search_research first for this project research question.');
        }
      }
      if (request?.documentQuestion && (!request.documentSearches || request.documentSearchStatus === 'no_match')) {
        const namedRead = ['read','grep','tokensaver_docs_read'].includes(event.tool) && typeof readPath === 'string' &&
          resolve(readPath) === resolve(request.documentQuestion);
        const namedShell = event.tool === 'shell' && typeof event.input?.command === 'string' &&
          event.input.command.includes(basename(request.documentQuestion));
        if (namedRead || namedShell) throw new Error(documentQuestionGuidance(request));
      }
      if (request?.completed)
        throw new Error('Preparation is complete; return the reported Markdown paths and status without further tool calls.');
      const fileAccess = /(?:^|__|_)(?:read(?:_[a-z]+)?|glob|grep|search|webfetch|websearch|write|edit|shell|bash|execute)(?:_|$)/i.test(event.tool);
      if (request?.conversion && fileAccess) {
        throw new Error('Use tokensaver_docs_prepare first for this explicit conversion request; do not read, search, fetch, or write files directly.');
      }
      await legacy['tool.execute.before']({ tool: event.tool }, { args: event.input });
    });
    return () => researchEvents.abort();
  },
};
