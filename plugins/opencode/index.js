// SPDX-License-Identifier: MIT
// Copyright (c) 2026 winter0123 and tokensaver-docs contributors
import { tool } from '@opencode-ai/plugin';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { join, dirname, extname, resolve } from 'node:path';
import { readFile, stat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { homedir } from 'node:os';

const executable = join(dirname(fileURLToPath(import.meta.url)), 'bin', process.platform === 'win32' ? 'tokensaver-docs.exe' : 'tokensaver-docs');
// shortcut: request text remains in memory until a newer real prompt; add verified V2 session-final cleanup if long-lived servers accumulate entries.
const requestBySession = new Map();

const conversionInstruction = 'For this explicit conversion request only, call tokensaver_docs_prepare immediately as your first tool, before glob, listing, reading originals, or writing conversion commands. Use the source path or attachment name already given; if it is missing or ambiguous, ask instead of searching. Omit output unless the user names an output directory; output is a directory, never infer a filename. Respect an explicitly chosen alternative converter. Follow the tool’s setup and image-choice questions: without an actual user choice, stop and ask; never infer a model, defer, image mode, or provider consent. For conversion-only, report the returned Markdown paths and status without rereading the result.';
const selectedModelApprovalInstruction = 'An image model is already configured or selected for this session. If the current genuine user message explicitly approves image analysis, immediately call tokensaver_docs_prepare for the original source with image_mode analyze, using that selected model. Do not ask the user to select or repeat the provider/model. This instruction does not grant consent; the tool accepts only explicit approval in the current real user message.';
const completedConversionInstruction = 'Preparation is complete. Return the reported Markdown paths and status to the user. Do not call any more tools or reread the result.';

function isMarkdownConversionRequest(prompt) {
  const text = prompt?.text ?? '';
  const files = prompt?.files ?? [];
  const source = files.length > 0 || /\b(?:image|photo|picture|screenshot|document|file|folder|pdf|docx?|xlsx?|html|htm|pptx?)\b|\.(?:png|jpe?g|gif|webp|bmp|tiff?|svg|pdf|docx?|xlsx?|html|htm|pptx?)\b|이미지|사진|스크린샷|캡처|문서|파일|폴더/i.test(text);
  const target = /\b(?:to|into|as)\s+(?:an?\s+)?(?:markdown|md)(?:\s+(?:file|document))?|\b(?:markdown|md)\s+file\b|마크다운(?:으로|\s*파일)|md\s*파일(?:로)?|md로/i.test(text);
  const alternative = /\b(?:pandoc|libreoffice|obsidian)\b|\b(?:another|different|external|my)\s+(?:converter|tool|command|script)\b|(?:다른|별도|직접 지정한)\s*(?:변환기|도구|명령|스크립트)|\buse\s+(?!tokensaver\b)(?:the\s+)?[a-z][\w.@/-]*\s+to\s+(?:convert|turn|make|write|save)/i.test(text);
  const convert = /\b(?:convert|turn|transform|export)\b|변환|바꿔|정리해/i.test(text);
  return source && target && convert && !alternative;
}

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

function run(args) {
  return new Promise((resolve) => {
    const child = spawn(executable, args, { shell: false, windowsHide: true });
    let output = '';
    let truncated = false;
    let timedOut = false;
    const analyzing = args.includes('--transcribe-images') || args[args.indexOf('--image-mode') + 1] === 'analyze';
    const timeout = analyzing ? 7200000 : 300000;
    const timer = setTimeout(() => { timedOut = true; child.kill(); }, timeout);
    const append = chunk => {
      const text = chunk.toString();
      if (output.length + text.length > 6500) truncated = true;
      output += text.slice(0, Math.max(0, 6500 - output.length));
    };
    child.stdout.on('data', append);
    child.stderr.on('data', append);
    child.on('error', error => { clearTimeout(timer); resolve(`Unable to start bundled tokensaver-docs: ${error.message}`); });
    child.on('close', code => {
      clearTimeout(timer);
      if (['prepare','setup-model'].includes(args[0]) && !truncated && !timedOut) {
        try {
          if (typeof JSON.parse(output).status === 'string') return resolve(output);
        } catch { /* retain process errors below */ }
      }
      resolve(output + (truncated ? '\n[Output truncated]' : '') + (timedOut ? '\n[Timed out; completed image results remain cached. Retry the same request to resume.]' : code ? `\n[Exit code: ${code}]` : ''));
    });
  });
}

export const TokenSaverDocsPlugin = async () => ({
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
      description: 'Prepare a user-selected multilingual local audio model. Confirm the size with the user before downloading.',
      args: { model: tool.schema.enum(['tiny','base','small']), confirmed: tool.schema.boolean() },
      execute: ({model,confirmed}) => run(['setup-audio','--model',model,...(confirmed ? ['--download'] : [])]),
    }),
    tokensaver_docs_context: tool({
      description: 'Reuse converted files and return bounded original evidence, source lines and pending items in one call.',
      args: { source: tool.schema.string(), query: tool.schema.string(), output: tool.schema.string(), max_tokens: tool.schema.number().int().min(1).max(10000).optional() },
      execute: ({source,query,output,max_tokens}) => run(['context',source,query,'--output',output,'--max-tokens',String(max_tokens ?? 1200)]),
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
});

// V2 uses a default plugin definition; V1 keeps the named function above.
export default {
  id: 'tokensaver-docs',
  async setup(ctx) {
    const legacy = await TokenSaverDocsPlugin();
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
          const parsed = parseResult(result);
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
      add('tokensaver_docs_read', {file:string,start_line:{type:'integer',minimum:1}}, ['file'], legacy.tool.tokensaver_docs_read.execute);
    });
    const skillPath = join(skillDirectory,'SKILL.md');
    const skillContent = await readFile(skillPath,'utf8');
    await ctx.skill.transform(editor => editor.add({
      id:'tokensaver-docs-opencode',name:'TokenSaver Docs for OpenCode',
      description:'Convert local PDF, DOCX, XLSX, HTML, photos, images, screenshots or audio to Markdown. Use for file/folder-to-MD requests and relevant passage retrieval.',
      path:skillPath,content:skillContent,
    }));
    await ctx.session.hook('context', event => {
      const request = requestBySession.get(event.sessionID);
      if (request?.conversion) {
        if (request.completed) {
          event.system.push({type:'text',text:completedConversionInstruction});
          return;
        }
        event.system.push({type:'text',text:conversionInstruction});
        if (request.pending && request.profile)
          event.system.push({type:'text',text:selectedModelApprovalInstruction});
      }
    });
    await ctx.session.hook('prompt', event => {
      const sessionID = event.sessionID;
      if (typeof sessionID !== 'string' || !sessionID.trim() ||
          typeof event.messageID !== 'string' || !event.messageID.trim()) {
        if (sessionID) requestBySession.delete(sessionID);
        return;
      }
      const previous = requestBySession.get(sessionID);
      const text = event.prompt?.text ?? '';
      const conversion = isMarkdownConversionRequest(event.prompt);
      const continuing = previous?.pending && !conversion && choiceReply(text,previous);
      const active = conversion || continuing;
      if (active) requestBySession.set(sessionID,{
        text,messageID:event.messageID,conversion:true,pending:continuing,
        profile:continuing ? previous?.profile : undefined,
        defaultConfirmation:continuing ? previous?.defaultConfirmation : undefined,
      });
      else requestBySession.delete(sessionID);
    });
    await ctx.mcp.transform(editor => {
      editor.set('tokensaver-docs', { type: 'local', command: [executable, 'mcp'], codemode: false });
    });
    await ctx.tool.hook('execute.before', async event => {
      // MCP read-only names come from mcp_server.py; conversion/settings use guarded native tools only.
      const safeMcp = new Set(['list_free_models','outline_document','search_documents','read_document']);
      const mcpName = event.tool.startsWith('tokensaver-docs_') ? event.tool.slice('tokensaver-docs_'.length) : null;
      const nativeName = event.tool.startsWith('tokensaver_docs_') ? event.tool.slice('tokensaver_docs_'.length) : null;
      if ((mcpName !== null && !safeMcp.has(mcpName)) ||
          (nativeName !== null && !['prepare','setup_model','read',...safeMcp].includes(nativeName)))
        throw new Error('Use the guarded native tokensaver_docs_prepare or tokensaver_docs_setup_model tools; duplicate conversion/settings routes are disabled.');
      const request = requestBySession.get(event.sessionID);
      if (request?.completed)
        throw new Error('Preparation is complete; return the reported Markdown paths and status without further tool calls.');
      const fileAccess = /(?:^|__|_)(?:read(?:_[a-z]+)?|glob|grep|search|webfetch|websearch|write|edit|shell|bash|execute)(?:_|$)/i.test(event.tool);
      if (request?.conversion && fileAccess) {
        throw new Error('Use tokensaver_docs_prepare first for this explicit conversion request; do not read, search, fetch, or write files directly.');
      }
      await legacy['tool.execute.before']({ tool: event.tool }, { args: event.input });
    });
  },
};
