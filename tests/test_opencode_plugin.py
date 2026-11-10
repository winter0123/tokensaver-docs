import base64
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from PIL import Image


@unittest.skipUnless(os.environ.get('TOKENSAVER_DOCS_PLUGIN'), 'built OpenCode plugin not supplied')
class OpenCodePluginTests(unittest.TestCase):
    def test_v2_registers_mcp_and_read_hook(self):
        script = '''
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';
const {default: plugin, TokenSaverDocsPlugin} = await import(pathToFileURL(process.env.TOKENSAVER_DOCS_PLUGIN));
const legacy = await TokenSaverDocsPlugin();
let server, hook, contextHook, promptHook, skill;
const tools = new Map();
await plugin.setup({
  mcp:{transform: async fn => fn({set: (name, value) => {server = {name, ...value}}})},
  skill:{transform: async fn => fn({add: definition => {skill = definition}})},
  session:{hook: async (name, fn) => {if(name === 'prompt') promptHook = fn; else contextHook = fn}},
  tool:{transform:async fn=>fn({add(definition){tools.set(definition.name, definition)}}),hook: async (name, fn) => {hook = {name, fn}}},
});
const prepare = tools.get('tokensaver_docs_prepare');
assert.equal(prepare.description, legacy.tool.tokensaver_docs_prepare.description);
assert.ok(prepare.description.includes('PDF, DOCX, XLSX, HTML, image/photo/screenshot or audio files/folders to Markdown'));
assert.match(prepare.description, /unless the user specifies another converter/);
assert.ok(prepare.description.includes('image/photo/screenshot text and description into an MD file'));
assert.match(prepare.description, /ordinary image viewing or questions remain normal image tasks/);
assert.match(prepare.description, /output is a directory, not an output filename; omit it to use the safe default/);
assert.match(prepare.description, /Analyze produces an MD file with an image link, visible text and a separate image description/);
assert.match(prepare.description, /never choose for the user/);
assert.match(prepare.description, /If a question fails or is cancelled, stop and ask the user; never infer a model or image mode/);
assert.match(prepare.description, /Use analyze only after the user explicitly approves image analysis with the chosen model/);
assert.match(prepare.description, /If preparation fails, report the failure instead of automatically writing a fallback conversion script/);
const setupModel = tools.get('tokensaver_docs_setup_model');
assert.equal(setupModel.description, legacy.tool.tokensaver_docs_setup_model.description);
assert.match(setupModel.description, /If a question fails or is cancelled, stop and ask the user; never infer defer, model or confirmation arguments/);
const unapproved = await prepare.execute({source:'photo.png',image_mode:'analyze',model_provider:'openrouter',model:'nvidia/nemotron-3.5-super-vl:free'},{sessionID:'test'});
assert.equal(JSON.parse(unapproved.content).status, 'choice_required');
const inferredDefer = await setupModel.execute({defer:true},{sessionID:'test'});
assert.equal(JSON.parse(inferredDefer.content).status, 'choice_required');
assert.deepEqual(prepare.input.required, ['source']);
assert.deepEqual(prepare.input.properties.image_mode.enum, ['analyze', 'preserve', 'placeholder']);
assert.equal(skill.id, 'tokensaver-docs-opencode');
assert.equal(skill.name, 'TokenSaver Docs for OpenCode');
assert.match(skill.content, /turn this photo[/]image[/]screenshot and its text[/]description into an MD file/);
assert.equal(skill.path.split('/').at(-1), 'SKILL.md');
const conversion = {sessionID:'test',messages:[{info:{role:'user'},parts:[{type:'text',text:'photo.png 사진의 글자와 설명을 MD로 정리해줘'}]}],system:[],tools:{read:{},glob:{},shell:{},write:{},edit:{},tokensaver_docs_prepare:{},tokensaver_docs_read:{},tokensaver_docs_search:{},tokensaver_docs_convert:{},question:{}}};
await promptHook({sessionID:'test',messageID:'user-1',prompt:{text:'photo.png 사진의 글자와 설명을 MD로 정리해줘',files:[]}});
await contextHook(conversion);
assert.equal(conversion.system.length, 1);
assert.match(conversion.system[0].text, /call tokensaver_docs_prepare immediately as your first tool, before glob, listing, reading originals/);
assert.match(conversion.system[0].text, /never infer a model, defer, image mode, or provider consent/);
for (const mode of [{transcribe_images:true},{image_mode:'analyze'}]) {
  const retry = await prepare.execute({source:'photo.png',...mode},{sessionID:'test'});
  assert.equal(JSON.parse(retry.content).status, 'choice_required');
}
const denial = {sessionID:'denial',messages:[{info:{role:'user'},parts:[{type:'text',text:'Convert photo.png text and description to MD. I do not approve image analysis with openrouter nvidia/nemotron-3.5-super-vl:free.'}]}],system:[]};
await promptHook({sessionID:'denial',messageID:'user-denial',prompt:{text:'Convert photo.png text and description to MD. I do not approve image analysis with openrouter nvidia/nemotron-3.5-super-vl:free.',files:[]}});
await contextHook(denial);
const deniedAnalyze = await prepare.execute({source:'photo.png',image_mode:'analyze',model_provider:'openrouter',model:'nvidia/nemotron-3.5-super-vl:free'},{sessionID:'denial'});
assert.equal(JSON.parse(deniedAnalyze.content).status, 'consent_declined');
await assert.rejects(hook.fn({tool:'read',sessionID:'test',input:{filePath:'photo.png'}}), /Use tokensaver_docs_prepare first/);
await assert.rejects(hook.fn({tool:'grep',sessionID:'test',input:{pattern:'image'}}), /Use tokensaver_docs_prepare first/);
const ordinary = {sessionID:'test',messages:[{info:{role:'user'},parts:[{type:'text',text:'What is in this photo?'}]}],system:[],tools:{read:{},glob:{},shell:{},tokensaver_docs_read:{}}};
await promptHook({sessionID:'test',messageID:'user-2',prompt:{text:'What is in this photo?',files:[]}});
await contextHook(ordinary);
assert.equal(ordinary.system.length, 0);
await hook.fn({tool:'read',sessionID:'test',input:{filePath:'photo.png'}});
await hook.fn({tool:'grep',sessionID:'test',input:{pattern:'image'}});
const alternative = {sessionID:'test',messages:[{info:{role:'user'},parts:[{type:'text',text:'Use Pandoc to convert photo.png to a Markdown file.'}]}],system:[],tools:{read:{},glob:{},shell:{},tokensaver_docs_read:{}}};
await promptHook({sessionID:'test',messageID:'user-3',prompt:{text:'Use Pandoc to convert photo.png to a Markdown file.',files:[]}});
await contextHook(alternative);
assert.equal(alternative.system.length, 0);
await hook.fn({tool:'read',sessionID:'test',input:{filePath:'photo.png'}});
const reset = {sessionID:'test',messages:[...conversion.messages,{info:{role:'assistant'},parts:[]},{info:{role:'user'},parts:[{type:'text',text:'What is in this photo?'}]}],system:[]};
await promptHook({sessionID:'test',messageID:'user-4',prompt:{text:'What is in this photo?',files:[]}});
await contextHook(reset);
assert.equal(reset.system.length, 0);
assert.equal(server.name, 'tokensaver-docs');
assert.equal(server.type, 'local');
assert.deepEqual(server.command.slice(-1), ['mcp']);
assert.equal(hook.name, 'execute.before');
await hook.fn({tool: 'other', input: {}});
'''
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(['node', '--input-type=module', '-e', script], env=dict(os.environ, XDG_CONFIG_HOME=tmp), capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_embedded_image_read_waits_for_choice_without_writing_beside_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / 'image.png'
            Image.new('RGB', (10, 12), 'blue').save(image)
            source_dir = root / 'read-only'
            source_dir.mkdir()
            payload = base64.b64encode(image.read_bytes()).decode()
            for name, prefix in [('lower.html', 'data:image/png;base64,'), ('upper.html', 'DATA:IMAGE/PNG;BASE64,')]:
                (source_dir / name).write_text('<p>Refunds within seven days.</p><img src="' + prefix + payload + '">')
            html = '<p>Refunds within seven days.</p><img src="data:image/png;base64,' + payload + '">'
            (source_dir / 'utf16le.html').write_bytes(b'\xff\xfe' + html.encode('utf-16-le'))
            (source_dir / 'utf16be.html').write_bytes(b'\xfe\xff' + html.encode('utf-16-be'))
            source_dir.chmod(0o555)
            script = '''
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { join, relative } from 'node:path';
import assert from 'node:assert/strict';
const {TokenSaverDocsPlugin} = await import(pathToFileURL(process.env.TOKENSAVER_DOCS_PLUGIN));
const plugin = await TokenSaverDocsPlugin();
for (const name of ['utf16be.html', 'utf16le.html', 'upper.html', 'lower.html']) {
  const source = join(process.env.TEST_SOURCE_DIR, name);
  const call = {args: {filePath: source}};
  await assert.rejects(plugin['tool.execute.before']({tool: 'read'}, call), /tokensaver_docs_prepare/);
  assert.equal(call.args.filePath, source);
  const prepared = JSON.parse(await plugin.tool.tokensaver_docs_prepare.execute({source, output: join(process.env.TEST_OUTPUT, name), image_mode: 'preserve'}));
  const output = prepared.files[0].output;
  assert.ok(relative(process.env.TEST_SOURCE_DIR, output).startsWith('..'));
  assert.ok((await readFile(output, 'utf8')).includes('seven days'));
  assert.equal(prepared.ai_calls, 0);
}
'''
            env = dict(os.environ, TOKENSAVER_DOCS_PLUGIN=str(Path(os.environ['TOKENSAVER_DOCS_PLUGIN']).resolve()),
                       TEST_SOURCE_DIR=str(source_dir), TEST_OUTPUT=str(root/'out'), XDG_CONFIG_HOME=str(root/'config'), TOKENSAVER_DOCS_CACHE_DIR=str(root/'cache'))
            try:
                result = subprocess.run(['node', '--input-type=module', '-e', script], env=env,
                                        capture_output=True, text=True, timeout=120)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            finally:
                source_dir.chmod(0o755)

    def test_raw_embedded_html_read_requires_explicit_preparation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            image=root/'image.png';Image.new('RGB',(10,12),'blue').save(image)
            source=root/'policy.html'
            source.write_text('<p>Refunds within seven days.</p><img alt="Refund policy" src="data:image/png;base64,'+base64.b64encode(image.read_bytes()).decode()+'">')
            script='''
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';
const {TokenSaverDocsPlugin}=await import(pathToFileURL(process.env.TOKENSAVER_DOCS_PLUGIN));
const plugin=await TokenSaverDocsPlugin();
const call={args:{filePath:process.env.TEST_HTML,offset:1000,limit:2000}};
await assert.rejects(plugin['tool.execute.before']({tool:'read'},call), /tokensaver_docs_prepare/);
assert.equal(call.args.filePath,process.env.TEST_HTML);
const result=JSON.parse(await plugin.tool.tokensaver_docs_prepare.execute({source:process.env.TEST_HTML,output:process.env.TEST_OUTPUT,image_mode:'placeholder'}));
const text=await readFile(result.files[0].output,'utf8');
assert.ok(text.includes('seven days'));
assert.ok(text.includes('[이미지]'));
assert.ok(!text.includes('data:image'));
assert.ok(!text.includes('!['));
assert.equal(result.total,1);
assert.equal(result.files[0].ai_calls,0);
console.log('PASS: native read asks and explicit placeholder preparation preserves text');
'''
            env=dict(os.environ,TOKENSAVER_DOCS_PLUGIN=str(Path(os.environ['TOKENSAVER_DOCS_PLUGIN']).resolve()),TEST_HTML=str(source),TEST_OUTPUT=str(root/'out'),XDG_CONFIG_HOME=str(root/'config'),TOKENSAVER_DOCS_CACHE_DIR=str(root/'cache'))
            result=subprocess.run(['node','--input-type=module','-e',script],env=env,capture_output=True,text=True,timeout=120)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
