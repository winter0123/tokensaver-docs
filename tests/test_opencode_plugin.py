import base64
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from PIL import Image


@unittest.skipUnless(os.environ.get('TOKENSAVER_DOCS_PLUGIN'), 'built OpenCode plugin not supplied')
class OpenCodePluginTests(unittest.TestCase):
    def test_v2_bounded_project_source_resolution(self):
        script = r"""
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {join} from 'node:path';
import {mkdtemp, mkdir, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
const {resolveProjectSource} = await import(pathToFileURL(process.env.TOKENSAVER_DOCS_PLUGIN));
const root=await mkdtemp(join(tmpdir(),'tokensaver-source-'));
await mkdir(join(root,'하위 폴더'));
await writeFile(join(root,'하위 폴더','test.html'),'<p>ok</p>');
assert.deepEqual(await resolveProjectSource('test.html',root),
  {status:'ready',source:join(root,'하위 폴더','test.html')});
await writeFile(join(root,'하위 폴더','한글.html'.normalize('NFD')),'x');
const unicode=await resolveProjectSource('한글.html',root);
assert.equal(unicode.status,'ready');
assert.equal(unicode.source.normalize('NFC'),join(root,'하위 폴더','한글.html').normalize('NFC'));
await writeFile(join(root,'test.html'),'<p>direct</p>');
assert.equal((await resolveProjectSource('test.html',root)).source,join(root,'test.html'));
await writeFile(join(root,'하위 폴더','ambiguous.html'),'a');
await writeFile(join(root,'ambiguous.html'),'b');
await mkdir(join(root,'두번째 폴더'));
await writeFile(join(root,'두번째 폴더','ambiguous.html'),'c');
const ambiguous=await resolveProjectSource('ambiguous.html'.replace('ambiguous','same'),root);
assert.equal(ambiguous.status,'source_not_found');
await writeFile(join(root,'두번째 폴더','ambiguous.html'),'d');
const matched=await resolveProjectSource('ambiguous.html',root);
assert.equal(matched.source,join(root,'ambiguous.html'));
assert.equal((await resolveProjectSource('../outside.html',root)).status,'source_outside_project');
assert.equal((await resolveProjectSource('not-here.html',root)).status,'source_not_found');
console.log('PASS project path and Unicode source resolution');
"""
        env = dict(os.environ, TOKENSAVER_DOCS_PLUGIN=str(Path(os.environ['TOKENSAVER_DOCS_PLUGIN']).resolve()))
        result = subprocess.run(['node', '--input-type=module', '-e', script],
                                env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_v2_service_first_model_selection_and_one_time_approval(self):
        script = r"""
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const {recordQuestionAnswers} = await import(pathToFileURL(process.env.TOKENSAVER_DOCS_PLUGIN));
const request={conversion:true,text:'Convert test.html to Markdown'};
const send=(title,options,selected,status='completed')=>recordQuestionAnswers({
  tool:'question',status,
  input:{questions:[{question:title,options:options.map(label=>({label}))}]},
  result:{output:{answers:[[selected]]}}
},request);
send('이미지를 Markdown에 어떻게 넣을까요?',
  ['이미지·글자·설명 넣기','이미지만 넣기'],'이미지·글자·설명 넣기');
assert.equal(request.uiMode,'analyze');
send('이미지 분석에 사용할 서비스(플랫폼)를 선택하세요.',
  ['Codex / GPT','Claude Code','OpenCode','API / OpenRouter','로컬 LLM'],'API / OpenRouter');
assert.deepEqual(request.uiRuntime,{runtime:'api',provider:'openrouter'});
request.catalogModels=[{provider:'openrouter',id:'anthropic/vision-test'}];
send('이미지 분석 모델을 선택하세요. 이후 변환에도 기본값으로 저장됩니다. 외부 서비스로 이미지가 전송됩니다.',
  ['anthropic/vision-test — image'],'anthropic/vision-test — image');
assert.deepEqual(request.uiModel,{provider:'openrouter',model:'anthropic/vision-test'});
assert.deepEqual(request.uiConsent,request.uiModel);
assert.deepEqual(request.uiPersistentConsent,request.uiModel);
const oneTime={conversion:true,uiMode:'analyze',
  uiModel:{provider:'openrouter',model:'anthropic/vision-test'}};
const oldSend=(selected,status='completed')=>recordQuestionAnswers({
  tool:'question',status,
  input:{questions:[{question:'OpenRouter anthropic/vision-test로 이미지 외부 전송을 허용할까요?',
    options:[{label:'이번에만 허용'},{label:'동의 안 함'}]}]},
  result:{output:{answers:[[selected]]}}
},oneTime);
oldSend('이번에만 허용');
assert.deepEqual(oneTime.uiConsent,oneTime.uiModel);
assert.equal(oneTime.uiPersistentConsent,undefined);
oneTime.uiConsent=null;
oldSend('이번에만 허용','error');
assert.equal(oneTime.uiConsent,null);
send('이미지를 Markdown에 어떻게 넣을까요?',
  ['이미지·글자·설명 넣기','이미지만 넣기'],'이미지·글자·설명 넣기');
send('이미지 분석에 사용할 서비스(플랫폼)를 선택하세요.',
  ['Codex / GPT','Claude Code','OpenCode','API / OpenRouter','로컬 LLM'],'로컬 LLM');
send('로컬 서버 제공자를 선택하세요.',
  ['Ollama','LM Studio','OpenAI 호환 서버'],'Ollama');
request.catalogModels=[{provider:'ollama',id:'llava:latest'}];
send('이미지 분석 모델을 선택하세요. 로컬 분석이므로 외부 전송 없음.',
  ['llava:latest'],'llava:latest');
assert.equal(request.uiRuntime.runtime,'local');
assert.equal(request.uiRuntime.provider,'ollama');
assert.equal(request.uiModel.provider,'local');
assert.equal(request.uiModel.model,'llava:latest');
assert.equal(request.uiPersistentConsent,null);
console.log('PASS form choices, catalog model and one-time authorization');
"""
        env = dict(os.environ, TOKENSAVER_DOCS_PLUGIN=str(Path(os.environ['TOKENSAVER_DOCS_PLUGIN']).resolve()))
        result = subprocess.run(['node', '--input-type=module', '-e', script],
                                env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_v2_question_form_answers_drive_choices_without_chat_reentry(self):
        # One completed OpenCode question tool result must be sufficient to
        # authorize a selected local mode. Image transfer needs an additional
        # explicit provider/model-specific answer, not the model selection alone.
        script = """
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';
const {recordQuestionAnswers} = await import(pathToFileURL(process.env.TOKENSAVER_DOCS_PLUGIN));
const request = {conversion:true, text:'Convert test.html to Markdown'};
const send = (question, option, answers, status='completed') => recordQuestionAnswers({
  tool:'question',status,
  input:{questions:[{question,options:option.map(label=>({label}))}]},
  result:{output:{answers:[[answers]]}}
},request);
send('test.html 안의 이미지를 Markdown에 어떻게 넣을까요?',
  ['이미지·글자·설명 넣기','이미지 링크만 넣기'], '이미지·글자·설명 넣기');
assert.equal(request.uiMode,'analyze');
assert.equal(request.uiConsent,null);
send('OpenRouter 이미지 분석 모델을 선택하세요 (외부 전송됩니다).',
  ['nvidia/nemotron-3.5-super-vl:free (Recommended)'],
  'nvidia/nemotron-3.5-super-vl:free (Recommended)');
assert.deepEqual(request.uiModel,{provider:'openrouter',model:'nvidia/nemotron-3.5-super-vl:free'});
assert.equal(request.uiConsent,null);
send('OpenRouter nvidia/nemotron-3.5-super-vl:free 모델로 이미지를 외부 전송하여 분석해도 될까요?',
  ['분석 동의','동의 안 함'],'분석 동의');
assert.deepEqual(request.uiConsent,request.uiModel);
send('OpenRouter nvidia/another:free 모델로 이미지를 외부 전송해도 될까요?',
  ['분석 동의','동의 안 함'],'분석 동의');
assert.deepEqual(request.uiConsent,request.uiModel);
send('test.html 안의 이미지를 Markdown에 어떻게 넣을까요?',
  ['이미지 링크만 넣기','이미지·글자·설명 넣기'],'이미지 링크만 넣기');
assert.equal(request.uiMode,'preserve');
assert.equal(request.uiConsent,null);
send('OpenRouter nvidia/nemotron-3.5-super-vl:free 모델로 이미지를 외부 전송해도 될까요?',
  ['분석 동의','동의 안 함'],'분석 동의','error');
assert.equal(request.uiConsent,null);
// A model-claimed answer not present in real form options cannot grant consent.
send('OpenRouter nvidia/nemotron-3.5-super-vl:free 모델로 이미지를 외부 전송해도 될까요?',
  ['동의 안 함'],'분석 동의');
assert.equal(request.uiConsent,null);
console.log('PASS: UI selection, explicit scoped consent, and deny-by-default');
"""
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                ['node', '--input-type=module', '-e', script],
                env=dict(os.environ, XDG_CONFIG_HOME=tmp),
                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_v2_registers_mcp_and_read_hook(self):
        script = '''
import { pathToFileURL } from 'node:url';
import { writeFile } from 'node:fs/promises';
import { join } from 'node:path';
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
assert.match(skill.content, /tokensaver_docs_prepare/);
assert.equal(skill.path.replaceAll('\\\\', '/').split('/').at(-1), 'SKILL.md');
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
const evidence = tools.get('tokensaver_docs_context');
assert.deepEqual(evidence.input.required, ['source','query']);
assert.equal(evidence.input.properties.use_configured_providers, undefined);
await hook.fn({tool:evidence.name, sessionID:'evidence', input:{}});
await assert.rejects(hook.fn({tool:'tokensaver-docs_context_documents',sessionID:'evidence',input:{}}), /guarded native/);
const evidenceFile = join(process.env.XDG_CONFIG_HOME, 'policy.md');
await writeFile(evidenceFile, '# Policy\\nRefunds are allowed for seven days.\\nCustom orders are excluded.\\n');
const evidenceArgs = {source:evidenceFile, query:'Refunds', max_tokens:300};
const evidenceResult = JSON.parse((await evidence.execute(evidenceArgs, {sessionID:'evidence'})).content);
assert.equal(evidenceResult.excerpts[0].start_line, 1);
assert.match(evidenceResult.excerpts[0].text, /Custom orders are excluded/);
assert.deepEqual(evidenceResult, JSON.parse(await legacy.tool.tokensaver_docs_context.execute(evidenceArgs)));
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
