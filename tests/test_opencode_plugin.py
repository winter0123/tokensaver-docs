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
const {default: plugin} = await import(pathToFileURL(process.env.TOKENSAVER_DOCS_PLUGIN));
let server, hook;
await plugin.setup({mcp:{transform: async fn => fn({set: (name, value) => {server = {name, ...value}}})}, tool:{transform:async fn=>fn({add(){}}),hook: async (name, fn) => {hook = {name, fn}}}});
assert.equal(server.name, 'tokensaver-docs');
assert.equal(server.type, 'local');
assert.deepEqual(server.command.slice(-1), ['mcp']);
assert.equal(hook.name, 'execute.before');
await hook.fn({tool: 'other', input: {}});
'''
        result = subprocess.run(['node', '--input-type=module', '-e', script], env=os.environ.copy(), capture_output=True, text=True, timeout=30)
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
