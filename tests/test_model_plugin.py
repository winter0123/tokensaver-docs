"""Source-plugin checks use a fake CLI so no account or external service is involved."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('node') and os.name != 'nt', 'POSIX fake CLI fixture; Windows executable is tested separately')
class ModelPluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        plugin = Path(__file__).resolve().parents[1] / 'plugins/opencode/index.js'
        (self.root/'index.mjs').write_text(plugin.read_text())
        package = self.root/'node_modules/@opencode-ai/plugin'
        package.mkdir(parents=True)
        (package/'package.json').write_text('{"type":"module","exports":"./index.js"}')
        (package/'index.js').write_text('export const tool = x => x; const schema = () => ({optional: schema, int: schema, min: schema, max: schema}); tool.schema = {string: schema, boolean: schema, number: schema, enum: schema};')
        binary = self.root/'bin/file-to-md'
        binary.parent.mkdir()
        binary.write_text('#!' + sys.executable + '\nimport json, sys\nprint(json.dumps({"status":"setup_required", "question":"Choose a model", "args":sys.argv[1:]}))\nraise SystemExit(2)\n')
        binary.chmod(0o755)

    def run_plugin(self, body):
        script = 'import assert from "node:assert/strict"; import {pathToFileURL} from "node:url"; const {FileToMdPlugin}=await import(pathToFileURL(process.argv[1])); const p=await FileToMdPlugin();\n' + body
        result = subprocess.run(['node','--input-type=module','-e',script,str(self.root/'index.mjs')], capture_output=True,text=True,timeout=30,env=dict(os.environ, FILE_TO_MD_CACHE_DIR=str(self.root/'cache')))
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        return result.stdout

    def test_prepare_passes_explicit_mode_and_one_time_model(self):
        self.run_plugin('''
const result=JSON.parse(await p.tool.file_to_md_prepare.execute({source:'a.html', image_mode:'analyze', model_provider:'openrouter', model:'chosen:free', allow_unverified_model:true}));
assert.deepEqual(result.args,['prepare','a.html','--output','converted','--image-mode','analyze','--model-provider','openrouter','--model','chosen:free','--allow-unverified-model']);
''')

    def test_analyze_mode_uses_image_processing_timeout(self):
        self.run_plugin('''
const originalTimer=globalThis.setTimeout;
let duration;
globalThis.setTimeout=(fn, ms, ...args) => {duration=ms; return originalTimer(fn,ms,...args);};
await p.tool.file_to_md_prepare.execute({source:'a.html',image_mode:'analyze'});
assert.equal(duration,7200000);
await p.tool.file_to_md_prepare.execute({source:'a.html',image_mode:'placeholder'});
assert.equal(duration,300000);
''')

    def test_setup_passes_explicit_save_and_defer(self):
        self.run_plugin('''
let result=JSON.parse(await p.tool.file_to_md_setup_model.execute({provider:'openrouter',model:'chosen:free',save_as_default:true,confirmed:true}));
assert.deepEqual(result.args,['setup-model','--provider','openrouter','--model','chosen:free','--save-as-default','--confirmed']);
result=JSON.parse(await p.tool.file_to_md_setup_model.execute({defer:true}));
assert.deepEqual(result.args,['setup-model','--defer']);
''')

    def test_native_read_never_selects_image_policy(self):
        source = self.root/'a.html'
        source.write_text('<p>Example</p><img src="data:image/png;base64,AA==">')
        self.run_plugin('''
const call={args:{filePath:''' + json.dumps(str(source)) + '''}};
await assert.rejects(p['tool.execute.before']({tool:'read'},call), /Choose a model/);
assert.equal(call.args.filePath,''' + json.dumps(str(source)) + ''');
''')

    def test_v2_read_path_argument_requires_choice(self):
        source=self.root/'v2.html'
        source.write_text('<img src="data:image/png;base64,AA==">')
        script='''
const {default:definition}=await import(pathToFileURL(process.argv[1]));
let hook;
await definition.setup({mcp:{transform:async fn=>fn({set(){}})},tool:{transform:async fn=>fn({add(){}}),hook:async(name,fn)=>{hook=fn}}});
await assert.rejects(hook({tool:'read',input:{path:SOURCE}}),/Choose a model/);
'''.replace('SOURCE',json.dumps(str(source)))
        self.run_plugin(script)

    def test_v2_bootstrap_tools_work_before_mcp_registration(self):
        self.run_plugin('''
const {default:definition}=await import(pathToFileURL(process.argv[1]));
const registered=[];
await definition.setup({tool:{transform:async fn=>fn({add:t=>registered.push(t)}),hook:async()=>{}},mcp:{transform:async()=>{assert.equal(registered.length,3);}}});
const prepare=registered.find(t=>t.name==='file_to_md_prepare');
assert.equal(prepare.options.codemode,false);
assert.deepEqual(prepare.input.required,['source']);
const reply=await prepare.execute({source:'a.html',image_mode:'placeholder'});
assert.equal(JSON.parse(reply.content).status,'setup_required');
assert.deepEqual(JSON.parse(reply.content).args,['prepare','a.html','--output','converted','--image-mode','placeholder']);
''')
