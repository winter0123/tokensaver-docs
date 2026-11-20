"""Offline metadata and packaging tests for the three plugin-host paths."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "marketplace-plugin"
OPENCODE = ROOT / "plugins/opencode"


class MarketplaceMetadataTests(unittest.TestCase):
    def test_codex_skills_only_manifest(self):
        manifest = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "tokensaver-docs")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(manifest["interface"]["displayName"], "TokenSaver Docs")
        self.assertNotIn("mcpServers", manifest)
        self.assertFalse((PLUGIN / "mcp.json").exists())
        self.assertTrue((PLUGIN / "skills/tokensaver-docs/SKILL.md").is_file())

    def test_claude_skills_only_manifest(self):
        manifest = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "tokensaver-docs")
        self.assertFalse((PLUGIN / ".mcp.json").exists())
        skill = (PLUGIN / "skills/tokensaver-docs/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("context INPUT", skill)
        self.assertIn("prepare INPUT", skill)

    def test_platform_launchers(self):
        shell = PLUGIN / "scripts/run.sh"
        powershell = PLUGIN / "scripts/run.ps1"
        self.assertTrue(shell.is_file())
        self.assertTrue(powershell.is_file())
        self.assertEqual(shell.read_text(encoding="utf-8"),
                         (OPENCODE / "scripts/run.sh").read_text(encoding="utf-8"))
        self.assertEqual(powershell.read_text(encoding="utf-8"),
                         (OPENCODE / "scripts/run.ps1").read_text(encoding="utf-8"))
        if shutil.which("sh"):
            subprocess.run(["sh", "-n", str(shell)], check=True)

    def test_opencode_git_subdirectory_has_all_assets(self):
        pkg = json.loads((OPENCODE / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(pkg["name"], "tokensaver-docs-opencode")
        self.assertEqual(pkg["exports"]["."], "./index.js")
        self.assertEqual(pkg["exports"]["./tui"], "./tui.js")
        self.assertIn("tui.js", pkg["files"])
        for item in ("index.js", "tui.js", "runtime.js", "research-routing.json", "skills/tokensaver-docs/SKILL.md", "scripts/run.sh", "scripts/run.ps1"):
            self.assertTrue((OPENCODE / item).is_file(), item)
        self.assertEqual((OPENCODE / "research-routing.json").read_bytes(),
                         (ROOT / "tokensaver_docs/data/research-routing.json").read_bytes())
        source = (OPENCODE / "index.js").read_text(encoding="utf-8")
        self.assertIn("ensureTokenSaverExecutable", source)
        self.assertIn("./research-routing.json", source)

    def test_model_catalog_is_blocked_until_explicit_service_choice(self):
        """The original screenshot's model-first flow must not be possible anymore."""
        if not shutil.which("node"):
            self.skipTest("Node.js unavailable")
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ("index.js","runtime.js","research-routing.json"):
                shutil.copy2(OPENCODE / name,root / name)
            (root / "package.json").write_text('{"type":"module"}')
            stub=root / "node_modules" / "@opencode-ai" / "plugin"
            stub.mkdir(parents=True)
            (stub / "package.json").write_text('{"type":"module","exports":"./index.js"}')
            (stub / "index.js").write_text("export const tool = () => ({});")
            script=r"""
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const {requireSelectedImageService,recordQuestionAnswers,normalizeImageWizardQuestion}=await import(pathToFileURL(process.argv[1]));
const req={conversion:true,uiMode:'analyze'};
assert.equal(requireSelectedImageService(req,'opencode').stage,'service');
const original=Object.freeze({header:'AI 모델',question:'이미지 분석 모델을 선택하세요.',
  options:Object.freeze([Object.freeze({label:'openrouter/one'}),
    Object.freeze({label:'local llm api 연결'})])});
const premature=Object.freeze({questions:Object.freeze([original])});
const rewritten=normalizeImageWizardQuestion(premature,req);
assert.equal(rewritten.questions[0].header,'TokenSaver 서비스');
assert.equal(original.header,'AI 모델');
assert.equal(original.options[0].label,'openrouter/one');
assert.notEqual(rewritten.questions[0],original);
assert.notEqual(rewritten.questions,premature.questions);
assert.deepEqual(rewritten.questions[0].options.map(x=>x.label),
 ['GPT / Codex','Claude Code','OpenCode','로컬 LLM','API / OpenRouter']);
assert.deepEqual(requireSelectedImageService(req,'opencode').selection_ui.options.map(x=>x.label),
 ['GPT / Codex','Claude Code','OpenCode','로컬 LLM','API / OpenRouter']);
const answer=(prompt,labels,selected,status='completed')=>recordQuestionAnswers({
  tool:'question',status,
  input:{questions:[{question:prompt,header:'TokenSaver 서비스',
    options:labels.map(label=>({label}))}]},
  result:{output:{answers:[[selected]]}}
},req);
answer('이미지 분석에 사용할 서비스(플랫폼)를 먼저 선택하세요.',
  ['GPT / Codex','Claude Code','OpenCode','로컬 LLM','API / OpenRouter'],'로컬 LLM');
assert.equal(req.uiRuntime.runtime,'local');
assert.equal(requireSelectedImageService(req,'ollama').stage,'local_provider');
const wrongSecond=Object.freeze({questions:Object.freeze([
  Object.freeze({question:'Which model?',
    options:Object.freeze([Object.freeze({label:'openrouter/free'})])})
])});
const localQuestion=normalizeImageWizardQuestion(wrongSecond,req);
assert.equal(localQuestion.questions[0].header,'TokenSaver 로컬 제공자');
assert.equal(wrongSecond.questions[0].question,'Which model?');
answer('로컬 서버 제공자를 선택하세요.',
  ['Ollama','LM Studio','OpenAI 호환 서버'],'Ollama');
assert.deepEqual(req.uiRuntime,{runtime:'local',provider:'ollama'});
assert.equal(requireSelectedImageService(req,'ollama'),null);
req.catalogModels=[{id:'qwen2.5-vl:latest',provider:'ollama'}];
const modelQuestion=Object.freeze({questions:Object.freeze([
  Object.freeze({question:'Choose model',
    options:Object.freeze([Object.freeze({label:'fake cloud model'})])})
])});
const modelRewritten=normalizeImageWizardQuestion(modelQuestion,req);
assert.equal(modelRewritten.questions[0].header,'TokenSaver 모델');
assert.deepEqual(modelRewritten.questions[0].options.map(o=>o.label),['qwen2.5-vl:latest']);
assert.match(modelRewritten.questions[0].question,/외부 서비스로 이미지를 전송하지/);
assert.equal(modelQuestion.questions[0].options[0].label,'fake cloud model');
// V2 host's event.input is the writable replacement point, while its nested
// original question objects and arrays may be deeply frozen.
const beforeEvent={tool:'question',input:premature};
beforeEvent.input=normalizeImageWizardQuestion(beforeEvent.input,{conversion:true,uiMode:'analyze'});
assert.equal(beforeEvent.input.questions[0].header,'TokenSaver 서비스');
assert.equal(premature.questions[0].header,'AI 모델');
assert.equal(requireSelectedImageService(req,'openrouter').stage,'service_mismatch');
req.uiRuntime=null;
answer('이미지 분석에 사용할 서비스(플랫폼)를 먼저 선택하세요.',
  ['GPT / Codex','Claude Code','OpenCode','로컬 LLM','API / OpenRouter'],'OpenCode','error');
assert.equal(req.uiRuntime,null);
console.log('PASS mandatory runtime choice before catalog');
"""
            run=subprocess.run(['node','--input-type=module','-e',script,str(root/'index.js')],
                cwd=root,env=dict(os.environ),capture_output=True,text=True,timeout=25)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)

    def test_tui_model_search_picker_and_form_submission(self):
        """The separate TUI part provides native fuzzy-like search and replies to its own forms only."""
        if not shutil.which("node"):
            self.skipTest("Node.js unavailable")
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            from pathlib import Path
            root=Path(temp)
            shutil.copy2(OPENCODE / "tui.js", root / "tui.js")
            (root / "package.json").write_text('{"type":"module"}')
            stub=root / "node_modules" / "@opencode" / "plugin"
            stub.mkdir(parents=True)
            (stub / "package.json").write_text(
                '{"type":"module","exports":{"./tui":"./tui.js"}}')
            (stub / "tui.js").write_text("export const Plugin={define: value => value};")
            script=r"""
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const {default:plugin,tokensaverModelForm,searchTokensaverModels}=
  await import(pathToFileURL(process.argv[1]));
const form={id:'f1',sessionID:'s1',title:'Questions',fields:[{
  key:'q0',title:'TokenSaver 모델',description:'이미지 분석 모델을 선택하세요.',
  type:'string',custom:true,options:[
    {label:'openrouter/vision-large',value:'openrouter/vision-large'},
    {label:'openrouter/vision-small',value:'openrouter/vision-small'},
    {label:'ollama/qwen2.5-vl',value:'ollama/qwen2.5-vl'},
  ]}]};
assert.equal(tokensaverModelForm({title:'Questions',fields:[{...form.fields[0],title:'Other plugin'}]}),null);
const specs=tokensaverModelForm(form);
assert.equal(specs.options.length,3);
assert.deepEqual(searchTokensaverModels('vision small',specs.options).map(v=>v.value),
  ['openrouter/vision-small']);
let handler,reply,dialog;
const context={location:{directory:'/project'},
  data:{on(type,cb){assert.equal(type,'form.created');handler=cb;return ()=>{}},
    session:{form:{
      async sync(){},
      list(){return [form]},
      async reply(value){reply=value;}
    }}},
  ui:{dialog:{async select(value){dialog=value;return 'openrouter/vision-small'}}}
};
plugin.setup(context);
handler({type:'form.created',data:{form}});
await new Promise(resolve=>setTimeout(resolve,10));
assert.equal(dialog.title,'TokenSaver Docs · 이미지 모델 검색');
assert.deepEqual(dialog.search('ollama',dialog.options).map(v=>v.value),['ollama/qwen2.5-vl']);
assert.deepEqual(reply,{sessionID:'s1',formID:'f1',answer:{q0:'openrouter/vision-small'}});
console.log('PASS TUI model picker search and native form reply');
"""
            run=subprocess.run(['node','--input-type=module','-e',script,str(root/'tui.js')],
                cwd=root,env=dict(os.environ),capture_output=True,text=True,timeout=25)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)

    def test_opencode_question_ui_result_is_consumed_without_chat_reentry(self):
        """Exercise the actual Git plugin module with a stub-only SDK import."""
        if not shutil.which("node"):
            self.skipTest("Node.js unavailable")
        import os
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("index.js", "runtime.js", "research-routing.json"):
                shutil.copy2(OPENCODE / name, root / name)
            (root / "package.json").write_text('{"type":"module"}')
            stub = root / "node_modules" / "@opencode-ai" / "plugin"
            stub.mkdir(parents=True)
            (stub / "package.json").write_text('{"type":"module","exports":"./index.js"}')
            (stub / "index.js").write_text("export const tool = () => ({});")
            script = """
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const {recordQuestionAnswers} = await import(pathToFileURL(process.argv[1]));
const request = {conversion:true,text:'Convert test.html to MD'};
function answer(question, options, selected, status='completed') {
  recordQuestionAnswers({
    tool:'question', status,
    input:{questions:[{question,options:options.map(label=>({label}))}]},
    result:{output:{answers:[[selected]]}}
  },request);
}
answer('test.html 안의 이미지를 Markdown에 어떻게 넣을까요?',
  ['이미지·글자·설명 넣기','이미지 링크만 넣기'], '이미지·글자·설명 넣기');
assert.equal(request.uiMode,'analyze');
assert.equal(request.uiConsent,null);
answer('이미지 분석할 모델을 선택하세요 (외부 전송됩니다).',
  ['nvidia/nemotron-3.5-super-vl:free (Recommended)'],
  'nvidia/nemotron-3.5-super-vl:free (Recommended)');
assert.deepEqual(request.uiModel,{provider:'openrouter',model:'nvidia/nemotron-3.5-super-vl:free'});
assert.equal(request.uiConsent,null);
answer('OpenRouter nvidia/nemotron-3.5-super-vl:free 모델로 이미지를 외부 전송하여 분석해도 될까요?',
  ['분석 동의','동의 안 함'],'분석 동의');
assert.deepEqual(request.uiConsent,request.uiModel);
assert.equal(request.uiPersistentConsent,null);
answer('OpenRouter nvidia/nemotron-3.5-super-vl:free 모델로 앞으로 모든 변환 이미지를 외부 전송하는 데 계속 동의하나요?',
  ['분석 동의','동의 안 함'],'분석 동의');
assert.deepEqual(request.uiPersistentConsent,request.uiModel);
answer('test.html 안의 이미지를 Markdown에 어떻게 넣을까요?',
  ['이미지 링크만 넣기 (Recommended)','이미지·글자·설명 넣기'],
  '이미지 링크만 넣기 (Recommended)');
assert.equal(request.uiMode,'preserve');
assert.equal(request.uiConsent,null);
assert.equal(request.uiPersistentConsent,null);
answer('OpenRouter nvidia/nemotron-3.5-super-vl:free 모델로 이미지를 외부 전송하여 분석해도 될까요?',
  ['분석 동의','동의 안 함'],'분석 동의','error');
assert.equal(request.uiConsent,null);
answer('OpenRouter nvidia/nemotron-3.5-super-vl:free 모델로 이미지를 외부 전송하여 분석해도 될까요?',
  ['동의 안 함'],'분석 동의');
assert.equal(request.uiConsent,null);
"""
            run = subprocess.run(
                ["node", "--input-type=module", "-e", script, str(root / "index.js")],
                cwd=root, env=dict(os.environ, XDG_CONFIG_HOME=temp),
                capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_opencode_catalog_lists_configured_vision_models_without_inventing_support(self):
        """The host catalog is distinct from the external/local Python engines."""
        if not shutil.which("node"):
            self.skipTest("Node.js unavailable")
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            from pathlib import Path
            root = Path(temp)
            for name in ("index.js", "runtime.js", "research-routing.json"):
                shutil.copy2(OPENCODE / name, root / name)
            (root / "package.json").write_text('{"type":"module"}')
            stub = root / "node_modules" / "@opencode-ai" / "plugin"
            stub.mkdir(parents=True)
            (stub / "package.json").write_text('{"type":"module","exports":"./index.js"}')
            (stub / "index.js").write_text("export const tool = () => ({});")
            script = """
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const {pagedOpenCodeModels,selectableModelPage}=await import(pathToFileURL(process.argv[1]));
const example={data:[
  {id:'vl-2',providerID:'intranet',name:'Internal VL',enabled:true,
   capabilities:{input:['image','text']}},
  {id:'vision-free',providerID:'openrouter',name:'Vision Free',enabled:true,
   capabilities:{input:['image','text']}},
  {id:'text-only',providerID:'openrouter',name:'No images',enabled:true,
   capabilities:{input:['text']}},
  {id:'disabled-vl',providerID:'intranet',enabled:false,
   capabilities:{input:['image']}}
]};
const all=pagedOpenCodeModels(example);
assert.equal(all.total,2);
assert.deepEqual(all.models.map(x=>x.provider),['intranet','openrouter']);
assert.equal(all.models[0].conversion_available,true);
assert.equal(all.models[0].requires_installed_cli,true);
assert.equal(all.models[0].network_policy,'unknown');
const page=pagedOpenCodeModels(example,{query:'vision',limit:1});
assert.equal(page.total,1);
assert.equal(page.models[0].id,'vision-free');
const clickable=selectableModelPage(all);
assert.deepEqual(clickable.selection_ui.options.map(x=>x.label),['intranet/vl-2','openrouter/vision-free']);
assert.match(clickable.selection_ui.question,/외부 서비스/);
assert.match(clickable.selection_ui.next,/do not ask the user to retype/);
const filtered=selectableModelPage(pagedOpenCodeModels(example,{limit:1}));
assert.equal(filtered.selection_ui.options.at(-1).label,'다음 모델 보기');
console.log('PASS: host vision catalog and clickable model choices');
"""
            run = subprocess.run(
                ["node", "--input-type=module", "-e", script, str(root / "index.js")],
                cwd=root, env=dict(os.environ, XDG_CONFIG_HOME=temp),
                capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_opencode_activation_does_not_bootstrap_runtime(self):
        """Plugin setup must be fast/offline even for a new Git installation."""
        source = (OPENCODE / "index.js").read_text(encoding="utf-8")
        setup = source.split("export default {", 1)[1]
        self.assertIn("await findTokenSaverExecutable(", setup)
        self.assertNotIn("await ensureTokenSaverExecutable(", setup)
        self.assertIn("if (installedExecutable) {", setup)
        self.assertIn("await ctx.mcp.transform(", setup)

        if not shutil.which("node"):
            self.skipTest("Node.js unavailable")
        # No archive, no cache, and no consent: merely resolving an installed
        # executable must return null without attempting a download.
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            script = """
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
const {findTokenSaverExecutable} = await import(pathToFileURL(process.argv[1]));
assert.equal(await findTokenSaverExecutable(process.argv[2]), null);
"""
            env = dict(os.environ, TOKENSAVER_DOCS_RUNTIME_HOME=temp,
                       TOKENSAVER_DOCS_NO_BOOTSTRAP="1")
            proc = subprocess.run(
                ["node", "--input-type=module", "-e", script,
                 str(OPENCODE / "runtime.js"), temp],
                env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
