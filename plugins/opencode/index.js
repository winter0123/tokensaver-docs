import { tool } from '@opencode-ai/plugin';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { join, dirname, extname, resolve } from 'node:path';
import { readFile, stat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { homedir } from 'node:os';

const executable = join(dirname(fileURLToPath(import.meta.url)), 'bin', process.platform === 'win32' ? 'tokensaver-docs.exe' : 'tokensaver-docs');

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
      description: 'CALL FIRST. Ask the returned first-use/model/image question; never choose for the user. analyze includes images, visible text and descriptions; preserve includes images only; placeholder writes [이미지] at their positions with no image text, description or link. Unsupported models require switching models or explicitly continuing with placeholder. One-time model parameters do not change defaults. Image analysis may send images externally; audio is separate. Never read raw HTML/Base64 or write conversion scripts.',
      args: { source: tool.schema.string(), output: tool.schema.string().optional(), transcribe_images: tool.schema.boolean().optional(), image_mode: tool.schema.enum(['analyze','preserve','placeholder']).optional(), model_provider: tool.schema.enum(['openrouter','codex','claude']).optional(), model: tool.schema.string().optional(), allow_unverified_model: tool.schema.boolean().optional() },
      execute: ({source,output,transcribe_images,image_mode,model_provider,model,allow_unverified_model}) => run(['prepare',source,'--output',output ?? 'converted',...(transcribe_images === undefined ? [] : [transcribe_images ? '--transcribe-images' : '--skip-image-transcription']),...(image_mode ? ['--image-mode',image_mode] : []),...(model_provider ? ['--model-provider',model_provider] : []),...(model ? ['--model',model] : []),...(allow_unverified_model ? ['--allow-unverified-model'] : [])]),
    }),
    tokensaver_docs_setup_model: tool({
      description: 'Inspect first-use setup or a user-selected conversion model. Defer only when the user chooses later. A one-time selection does not save defaults; save_as_default requires explicit confirmation. Never request API keys in chat or assume the host chat model is the conversion model.',
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
    // First-use tools must be available before the background MCP connection is ready.
    await ctx.tool.transform(editor => {
      const string = { type: 'string' }, boolean = { type: 'boolean' };
      const add = (name, properties, required, execute) => editor.add({
        name, description: legacy.tool[name].description,
        input: { type: 'object', properties, required, additionalProperties: false },
        options: { codemode: false },
        execute: async input => ({ content: await execute(input) }),
      });
      add('tokensaver_docs_prepare', {source:string,output:string,transcribe_images:boolean,
        image_mode:{type:'string',enum:['analyze','preserve','placeholder']},
        model_provider:{type:'string',enum:['openrouter','codex','claude']},model:string,
        allow_unverified_model:boolean}, ['source'], legacy.tool.tokensaver_docs_prepare.execute);
      add('tokensaver_docs_setup_model', {provider:{type:'string',enum:['openrouter','codex','claude']},
        model:string,defer:boolean,save_as_default:boolean,confirmed:boolean}, [], legacy.tool.tokensaver_docs_setup_model.execute);
      add('tokensaver_docs_read', {file:string,start_line:{type:'integer',minimum:1}}, ['file'], legacy.tool.tokensaver_docs_read.execute);
    });
    await ctx.mcp.transform(editor => {
      editor.set('tokensaver-docs', { type: 'local', command: [executable, 'mcp'], codemode: false });
    });
    await ctx.tool.hook('execute.before', async event => {
      await legacy['tool.execute.before']({ tool: event.tool }, { args: event.input });
    });
  },
};
