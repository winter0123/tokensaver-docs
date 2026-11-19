// SPDX-License-Identifier: MIT
// Copyright (c) 2026 winter0123 and tokensaver-docs contributors
import { tool } from '@opencode-ai/plugin';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { basename, join, dirname, extname, resolve, relative, isAbsolute } from 'node:path';
import { readFile, stat, lstat, realpath } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { homedir } from 'node:os';
import researchRouting from '../../tokensaver_docs/data/research-routing.json' with { type: 'json' };

const executable = join(dirname(fileURLToPath(import.meta.url)), 'bin', process.platform === 'win32' ? 'tokensaver-docs.exe' : 'tokensaver-docs');
// shortcut: request text remains in memory until a newer real prompt; add verified V2 session-final cleanup if long-lived servers accumulate entries.
const requestBySession = new Map();

const conversionInstruction = 'For this explicit conversion request only, call tokensaver_docs_prepare immediately as your first tool, before glob, listing, reading originals, or writing conversion commands. Use the source path or attachment name already given; if it is missing or ambiguous, ask instead of searching. Omit output unless the user names an output directory; output is a directory, never infer a filename. Respect an explicitly chosen alternative converter. Follow the tool’s setup and image-choice questions: without an actual user choice, stop and ask; never infer a model, defer, image mode, or provider consent. For conversion-only, report the returned Markdown paths and status without rereading the result.';
const audioConversionInstruction = 'For this explicit local audio conversion request, use tokensaver_docs_setup_audio to ask the user to select tiny, base, or small, then show the returned exact download size and wait for the user’s explicit download confirmation. After setup, call tokensaver_docs_convert_audio to ask for separate explicit local transcription consent. Convert only the single audio file the user named, with the configured local whisper.cpp profile; never use an external provider or process folders. If any question is unanswered, declined, or canceled, stop without downloading or transcribing.';
const selectedModelApprovalInstruction = 'An image model is already configured or selected for this session. If the current genuine user message explicitly approves image analysis, immediately call tokensaver_docs_prepare for the original source with image_mode analyze, using that selected model. Do not ask the user to select or repeat the provider/model. This instruction does not grant consent; the tool accepts only explicit approval in the current real user message.';
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
  const value = text.trim().toLowerCase().replace(/[.!]$/, '');
  const labels = {
    defer: ['later','defer','not now','나중에','나중에 선택하기'],
    select_model: ['모델 선택하기','모델 바꾸기'],
    preserve: ['preserve','images only','image links only','이미지 링크만','보존(preserve)','이미지만 넣기'],
    placeholder: ['placeholder','[이미지]','플레이스홀더(placeholder)','현재 모델로 계속하기'],
    analyze: ['이미지·글자·설명 넣기','이미지 분석에 동의합니다'],
    decline: ['no','no, do not analyze the image','no, do not analyze it','cancel','아니요','취소'],
    confirm: ['yes','confirm','네','예','확인'],
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

function choiceError(choice) {
  return JSON.stringify({status:'choice_required',question:choice,
    next:'Ask the user in chat and stop this turn. Do not retry with inferred arguments.'});
}

function parseResult(result) {
  try { return JSON.parse(result); } catch { return null; }
}

async function configuredImageProfile() {
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
          !matchesModelChoice(text,input.provider,input.model)))
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
    const approved = choice === 'analyze';
    const selected = request?.profile;
    const hasModelChoice = Boolean(input.model && input.model_provider &&
      text.toLowerCase().includes(input.model.toLowerCase()) && text.toLowerCase().includes(input.model_provider.toLowerCase()));
    const mismatch = selected && ((input.model && input.model !== selected.model) ||
      (input.model_provider && input.model_provider !== selected.provider));
    if (!approved || mismatch || (!selected && !hasModelChoice))
      return choiceError(selected && !mismatch
        ? 'The image model is already selected. Ask only for explicit image-analysis approval; use this same model after the user approves.'
        : 'Ask the user to choose an image model and explicitly approve image analysis for this request.');
  }
  if (mode === 'placeholder' && choice !== 'placeholder')
    return choiceError('Ask whether the user wants placeholder images with no extracted text or description.');
  if (mode === 'preserve' && choice !== 'preserve')
    return choiceError('Ask whether the user wants image links only, without extracted text or descriptions.');
  return null;
}

function run(args, env = process.env) {
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
            selected ??= await configuredImageProfile();
            if (selected && ((input.model && input.model !== selected.model) ||
                (input.model_provider && input.model_provider !== selected.provider))) {
              request.profile = selected;
              request.pending = Boolean(request.conversion);
              if (sessionID) requestBySession.set(sessionID,request);
              return { content: choiceError('Use the selected image model or ask the user to select another model first.') };
            }
            request.profile = selected;
            if (selected) callInput = { ...input, model_provider: selected.provider, model: selected.model };
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
          const result = await execute(callInput);
          const research = researchSessions.get(sessionID);
          if (name === 'tokensaver_docs_search_research' && research &&
              resolve(input.project) === resolve(research.directory)) research.searched = true;
          const parsed = parseResult(result);
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
        defaultConfirmation:continuing ? previous?.defaultConfirmation : undefined,
      });
      else if (documentQuestion) requestBySession.set(sessionID,{text,messageID:event.messageID,documentQuestion,documentSearches:0});
      else requestBySession.delete(sessionID);
    });
    await ctx.mcp.transform(editor => {
      editor.set('tokensaver-docs', { type: 'local', command: [executable, 'mcp'], codemode: false });
    });
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
          (nativeName !== null && !['prepare','setup_model','setup_audio','convert_audio','read','context',...safeMcp].includes(nativeName)))
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
